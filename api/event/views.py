from flask import Blueprint, jsonify, request
import logging
from api.util.util import generate_response, value_is_true
from api.auth.auth import auth_required
from .models import Event

bp = Blueprint("event", __name__)


@bp.route("/events/me", methods=(["GET"]))
@auth_required
def get_alerts_created_by_current_user(user):
    acknowledged = request.args.get("acknowledged", default=False, type=value_is_true)
    try:
        events = Event.get_events_by_alert_created_by(user["_id"], acknowledged)
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
