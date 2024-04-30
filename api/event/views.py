from flask import Blueprint, jsonify, request
from api.common.constants import DATETIME_FORMATE_CODE
import logging
from api.util.util import generate_response, value_is_true, validate_date_string
from api.auth.auth import auth_required
from api.exception.models import BadRequestException
from datetime import datetime
from .models import Event

bp = Blueprint("event", __name__)


@bp.route("/events/me", methods=(["GET"]))
@auth_required
def get_alerts_created_by_current_user(user):
    acknowledged = request.args.get("acknowledged", default=False, type=value_is_true)
    start_date = request.args["startDate"] if "startDate" in request.args else None
    end_date = request.args["endDate"] if "endDate" in request.args else None

    dates_input = [start_date, end_date]

    if start_date and end_date:
        if not all([validate_date_string(i) for i in dates_input]):
            raise BadRequestException(
                "Invalid date input. Must be in format DD-MM-YYYY", status_code=400
            )
        else:
            start_date = datetime.strptime(start_date, DATETIME_FORMATE_CODE)
            end_date = datetime.strptime(end_date, DATETIME_FORMATE_CODE)
    try:
        events = Event.get_events_by_alert_created_by(
            user["_id"], acknowledged, start_date, end_date
        )
        return generate_response(events)
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get events by current user failed"}), 500


@bp.route("/events/<event_id>", methods=["PUT"])
@auth_required
def update_event_by_id(_, event_id):
    data = request.get_json()
    if not data or not data["acknowledged"]:
        return jsonify({"message": "Missing field"}), 400

    try:
        res = Event.update_event_by_id(event_id=event_id, data=data)
        if res.matched_count:
            return jsonify({"message": "Event updated"}), 200
        else:
            return jsonify({"message": "Event not found"}), 404
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Update event failed"}), 500
