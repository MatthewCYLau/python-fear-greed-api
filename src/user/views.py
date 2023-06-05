from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from bson.objectid import ObjectId
from src.db.setup import db
from src.util.util import generate_response
from src.auth.auth import auth_required
from src.exception.models import UnauthorizedException, BadRequestException
import os
import jwt
import logging
from datetime import datetime, timezone, timedelta
from .models import User

bp = Blueprint("user", __name__)


@bp.route("/users", methods=(["GET"]))
def get_users():
    email = request.args.get("email")
    query = {"email": email} if request.args.get("email") else {}

    users = list(db["users"].find(query, {"password": False}))
    return generate_response(users)


@bp.route("/users/<user_id>", methods=(["GET"]))
def get_user_by_id(user_id):
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)}, {"password": False})
        if user:
            return generate_response(user)
        else:
            return "User not found", 404
    except Exception:
        return jsonify({"message": "Get user by ID failed"}), 500


@bp.route("/users", methods=(["POST"]))
def register_user():
    data = request.get_json()
    user = User.get_user_by_email(data["email"])
    if user:
        raise BadRequestException("Email already registered", status_code=400)
    new_user = User(
        email=data["email"],
        password=data["password"],
        name=data["name"],
        isEmailVerified=True,
        created=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    try:
        if new_user.save_user_to_db():
            return jsonify({"message": "User created"}), 201
        else:
            return jsonify({"errors": [{"message": "Failed to create user"}]}), 500
    except Exception as e:
        logging.error(e)
        return jsonify({"errors": [{"message": "Failed to create user"}]}), 500


@bp.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        res = db["users"].delete_one({"_id": ObjectId(user_id)})
        if res.deleted_count:
            return jsonify({"message": "User deleted"}), 200
        else:
            return jsonify({"message": "User not found"}), 404
    except Exception:
        return jsonify({"message": "Delete user by ID failed"}), 500


@bp.route("/auth", methods=["GET"])
@auth_required
def get_auth_user(user):
    return generate_response(user)


@bp.route("/auth", methods=["POST"])
def login_user():

    data = request.get_json()

    if not data or not data["email"] or not data["password"]:
        raise UnauthorizedException("User not authorized", status_code=401)

    user = User.get_user_by_email(data["email"])

    if user and check_password_hash(user["password"], data["password"]):
        if not user["isEmailVerified"]:
            raise UnauthorizedException(
                "User email has not been verified", status_code=401
            )

        token = jwt.encode(
            {"email": user["email"], "exp": datetime.utcnow() + timedelta(minutes=30)},
            os.environ.get("JWT_SECRET"),
            algorithm="HS256",
        )
        return jsonify({"token": token})

    raise UnauthorizedException("User not authorized", status_code=401)

@bp.route("/users/<user_id>", methods=["PUT"])
@auth_required
def update_user_by_id(current_user, user_id):
    data = request.get_json()
    if not data or not data["email"] or not data["password"] or not data["name"]:
        return jsonify({"message": "Missing field"}), 400
    if current_user["email"] != data["email"]:
        user = db["users"].find_one({"email": data["email"]})
        if user:
            raise BadRequestException("Email already registered", status_code=400)
    try:
        res = User.update_user_by_id(user_id=user_id, data=data)
        if res.matched_count:
            return jsonify({"message": "User updated"}), 200
        else:
            return jsonify({"message": "User not found"}), 404
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Update project failed"}), 500
