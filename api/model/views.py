from flask import Blueprint, jsonify, request
from pydantic import ValidationError
import logging
import yfinance as yf
from api.analysis.views import ASSETS_PLOTS_BUCKET_NAME
from api.auth.auth import auth_required
from api.model.models import ExportModelRequest
from api.util.cloud_storage_connector import CloudStorageConnector
from api.util.util import (
    create_stock_close_linear_regression_model,
    generate_pkl_blob_filename,
)
import joblib


bp = Blueprint("model", __name__)


@bp.route("/models/export-to-blob", methods=(["POST"]))
@auth_required
def export_model_to_gcs_blob(_):
    try:
        impact_request = ExportModelRequest.model_validate_json(request.data)
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = impact_request.stock
    years_ago = impact_request.years

    data = yf.Ticker(stock_symbol)
    df = data.history(period=f"{years_ago}y")

    # Create a numerical representation of the time index
    model = create_stock_close_linear_regression_model(df)

    pkl_filename = generate_pkl_blob_filename()
    joblib.dump(model, pkl_filename)

    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )
    blob_public_url = cloud_storage_connector.upload_pkl(
        stock_symbol, pkl_filename, pkl_filename
    )
    return jsonify({"model_url": blob_public_url}), 200
