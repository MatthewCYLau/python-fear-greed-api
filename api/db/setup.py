import os
import logging
import certifi
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

def mongo_client():
    mongodb_url = os.environ.get("MONGO_DB_CONNECTION_STRING")
    client = MongoClient(mongodb_url, tlsCAFile=certifi.where())
    return client

def shutdown():
    raise RuntimeError("Shut down server")

def db_connect():
    try:
        client = mongo_client()
        client.admin.command("ismaster")
        logging.info("Connected to database")
    except ConnectionFailure as e:
        logging.error(f"Failed to connect to database - {e}")
        shutdown()

client = mongo_client()
db = client["python-fear-greed-scraper"]
