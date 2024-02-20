from flask import Blueprint, jsonify
import logging
from api.util.util import (
    generate_response,
)
from api.auth.auth import auth_required

bp = Blueprint("analysis", __name__)


@bp.route("/analysis", methods=(["GET"]))
@auth_required
def get_stock_analysis(_):
    try:
        analysis = "Ok"
        return generate_response(analysis)
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get stock analysis failed"}), 500
