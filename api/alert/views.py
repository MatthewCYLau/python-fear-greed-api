from flask import Blueprint, request, jsonify
import logging
from bson.objectid import ObjectId
from api.db.setup import db
from api.util.util import (
    generate_response,
)
from api.auth.auth import auth_required
from .models import Alert
from api.exception.models import UnauthorizedException, BadRequestException

bp = Blueprint("alert", __name__)


@bp.route("/alerts", methods=(["GET"]))
@auth_required
def get_alerts(_):
    count = int(request.args["count"]) if "count" in request.args else 0
    max_index = int(request.args["maxIndex"]) if "maxIndex" in request.args else 100
    alerts = Alert.get_alerts(count, max_index)
    return generate_response(alerts)


@bp.route("/alerts/me", methods=(["GET"]))
@auth_required
def get_alerts_created_by_current_user(user):
    try:
        alerts = Alert.get_alerts_by_created_by(user["_id"])
        return generate_response(alerts)
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get alerts by current user failed"}), 500


@bp.route("/alerts/<alert_id>", methods=(["GET"]))
@auth_required
def get_alert_by_id(_, alert_id):
    try:
        alert = Alert.get_alert_by_id(alert_id)
        if alert:
            return generate_response(alert)
        else:
            return "alert not found", 404
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get alert by ID failed"}), 500


@bp.route("/alerts", methods=(["POST"]))
@auth_required
def create_alert(user):
    data = request.get_json()
    index = data["index"]
    if (int(index) > 100 or int(index) <= 0):
        raise BadRequestException("Index must be between 1 and 100 inclusive", status_code=400)
    new_alert = Alert(
        index=index,
        note=data["note"],
        created_by=user["_id"],
    )
    res = db.alerts.insert_one(vars(new_alert))
    if res.inserted_id:
        return jsonify({"alert_id": str(res.inserted_id)}), 201
    else:
        return jsonify({"message": "Create alert failed"}), 500


@bp.route("/alerts/<alert_id>", methods=["DELETE"])
@auth_required
def delete_alert_by_id(user, alert_id):
    alert = Alert.get_alert_by_id(alert_id)
    if alert["created_by"] != user["_id"]:
        raise UnauthorizedException(
            "User is not authorized to delete alert", status_code=401
        )

    try:
        res = db["alerts"].delete_one({"_id": ObjectId(alert_id)})
        if res.deleted_count:
            return jsonify({"message": "alert deleted"}), 200

        else:
            return jsonify({"message": "alert not found"}), 404
    except Exception:
        return jsonify({"message": "Delete alert by ID failed"}), 500


@bp.route("/alerts/<alert_id>", methods=["PUT"])
@auth_required
def update_alert_by_id(_, alert_id):
    data = request.get_json()
    if not data or not data["index"] or not data["note"]:
        return jsonify({"message": "Missing field"}), 400

    try:
        res = Alert.update_alert_by_id(alert_id=alert_id, data=data)
        if res.matched_count:
            return jsonify({"message": "alert updated"}), 200
        else:
            return jsonify({"message": "alert not found"}), 404
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Update alert failed"}), 500
