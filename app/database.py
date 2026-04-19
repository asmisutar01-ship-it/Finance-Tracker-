import os
import logging
from pymongo import MongoClient

client = None
db = None

def get_db():
    global client, db

    if db is not None:
        return db

    if client is None:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise Exception("MONGO_URI not set")

        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

        try:
            client.admin.command("ping")
        except Exception as e:
            logging.error(f"MongoDB connection failed: {e}")
            raise Exception(f"Mongo connection failed: {e}")

    db = client["financetrack"]
    return db
