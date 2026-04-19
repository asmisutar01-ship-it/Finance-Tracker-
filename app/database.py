import os
import logging
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from flask import current_app

def init_db(app=None):
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/financetrack")
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.server_info()  # force connection

        db = client['financetrack']

        # ✅ IMPORTANT: attach db to app
        if app is not None:
            app.db = db

        logging.info("MongoDB connected successfully.")
        return db

    except ServerSelectionTimeoutError as err:
        logging.error(f"MongoDB connection failed: {err}")
        return None
    except Exception as e:
        logging.error(f"An error occurred while connecting to MongoDB: {e}")
        return None


def get_db():
    db = getattr(current_app, 'db', None)
    if db is None:
        raise Exception("Database connection is not initialized.")
    return db
