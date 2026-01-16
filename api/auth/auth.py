from flask import request
from api.db.setup import db
from api.exception.models import UnauthorizedException
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import jwt
import logging
from functools import wraps


def auth_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):

        token = None

        if "x-auth-token" in request.headers:
            token = request.headers["x-auth-token"]

        if not token:
            raise UnauthorizedException("Token missing", status_code=401)

        try:
            data = jwt.decode(token, os.environ.get("JWT_SECRET"), algorithms="HS256")
            user = db["users"].find_one({"email": data["email"]}, {"password": False})
        except Exception as e:
            logging.error(e)
            raise UnauthorizedException("Invalid token", status_code=401)

        return f(user, *args, **kwargs)

    return decorator


def validate_google_oauth_token(token):
    try:
        id_info = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ.get("OAUTH_CLIENT_ID")
        )

        user_id = id_info["sub"]
        email = id_info["email"]
        name = id_info["name"]

        return True, user_id, email, name

    except ValueError as e:
        logging.error(f"Error validating token: {e}")
        return False, None, None, None


def super_user_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        user_email = args[0]["email"]
        if user_email == "lau.cy.matthew@gmail.com":
            logging.info(f"Requestor email is super user: {user_email}")
        else:
            raise UnauthorizedException("User unauthorized!", status_code=401)

        return f(*args, **kwargs)

    return decorator
