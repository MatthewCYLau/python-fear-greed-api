from datetime import datetime
import uuid
from io import BytesIO
from flask import Blueprint, jsonify, request
from pydantic import ValidationError
import logging
import yfinance as yf
from api.auth.auth import auth_required
from api.common.constants import ASSETS_PLOTS_BUCKET_NAME, PANDAS_DF_DATE_FORMATE_CODE
from api.exception.models import BadRequestException
from api.model.models import ExportModelRequest, PredictStockFromModelRequest
from api.util.cloud_storage_connector import CloudStorageConnector
from api.util.util import (
    create_stock_close_linear_regression_model,
)
import joblib


bp = Blueprint("model", __name__)


@bp.route("/models/export-to-blob", methods=(["POST"]))
@auth_required
def export_model_to_gcs_blob(_):
    try:
        export_model_request = ExportModelRequest.model_validate_json(request.data)
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = export_model_request.stock
    years_ago = export_model_request.years

    data = yf.Ticker(stock_symbol)
    df = data.history(period=f"{years_ago}y")

    # Create a numerical representation of the time index
    model = create_stock_close_linear_regression_model(df)

    model_id = uuid.uuid4()
    pkl_filename = f"{model_id}.pkl"
    joblib.dump(model, pkl_filename)

    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )
    cloud_storage_connector.upload_pkl(stock_symbol, pkl_filename, pkl_filename)
    return jsonify({"model_id": model_id}), 200


@bp.route("/models/predict-from-blob", methods=(["POST"]))
@auth_required
def predict_stock_from_gcs_blob_model(_):
    try:
        predict_model_request = PredictStockFromModelRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = predict_model_request.stock
    future_date = predict_model_request.future_date
    model_id = predict_model_request.pkl_model_id
    pkl_filename = f"{model_id}.pkl"

    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )

    if not cloud_storage_connector.pkl_exists(stock_symbol, pkl_filename):
        raise BadRequestException(
            f"Blob for stock {stock_symbol} with model ID {pkl_filename} does not exist!",
            status_code=400,
        )

    blob_bytes = cloud_storage_connector.download_pkl(stock_symbol, pkl_filename)

    model = joblib.load(
        BytesIO(blob_bytes)
    )  # create a file-like object in memory from the bytes

    now = datetime.now()
    future_days = (
        datetime.strptime(future_date, PANDAS_DF_DATE_FORMATE_CODE) - now
    ).days

    future_days = 365 + future_days

    # Predict the price for the future date
    future_price = model.predict([[future_days]])[0]
    logging.info(f"Price prediction 1: {future_price}")
    return (
        jsonify(
            {"stock_symbol": stock_symbol, "price_prediction": round(future_price, 2)}
        ),
        200,
    )
