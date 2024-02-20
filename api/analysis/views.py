from flask import Blueprint, jsonify, request
import logging
import yfinance as yf
from api.auth.auth import auth_required
from api.exception.models import BadRequestException


bp = Blueprint("analysis", __name__)


@bp.route("/analysis", methods=(["GET"]))
@auth_required
def get_stock_analysis(_):
    stock_symbol = request.args.get("stock", default=None, type=None)
    if not stock_symbol:
        raise BadRequestException("Provide a stock symbol", status_code=400)
    logging.info(f"Analysing stock with ticker symbol {stock_symbol}...")
    try:
        data = yf.Ticker(stock_symbol)
        logging.info(data.history(period="1mo"))
        return "Ok"
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get stock analysis failed"}), 500
