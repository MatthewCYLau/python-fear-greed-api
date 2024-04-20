from flask import Blueprint, jsonify
import logging
from api.util.util import (
    generate_response,
)
from api.auth.auth import auth_required
from .models import Event

bp = Blueprint("event", __name__)


@bp.route("/events/me", methods=(["GET"]))
@auth_required
def get_alerts_created_by_current_user(user):
    try:
        events = Event.get_events_by_alert_created_by(user["_id"])
        return generate_response(events)
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get events by current user failed"}), 500
