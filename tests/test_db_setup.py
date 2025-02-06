from api.db.setup import mongo_client
from pymongo import MongoClient


def test_mongo_client():
    client = mongo_client()
    assert type(client) is MongoClient
