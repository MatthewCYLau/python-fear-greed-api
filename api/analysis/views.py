import asyncio
from datetime import datetime
from itertools import repeat
import statistics
from flask import Blueprint, jsonify, make_response, request
from matplotlib.dates import relativedelta
from api.db.setup import db
from bson.objectid import ObjectId
from concurrent.futures import ProcessPoolExecutor
from pydantic import ValidationError
import time
import base64
import logging
import heapq
import json
import yfinance as yf
import matplotlib
import matplotlib.pyplot as plt
import math
import multiprocessing
from google.cloud import pubsub_v1
from api.auth.auth import auth_required
from api.common.constants import (
    ANALYSIS_JOB_CREATION_DAILY_LIMIT,
    ASSETS_PLOTS_BUCKET_NAME,
    DATETIME_FORMATE_CODE,
    DEFAULT_TARGET_PE_RATIO,
    PANDAS_DF_DATE_FORMATE_CODE,
    TOPIC_NAME,
    VALID_CURRENCIES,
)
from api.util.util import (
    generate_dividend_yield_df,
    generate_monthly_mean_close_df,
    generate_response,
    generate_stock_fair_value,
    get_currency_impact_stock_return_df,
    predict_price_linear_regression,
    return_delta,
    generate_figure_blob_filename,
    get_years_ago_formatted,
    validate_date_string_for_pandas_df,
    value_is_true,
)
from api.util.cloud_storage_connector import CloudStorageConnector
from api.exception.models import BadRequestException
from api.analysis.models import (
    AnalyseCurrencyImpactOnReturnRequest,
    AnalysisJob,
    CreateStockPlotRequest,
    AnalysisJobRequest,
    PricePredictionRequest,
)
from api.record.models import Record
from sklearn.linear_model import LinearRegression


matplotlib.use("agg")

bp = Blueprint("analysis", __name__)


@bp.route("/analysis", methods=(["GET"]))
@auth_required
def get_stock_analysis(_):
    stock_symbol = request.args.get("stock", default=None, type=None)
    index_symbol = request.args.get("index", default=None, type=None)
    years_ago = request.args.get("years", default=1, type=int)
    correlation_stock_symbol = request.args.get(
        "correlationStock", default="", type=None
    )

    target_fear_greed_index = request.args.get(
        "targetFearGreedIndex", default=50, type=int
    )
    target_pe_ratio = request.args.get(
        "targetPeRatio", default=DEFAULT_TARGET_PE_RATIO, type=float
    )

    if int(years_ago) > 3:
        return jsonify({"message": "Maximum three years!"}), 400

    if index_symbol:
        data = yf.Ticker(index_symbol)
        index_info = data.info
        return (
            jsonify(
                {
                    "index": index_info.get("symbol"),
                    "open": index_info.get("open"),
                    "previousClose": index_info.get("previousClose"),
                }
            ),
            200,
        )

    if not stock_symbol:
        raise BadRequestException("Provide a stock symbol", status_code=400)
    logging.info(f"Analysing stock with ticker symbol {stock_symbol}...")
    try:
        data = yf.Ticker(stock_symbol)
        stock_info = data.info

        if stock_info.get("currentPrice") and stock_info.get("trailingEps"):
            current_price = stock_info["currentPrice"]
            EPS = stock_info["trailingEps"]
            PE_ratio = float("{:.2f}".format(current_price / EPS))
            logging.info(f"{stock_symbol} has PE ratio of {PE_ratio}")
        else:
            logging.info(
                f"{stock_symbol} info does not offer current price and trailing earnings per share (EPS)"
            )
            PE_ratio = float(-1)

        df = data.history(period=f"{years_ago}y")
        df["Daily change percentage"] = round(df["Close"].pct_change() * 100, 2)

        for index, row in df.tail().iterrows():
            logging.info(f"Most recent close with index {index} is {row.Close}")

        df_tail = df.tail().copy()
        df_tail["Close Doubled"] = df_tail["Close"].apply(lambda x: 2 * x)
        logging.info(df_tail)

        most_recent_close = df.tail(1)["Close"].values[0]
        most_recent_close = float("{:.2f}".format(most_recent_close))
        most_recent_fear_greed_index = int(Record.get_most_recent_record()["index"])

        period_high = float("{:.2f}".format(df["Close"].max()))
        logging.info(
            f"Period high is {period_high} on {df['Close'].idxmax().strftime(DATETIME_FORMATE_CODE)}"
        )

        period_low = float("{:.2f}".format(df["Close"].min()))
        logging.info(
            f"Period low is {period_low} on {df['Close'].idxmin().strftime(DATETIME_FORMATE_CODE)}"
        )

        most_early_row = df.head(1)
        most_early_row_date = most_early_row.index.strftime(DATETIME_FORMATE_CODE)[0]
        most_early_close = most_early_row["Close"].values[0]

        period_change = float("{:.2f}".format(most_recent_close - most_early_close))
        logging.info(f"Period change is {period_change} from {most_early_row_date}")

        monthly_mean_close_df = generate_monthly_mean_close_df(df)

        rolling_averages = {}

        for i in (50, 100, 200):
            rolling_avg = df.rolling(window=i).mean()
            current_rolling_avg = rolling_avg.iloc[-1]["Close"]
            logging.info(f"{i} day rolling average is: {current_rolling_avg:.2f}")
            rolling_averages[i] = float("{:.2f}".format(current_rolling_avg))
        with ProcessPoolExecutor(1) as exe:
            future = exe.submit(
                generate_stock_fair_value,
                most_recent_close,
                most_recent_fear_greed_index,
                PE_ratio,
                target_fear_greed_index=target_fear_greed_index,
                target_pe_ratio=target_pe_ratio,
            )
            fair_value = future.result()

        correlation = 0

        if correlation_stock_symbol:
            correlation_stock_data = yf.download(
                [stock_symbol, correlation_stock_symbol], get_years_ago_formatted()
            )["Close"]

            logging.info(correlation_stock_data.head())
            correlation = float(
                "{:.2f}".format(
                    correlation_stock_data[stock_symbol].corr(
                        correlation_stock_data[correlation_stock_symbol]
                    )
                )
            )

            logging.info(
                f"{stock_symbol} closing price correlation with {correlation_stock_symbol}: {correlation}"
            )

        groupby_day_of_week = df.groupby(df.index.day_name())["Close"].mean()
        monday_mean_close = float("{:.2f}".format(groupby_day_of_week.loc["Monday"]))
        logging.info(f"Mean close on Mondays: {monday_mean_close}")

        close_standard_deviation = round(df["Close"].std(), 2)
        logging.info(f"Close standard deviation: {close_standard_deviation}")

        initial_val = df["Close"].iloc[0]
        final_val = df["Close"].iloc[-1]
        total_roi = (final_val / initial_val) - 1

        num_years = (df.index[-1] - df.index[0]).days / 365.25
        cagr = (final_val / initial_val) ** (1 / num_years) - 1

        logging.info(f"Total ROI: {total_roi:.2%}")
        logging.info(f"Annualised return (CAGR): {cagr:.2%}")

        result_dict = {
            "stock": stock_symbol,
            "close": most_recent_close,
            "mostRecentFearGreedIndex": most_recent_fear_greed_index,
            "fairValue": fair_value,
            "delta": return_delta(fair_value, most_recent_close),
            "peRatio": PE_ratio,
            "rolling_averages": rolling_averages,
            "data": json.loads(
                df.tail(10)
                .sort_values(
                    by="Date",
                    ascending=False,
                )
                .to_json(orient="table")
            )["data"],
            "correlationStock": correlation_stock_symbol,
            "correlation": correlation,
            "periodLow": period_low,
            "periodHigh": period_high,
            "periodChange": period_change,
            "closeMonthlyAverage": json.loads(
                monthly_mean_close_df.to_json(orient="table")
            )["data"],
            "closeStandardDeviation": close_standard_deviation,
            "roi": {"total": round(total_roi, 2), "cagr": round(cagr, 2)},
        }

        return (
            jsonify(result_dict),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get stock analysis failed"}), 500


@bp.route("/analysis-jobs/<analysis_id>", methods=["DELETE"])
@auth_required
def delete_alert_by_id(_, analysis_id):
    try:
        res = db["analysis_jobs"].delete_one({"_id": ObjectId(analysis_id)})
        if res.deleted_count:
            return jsonify({"message": "Analysis job deleted"}), 200

        else:
            return jsonify({"message": "Analysis job not found"}), 404
    except Exception:
        return jsonify({"message": "Delete alert by ID failed"}), 500


@bp.route("/analysis-jobs", methods=(["POST"]))
@auth_required
def create_analysis_job(user):
    data = request.get_json()
    current_user_analysis_jobs_past_one_day = (
        AnalysisJob.get_analysis_jobs_by_created_by_within_hours(user["_id"])
    )
    logging.info(
        f"Current user has created {len(current_user_analysis_jobs_past_one_day)} analysis jobs past 24 hours."
    )

    if (
        len(current_user_analysis_jobs_past_one_day)
        >= ANALYSIS_JOB_CREATION_DAILY_LIMIT
    ):
        return (
            jsonify(
                {
                    "errors": [
                        {
                            "message": f"User cannot create more than {ANALYSIS_JOB_CREATION_DAILY_LIMIT} analysis jobs every 24 hours!"
                        }
                    ]
                }
            ),
            500,
        )
    try:
        analysis_job_request = AnalysisJobRequest.model_validate_json(request.data)
        new_analysis_job = AnalysisJob(
            stock_symbol=analysis_job_request.stock,
            target_fear_greed_index=analysis_job_request.targetFearGreedIndex,
            target_pe_ratio=analysis_job_request.targetFearGreedIndex,
            created_by=user["_id"],
        )
        analysis_job_id = new_analysis_job.save_analysis_job_to_db()
        logging.info(f"Created analysis job with id: {analysis_job_id}")
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(e)
        return jsonify({"errors": [{"message": "Failed to create analysis job"}]}), 500
    try:
        publisher = pubsub_v1.PublisherClient()
        job_data_dict = {
            "StockSymbol": data["stock"],
            "TargetFearGreedIndex": data["targetFearGreedIndex"],
            "TargetPeRatio": data["targetPeRatio"],
            "JobId": str(analysis_job_id),
        }
        job_data_encode = json.dumps(job_data_dict, indent=2).encode("utf-8")
        future = publisher.publish(TOPIC_NAME, job_data_encode)
        message_id = future.result()
        return (
            jsonify({"messageId": message_id, "analysisJobId": str(analysis_job_id)}),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Create analysis job failed"}), 500


@bp.route("/analysis-jobs", methods=(["GET"]))
@auth_required
def get_analysis_jobs(_):
    page_size = int(request.args["pageSize"]) if "pageSize" in request.args else 10
    current_page = int(request.args["page"]) if "page" in request.args else 1
    try:
        total_records = db["analysis_jobs"].estimated_document_count()
        total_pages = math.ceil(total_records / page_size)
        if current_page > total_pages:
            return (
                jsonify(
                    {
                        "errors": [
                            {
                                "message": f"Requested page {current_page} exceeds max page size"
                            }
                        ]
                    }
                ),
                400,
            )
        analysis_jobs = list(
            db["analysis_jobs"]
            .find()
            .sort("created", -1)
            .skip((current_page - 1) * page_size)
            .limit(page_size)
        )

        return generate_response(
            {
                "paginationMetadata": {
                    "totalRecords": total_records,
                    "currentPage": current_page,
                    "totalPages": total_pages,
                },
                "analysisJobs": analysis_jobs,
            }
        )

    except Exception as e:
        logging.error(e)
        return jsonify({"errors": [{"message": "Get analysis jobs failed"}]}), 500


@bp.route("/analysis-jobs/<analysis_job_id>", methods=(["GET"]))
@auth_required
def get_analysis_jobs_by_id(_, analysis_job_id):
    try:
        analysis_job = db["analysis_jobs"].find_one({"_id": ObjectId(analysis_job_id)})
        if analysis_job:
            return generate_response(analysis_job)
        else:
            return "Analysis job not found", 404
    except Exception:
        return jsonify({"message": "Get analysis job by ID failed"}), 500


@bp.route("/subscription-push", methods=(["POST"]))
def handle_pubsub_subscription_push():
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        logging.error(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        logging.error(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]

    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        message_string = (
            base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
        )
        message_json = json.loads(message_string)
        stock_symbol = message_json["StockSymbol"]
        target_fear_greed_index = message_json["TargetFearGreedIndex"]
        target_pe_ratio = message_json["TargetPeRatio"]
        job_id = message_json["JobId"]
        logging.info(
            f"Received Pub Sub message with for stock {stock_symbol} with job ID {job_id}; {target_fear_greed_index} and {target_pe_ratio}"
        )

        price_prediction = round(
            predict_price_linear_regression(
                stock_symbol=stock_symbol, data_years_ago=1, prediction_years_future=1
            )[0],
            2,
        )

        try:
            start_time = time.perf_counter()
            data = yf.Ticker(stock_symbol)
            df = data.history(period="1mo")
            stock_info = data.info
            current_price = stock_info["currentPrice"]
            EPS = stock_info["trailingEps"]
            PE_ratio = float("{:.2f}".format(current_price / EPS))
            logging.info(f"{stock_symbol} has PE ratio of {PE_ratio}")
            most_recent_close = df.tail(1)["Close"].values[0]
            logging.info(
                f"Most recent close for stock {stock_symbol} is {most_recent_close}"
            )
            most_recent_fear_greed_index = int(Record.get_most_recent_record()["index"])
            fair_value = generate_stock_fair_value(
                most_recent_close,
                most_recent_fear_greed_index,
                PE_ratio,
                target_fear_greed_index=target_fear_greed_index,
                target_pe_ratio=target_pe_ratio,
            )
            AnalysisJob.update_analysis_job_by_id(
                analysis_job_id=job_id,
                data={
                    "most_recent_fear_greed_index": most_recent_fear_greed_index,
                    "current_pe_ratio": PE_ratio,
                    "target_fear_greed_index": target_fear_greed_index,
                    "target_pe_ratio": target_pe_ratio,
                    "fair_value": fair_value,
                    "delta": return_delta(fair_value, most_recent_close),
                    "price_prediction": price_prediction,
                    "complete": True,
                },
            )
            logging.info(f"Update analysis job for stock {stock_symbol} complete!")
        except Exception as e:
            logging.error(f"Update analysis job failed -  {e}")
        finally:
            end_time = time.perf_counter()
            formatted_time_taken = "{:.2f}".format(round(end_time - start_time, 2))
            logging.info(f"Time taken: {formatted_time_taken}")

    return ("", 204)


@bp.route("/generate-stock-plot", methods=(["POST"]))
@auth_required
def generate_stock_plot_gcs_blob(_):

    base_currency = request.args.get("baseCurrency", default=None, type=None)
    quote_currency = request.args.get("quoteCurrency", default=None, type=None)

    stocks = request.args.get("stocks", default=None, type=None)
    years_ago = request.args.get("years", default=1, type=int)
    secondary_axis = request.args.get(
        "secondaryAxis", default=False, type=value_is_true
    )

    if not isinstance(years_ago, int):
        return jsonify({"message": "Invalid value for years!"}), 400
    if int(years_ago) > 3:
        return jsonify({"message": "Maximum three years!"}), 400

    if base_currency and quote_currency:
        if any(
            i.upper() not in VALID_CURRENCIES for i in [base_currency, quote_currency]
        ):
            raise BadRequestException(
                "Provide a valid currency symbol",
                status_code=400,
            )

        tickers_list = [f"{base_currency}{quote_currency}=X"]
    elif stocks:
        tickers_list = stocks.split(",")
    else:
        raise BadRequestException(
            "Provide a stock ticker symbols in comma separated list",
            status_code=400,
        )

    if len(tickers_list) > 5:
        return jsonify({"message": "Maximum five stocks!"}), 400

    first_stock_ticker = tickers_list[0]

    target_price = request.args.get("targetPrice", default=None, type=None)
    rolling_average_days = request.args.get("rollingAverageDays", default=50, type=int)

    if rolling_average_days and (
        rolling_average_days > 100 or rolling_average_days < 50
    ):
        raise BadRequestException(
            "Rolling average days must be between 50 and 100 inclusive", status_code=400
        )

    try:
        data = yf.download(tickers_list, get_years_ago_formatted(years_ago))["Close"]
        y_label = "Close Price"

        # data.plot(figsize=(10, 6))

        _ = plt.figure(num=1, clear=True, figsize=(10, 6))
        plt.plot(data.index, data[tickers_list], label="Close Price")

        x = data.index

        if len(tickers_list) == 1:

            if secondary_axis:
                data["vol"] = data[first_stock_ticker].pct_change().rolling(
                    window=21
                ).std() * math.sqrt(252)

                ax = data[first_stock_ticker].plot(color="b")
                ax2 = data.vol.plot(secondary_y=True, ax=ax, color="k")

                ax.set_ylabel("Closing Price")
                ax2.set_ylabel("Volatility")

                # Plot the grid lines
                plt.grid(which="major", color="k", linestyle="-.", linewidth=0.5)

                plt.title(f"{first_stock_ticker} Chart", fontsize=16)

                fig_to_upload = plt.gcf()
                cloud_storage_connector = CloudStorageConnector(
                    bucket_name=ASSETS_PLOTS_BUCKET_NAME
                )
                file_name = generate_figure_blob_filename("time-series")
                blob_public_url = cloud_storage_connector.upload_pyplot_figure(
                    fig_to_upload, file_name
                )
                return jsonify({"image_url": blob_public_url}), 200

            data["rolling_avg"] = (
                data[first_stock_ticker].rolling(window=rolling_average_days).mean()
            )
            plt.plot(
                data.index,
                data["rolling_avg"],
                label=f"{rolling_average_days}-Day Rolling Average",
            )
            if target_price:
                plt.axhline(
                    y=float(target_price),
                    color="r",
                    label=f"Target Price: ${target_price}",
                )
            y = data[first_stock_ticker].values.reshape(-1, 1)

            lm = LinearRegression()
            lm.fit(x.values.reshape(-1, 1), y)

            predictions = lm.predict(x.values.astype(float).reshape(-1, 1))
            plt.plot(
                x, predictions, label="Linear fit", linestyle="--", lw=1, color="red"
            )
            plt.legend()
        else:
            plt.legend(tickers_list)

        plt.title(f"{','.join(tickers_list)} Chart", fontsize=16)

        # Define the labels
        plt.ylabel(y_label, fontsize=14)
        plt.xlabel("Time", fontsize=14)

        # Plot the grid lines
        plt.grid(which="major", color="k", linestyle="-.", linewidth=0.5)

        fig_to_upload = plt.gcf()
        cloud_storage_connector = CloudStorageConnector(
            bucket_name=ASSETS_PLOTS_BUCKET_NAME
        )
        file_name = generate_figure_blob_filename("time-series")
        blob_public_url = cloud_storage_connector.upload_pyplot_figure(
            fig_to_upload, file_name
        )
        return jsonify({"image_url": blob_public_url}), 200

    except Exception as e:
        logging.error(e)
        return (
            jsonify({"message": "Generate stock plot failed"}),
            500,
        )


@bp.route("/generate-stocks-cumulative-returns-plot", methods=(["POST"]))
@auth_required
def generate_stock_cumulative_returns_plot_gcs_blob(_):

    data = request.get_json()
    if not data or not data.get("stocks") or not data.get("years"):
        return jsonify({"message": "Missing field"}), 400

    tickers_list = data.get("stocks").split(",")
    years = data.get("years")

    if not isinstance(years, int):
        return jsonify({"message": "Invalid value for years!"}), 400

    if len(tickers_list) > 5:
        return jsonify({"message": "Maximum five stocks!"}), 400

    if len(tickers_list) != len(set(tickers_list)):
        return jsonify({"message": "Duplicated stock symbol!"}), 400

    if int(years) > 3:
        return jsonify({"message": "Maximum three years!"}), 400

    try:
        data = yf.download(tickers_list, get_years_ago_formatted(int(years)))["Close"]

        y_label = "Cumulative Returns"
        ((data.pct_change().fillna(0) + 1).cumprod()).plot(figsize=(10, 7))
        plt.legend()
        plt.title("Stocks Cumulative Returns", fontsize=16)

        # Define the labels
        plt.ylabel(y_label, fontsize=14)
        plt.xlabel("Time", fontsize=14)

        # Plot the grid lines
        plt.grid(which="major", color="k", linestyle="-.", linewidth=0.5)
        fig_to_upload = plt.gcf()
        cloud_storage_connector = CloudStorageConnector(
            bucket_name=ASSETS_PLOTS_BUCKET_NAME
        )
        file_name = generate_figure_blob_filename("time-series")
        blob_public_url = cloud_storage_connector.upload_pyplot_figure(
            fig_to_upload, file_name
        )
        return jsonify({"image_url": blob_public_url}), 200

    except Exception as e:
        logging.error(e)
        return (
            jsonify({"message": "Generate stock cumulative returns plot failed"}),
            500,
        )


@bp.route("/analysis/export-csv", methods=(["POST"]))
def export_stock_analysis_csv():

    stock_symbol = request.args.get("stock", default=None, type=None)

    if not stock_symbol:
        raise BadRequestException("Provide a stock symbol", status_code=400)

    data = yf.Ticker(stock_symbol)
    df = data.history(period="1y")

    response = make_response(df.to_csv())
    response.headers["Content-Disposition"] = (
        f"attachment; filename={datetime.today().strftime(DATETIME_FORMATE_CODE)}.csv"
    )
    response.mimetype = "text/csv"
    return response


async def predict_price_async(stock_symbol: str):
    await asyncio.sleep(5)
    price_prediction = round(
        predict_price_linear_regression(
            stock_symbol=stock_symbol, data_years_ago=1, prediction_years_future=1
        )[0],
        2,
    )
    return price_prediction


@bp.route("/analysis/price-prediction-async", methods=(["POST"]))
async def get_price_prediction_async():

    try:
        price_prediction_request = PricePredictionRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = price_prediction_request.stock
    runs_count = price_prediction_request.runs

    if runs_count < 2:
        task = asyncio.create_task(predict_price_async(stock_symbol))
        result = await task
    else:
        futures = [predict_price_async(stock_symbol) for _ in range(runs_count)]
        results = await asyncio.gather(*futures)

        logging.info(f"Prediction results size: {len(results)}")
        result = round(statistics.mean(results), 2)
    return (
        jsonify(
            {
                "stock": stock_symbol,
                "pricePredictionMean": result,
                "predictionRunCount": runs_count,
            }
        ),
        200,
    )


@bp.route("/generate-stock-mean-close-plot", methods=(["POST"]))
@auth_required
def generate_stock_mean_close_plot_gcs_blob(_):

    try:
        create_stock_plot_request = CreateStockPlotRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = create_stock_plot_request.stock
    years_ago = create_stock_plot_request.years

    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period=f"{years_ago}y")
        monthly_mean_close_df = generate_monthly_mean_close_df(df)

        plt.figure(figsize=(10, 10))

        plt.plot(
            monthly_mean_close_df["Date"],
            monthly_mean_close_df["Monthly Average"],
            label="Monthly Average Close",
        )

        plt.title(f"{stock_symbol.upper()} Monthly Average Close", fontsize=14)
        plt.xlabel("Month", fontsize=12)
        plt.ylabel("Monthly Average Close", fontsize=12)

        plt.xticks(rotation=50, fontsize=10)

        fig_to_upload = plt.gcf()
        cloud_storage_connector = CloudStorageConnector(
            bucket_name=ASSETS_PLOTS_BUCKET_NAME
        )
        file_name = generate_figure_blob_filename("mean-close")
        blob_public_url = cloud_storage_connector.upload_pyplot_figure(
            fig_to_upload, file_name
        )
        return jsonify({"image_url": blob_public_url}), 200

    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Generate stock mean close plot failed"}), 500


@bp.route("/get-monthly-mean-close", methods=(["GET"]))
@auth_required
def get_monthly_mean_close(_):

    record_date = request.args.get("date")
    stock_symbol = request.args.get("stock", default=None, type=None)

    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period="3y")

        if not validate_date_string_for_pandas_df(record_date):
            raise BadRequestException(
                "Invalid date input. Must be in format YYYY-MM-DD", status_code=400
            )

        now = datetime.now()
        days_three_years = 365 * 3
        if (
            now - datetime.strptime(record_date, PANDAS_DF_DATE_FORMATE_CODE)
        ).days > days_three_years:
            three_years_ago = now - relativedelta(days=days_three_years)
            raise BadRequestException(
                f"{record_date} is too far behind! Oldest date is three years ago from current time {three_years_ago.strftime(PANDAS_DF_DATE_FORMATE_CODE)}",
                status_code=400,
            )
        record_date_formatted = datetime.strptime(
            record_date, PANDAS_DF_DATE_FORMATE_CODE
        ).strftime("%b %Y")

        monthly_mean_close_df = generate_monthly_mean_close_df(df)

        month_average_close = monthly_mean_close_df[
            monthly_mean_close_df["Date"] == record_date_formatted
        ]["Monthly Average"].values[0]

        return (
            jsonify(
                {
                    "stock": stock_symbol,
                    "requested_date": record_date,
                    "requested_date_formatted": record_date_formatted,
                    "month_average_close": month_average_close,
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get stock mean close failed"}), 500


@bp.route("/analysis/price-prediction-multiprocess", methods=(["POST"]))
def get_price_prediction_multiprocess():

    try:
        price_prediction_request = PricePredictionRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = price_prediction_request.stock
    runs_count = price_prediction_request.runs

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:

        results = pool.starmap(
            predict_price_linear_regression,
            zip([stock_symbol for _ in range(runs_count)], repeat(1), repeat(1)),
        )
        results_mean = round(statistics.mean([i[0] for i in results]), 2)

    return (
        jsonify(
            {
                "stock": stock_symbol,
                "pricePredictionMean": results_mean,
                "predictionRunCount": runs_count,
            }
        ),
        200,
    )


def predict_price_generator(
    run_count: int, stock_symbol: str, data_years_ago: int, prediction_years_future: int
):
    for _ in range(run_count):
        price_prediction = round(
            predict_price_linear_regression(
                stock_symbol, data_years_ago, prediction_years_future
            )[0],
            2,
        )
        yield price_prediction


@bp.route("/analysis/price-prediction-generator", methods=(["POST"]))
def get_price_prediction_generator():

    try:
        price_prediction_request = PricePredictionRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = price_prediction_request.stock
    runs_count = price_prediction_request.runs

    generator = predict_price_generator(runs_count, stock_symbol, 1, 1)

    results_mean = round(statistics.mean([i for i in generator]), 2)

    return (
        jsonify(
            {
                "stock": stock_symbol,
                "pricePredictionMean": results_mean,
                "predictionRunCount": runs_count,
            }
        ),
        200,
    )


@bp.route("/generate-stock-close-daily-return-plot", methods=(["POST"]))
@auth_required
def generate_stock_close_daily_return_plot_gcs_blob(_):

    try:
        create_stock_plot_request = CreateStockPlotRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = create_stock_plot_request.stock
    years_ago = create_stock_plot_request.years

    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period=f"{years_ago}y")
        df["Daily Return"] = round(df["Close"].pct_change() * 100, 2)
        df["Volatility"] = round(
            df["Daily Return"].rolling(window=21).std() * math.sqrt(252), 2
        )

        df.dropna(subset=["Daily Return"])

        fig, axs = plt.subplots(2, figsize=(10, 8))
        fig.suptitle(f"{stock_symbol} Daily Change")

        axs[0].plot(df.index, df["Daily Return"])
        axs[1].plot(df.index, df["Volatility"])

        axs[1].set_xlabel("Date")

        axs[0].set_ylabel("Close Percentage Change")
        axs[1].set_ylabel("Volatility")

        # Plot the grid lines
        plt.grid(which="major", color="k", linestyle="-.", linewidth=0.5)
        fig.autofmt_xdate()
        fig_to_upload = plt.gcf()
        cloud_storage_connector = CloudStorageConnector(
            bucket_name=ASSETS_PLOTS_BUCKET_NAME
        )
        file_name = generate_figure_blob_filename("close-daily-change")
        blob_public_url = cloud_storage_connector.upload_pyplot_figure(
            fig_to_upload, file_name
        )
        return jsonify({"image_url": blob_public_url}), 200

    except Exception as e:
        logging.error(e)
        return (
            jsonify({"message": "Generate stock close daily return plot failed"}),
            500,
        )


@bp.route("/analyse-currency-impact", methods=(["POST"]))
@auth_required
def analyse_currency_impact_on_return(_):

    try:
        impact_request = AnalyseCurrencyImpactOnReturnRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = impact_request.stock
    years_ago = impact_request.years
    currency = impact_request.currency

    data = get_currency_impact_stock_return_df(stock_symbol, years_ago, currency)

    cumulative_currency_impact = (
        data["Cumulative_Local_Return"].iloc[-1]
        - data["Cumulative_USD_Return"].iloc[-1]
    )

    local_currency_return = float(
        f"{data['Cumulative_Local_Return'].iloc[-1] * 100:.2f}"
    )

    logging.info(f"Cumulative Local Currency Return: {local_currency_return}%")

    cumulative_usd_return = float(f"{data['Cumulative_USD_Return'].iloc[-1] * 100:.2f}")
    logging.info(f"Cumulative USD Return: {cumulative_usd_return}%")

    currency_impact = float(f"{cumulative_currency_impact * 100:.2f}")
    logging.info(f"Currency Impact on Total Return (USD basis): {currency_impact}%")
    return jsonify(
        {
            "localCurrencyReturn": local_currency_return,
            "cumulativeUsdReturn": cumulative_usd_return,
            "currencyImpact": currency_impact,
        }
    )


@bp.route("/generate-currency-impact-plot", methods=(["POST"]))
@auth_required
def generate_currency_impact_on_return_plot(_):

    try:
        impact_request = AnalyseCurrencyImpactOnReturnRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = impact_request.stock
    years_ago = impact_request.years
    currency = impact_request.currency

    data = get_currency_impact_stock_return_df(stock_symbol, years_ago, currency)
    data.dropna()
    data["Cumulative_Local_Return"] = data["Cumulative_Local_Return"] * 100
    data["Cumulative_USD_Return"] = data["Cumulative_USD_Return"] * 100

    plt.figure(figsize=(10, 6))
    plt.plot(
        data.index,
        data[["Cumulative_Local_Return", "Cumulative_USD_Return"]],
        label="Close Price",
    )

    plt.title(f"{currency} currency impact on {stock_symbol} return", fontsize=16)
    plt.legend([f"Cumulative {currency} return", "Cumulative USD return"])
    plt.ylabel("Cumulative return percentage", fontsize=14)
    plt.xlabel("Time", fontsize=14)

    # Plot the grid lines
    plt.grid(which="major", color="k", linestyle="-.", linewidth=0.5)
    fig_to_upload = plt.gcf()
    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )
    file_name = generate_figure_blob_filename("currency-impact-return")
    blob_public_url = cloud_storage_connector.upload_pyplot_figure(
        fig_to_upload, file_name
    )
    return jsonify({"image_url": blob_public_url}), 200


@bp.route("/dividends-analysis", methods=(["GET"]))
@auth_required
def get_stock_dividends_analysis(_):
    stock_symbol = request.args.get("stock", default=None, type=None)
    years_ago = request.args.get("years", default=1, type=int)

    stock_dividends_df = generate_dividend_yield_df(stock_symbol, years_ago)

    latest = stock_dividends_df.iloc[-1]
    ttm_dividend_annual = float(f"{latest['TTM_Dividend']:.2f}")
    ttm_yield = float(f"{latest['TTM_Yield_%']:.2f}")

    logging.info(f"{'TTM Dividend (annual):':<40}{ttm_dividend_annual}$")
    logging.info(f"{'TTM Yield:':<40}{ttm_yield}%")
    return (
        jsonify({"ttm_dividend_annual": ttm_dividend_annual, "ttm_yield": ttm_yield}),
        200,
    )


@bp.route("/generate-stock-dividends-plot", methods=(["POST"]))
@auth_required
def generate_stock_dividends_plot_gcs_blob(_):

    try:
        create_stock_plot_request = CreateStockPlotRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = create_stock_plot_request.stock
    years_ago = create_stock_plot_request.years
    stock_dividends_df = generate_dividend_yield_df(stock_symbol, years_ago)

    plt.figure(figsize=(10, 6))
    plt.plot(
        stock_dividends_df.index,
        stock_dividends_df["TTM_Yield_%"],
        label="TTM Dividend Yield",
        linewidth=2,
    )
    plt.title(f"{stock_symbol.upper()} Dividend Yield History")
    plt.ylabel("Yield (%)")
    plt.xlabel("Date")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    fig_to_upload = plt.gcf()
    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )
    file_name = generate_figure_blob_filename("dividends")
    blob_public_url = cloud_storage_connector.upload_pyplot_figure(
        fig_to_upload, file_name
    )
    return jsonify({"image_url": blob_public_url}), 200


@bp.route("/generate-stock-roi-plot", methods=(["POST"]))
@auth_required
def generate_stock_roi_plot_gcs_blob(_):

    try:
        create_stock_plot_request = CreateStockPlotRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = create_stock_plot_request.stock
    years_ago = create_stock_plot_request.years

    data = yf.Ticker(stock_symbol).history(period=f"{years_ago}y")

    data["Previous_Close"] = data["Close"].shift(1)
    data["Daily_Return"] = (data["Close"] - data["Previous_Close"]) / data[
        "Previous_Close"
    ]

    data["Cumulative_ROI"] = ((1 + data["Daily_Return"]).cumprod() - 1) * 100

    plt.figure(figsize=(10, 6))
    plt.title(f"{stock_symbol} return on investment", fontsize=16)
    plt.ylabel("ROI percentage", fontsize=14)
    plt.xlabel("Time", fontsize=14)
    plt.plot(data.index, data["Cumulative_ROI"])

    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    fig_to_upload = plt.gcf()
    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )
    file_name = generate_figure_blob_filename("roi")
    blob_public_url = cloud_storage_connector.upload_pyplot_figure(
        fig_to_upload, file_name
    )
    return jsonify({"image_url": blob_public_url}), 200


@bp.route("/analysis/price-prediction-heapq", methods=(["POST"]))
def get_price_prediction_heapq():

    try:
        price_prediction_request = PricePredictionRequest.model_validate_json(
            request.data
        )
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = price_prediction_request.stock
    runs_count = price_prediction_request.runs

    min_heap = []

    for _ in range(runs_count):
        price_prediction = round(
            predict_price_linear_regression(stock_symbol, 1, 1)[0],
            2,
        )
        heapq.heappush(min_heap, price_prediction)

    while min_heap:
        logging.info(heapq.heappop(min_heap))

    return "Done!"
