import os
import logging
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from .db.setup import db_connect
from api.user import views as user
from api.alert import views as alert
from api.record import views as record
from api.event import views as event
from api.exception.models import *

load_dotenv("config/.env")


app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})
app.register_blueprint(user.bp, url_prefix="/api")
app.register_blueprint(alert.bp, url_prefix="/api")
app.register_blueprint(record.bp, url_prefix="/api")
app.register_blueprint(event.bp, url_prefix="/api")

logging.basicConfig(level=logging.INFO)


@app.errorhandler(UnauthorizedException)
@app.errorhandler(BadRequestException)
def handle_unauthorized_exception(e):
    return e.generate_exception_response()


if os.environ.get("MONGO_DB_CONNECTION_STRING"):
    db_connect()


@app.route("/ping")
def ping():
    return "pong!"
