import os
import logging
import time
import random
import asyncio
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
    futures = [return_random_int(x) for x in range(random.randint(1, 5))]
    results = await asyncio.gather(*futures)
    response = [{"result": i} for i in results]
    end_time = time.perf_counter()
    formatted_time_taken = "{:.2f}".format(round(end_time - start_time, 2))
    logging.info(f"Time taken: {formatted_time_taken}")
    return jsonify(response)


@app.route("/ping")
def ping():
    return "pong!"
