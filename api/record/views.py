from flask import Blueprint, request
from api.db.setup import db
from api.util.util import generate_response


bp = Blueprint("records", __name__)


@bp.route("/records", methods=(["GET"]))
def get_records():
    count = int(request.args["count"]) if "count" in request.args else 0
    records = list(db["records"].find().sort("_id", -1).limit(count))
    return generate_response(records)
