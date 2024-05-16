import os
import logging
import time
import random
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv("config/.env")

from flask import Flask, jsonify  # noqa: E402
from flask_cors import CORS  # noqa: E402
from .db.setup import db_connect  # noqa: E402
from api.user import views as user  # noqa: E402
from api.alert import views as alert  # noqa: E402
from api.record import views as record  # noqa: E402
from api.event import views as event  # noqa: E402
from api.analysis import views as analysis  # noqa: E402
from api.rate_limiter.rate_limiter import limiter  # noqa: E402
from api.util.util import return_random_int  # noqa: E402
from api.exception.models import (  # noqa: E402
    UnauthorizedException,
    BadRequestException,
)


app = Flask(__name__)
limiter.init_app(app)


CORS(app, resources={r"/*": {"origins": "*"}})
app.register_blueprint(user.bp, url_prefix="/api")
app.register_blueprint(alert.bp, url_prefix="/api")
app.register_blueprint(record.bp, url_prefix="/api")
app.register_blueprint(event.bp, url_prefix="/api")
app.register_blueprint(analysis.bp, url_prefix="/api")

logging.basicConfig(level=logging.INFO)


@app.errorhandler(UnauthorizedException)
@app.errorhandler(BadRequestException)
def handle_unauthorized_exception(e):
    return e.generate_exception_response()


if os.environ.get("MONGO_DB_CONNECTION_STRING"):
    db_connect()


@app.route("/async")
async def get_random_int():
    start_time = time.perf_counter()
    futures = [return_random_int(x=x) for x in range(random.randint(1, 5))]
    results = await asyncio.gather(*futures)
    response = [{"result": i} for i in results]
    end_time = time.perf_counter()
    formatted_time_taken = "{:.2f}".format(round(end_time - start_time, 2))
    logging.info(f"Time taken: {formatted_time_taken}")
    return jsonify(response)


@app.route("/random")
def get_random_int_http_request():
    response = requests.get(
        "https://www.randomnumberapi.com/api/v1.0/random?min=100&max=1000"
    )
    if response.status_code == 200:
        random_num = response.json()[0]
        return jsonify({"random_num": random_num}), 200
    else:
        raise BadRequestException("Get random number failed!", status_code=400)


@app.route("/ping")
def ping():
    return "pong!"
