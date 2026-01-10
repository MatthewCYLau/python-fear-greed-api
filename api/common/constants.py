import os
import json

DATETIME_FORMATE_CODE = "%d-%m-%Y"
ANALYSIS_JOB_CREATION_DAILY_LIMIT = 5
PANDAS_DF_DATE_FORMATE_CODE = "%Y-%m-%d"
DEFAULT_TARGET_PE_RATIO = 25
VALID_CURRENCIES = {"USD", "GBP", "EUR", "JPY", "CAD", "AUD", "HKD"}
SNP_TICKER = "^GSPC"
DJI_TICKER = "^DJI"
NASDAQ_TICKET = "^IXIC"

with open(
    os.path.dirname(os.path.dirname(__file__)) + "/config/gcp_config.json"
) as gcp_config_json:
    gcp_config = json.load(gcp_config_json)
GCP_PROJECT_ID = gcp_config["GCP_PROJECT_ID"]
PUB_SUB_TOPIC = gcp_config["PUB_SUB_TOPIC"]
PUB_SUB_ORDERS_TOPIC = gcp_config["PUB_SUB_ORDERS_TOPIC"]
PUB_SUB_TRADES_TOPIC = gcp_config["PUB_SUB_TRADES_TOPIC"]
ASSETS_PLOTS_BUCKET_NAME = gcp_config["ASSETS_PLOTS_BUCKET_NAME"]
ASSETS_UPLOADS_BUCKET_NAME = gcp_config["ASSETS_UPLOADS_BUCKET_NAME"]

TOPIC_NAME = f"projects/{GCP_PROJECT_ID}/topics/{PUB_SUB_TOPIC}"
ORDERS_TOPIC_NAME = f"projects/{GCP_PROJECT_ID}/topics/{PUB_SUB_ORDERS_TOPIC}"
TRADES_TOPIC_NAME = f"projects/{GCP_PROJECT_ID}/topics/{PUB_SUB_TRADES_TOPIC}"
CHART_LABELS = ["Extreme greed", "Greed", "Neutral", "Fear", "Extreme fear"]

BIGQUERY_DATASET_ID = gcp_config["BIGQUERY_DATASET_ID"]
BIGQUERY_TABLE_ID = gcp_config["BIGQUERY_TABLE_ID"]
