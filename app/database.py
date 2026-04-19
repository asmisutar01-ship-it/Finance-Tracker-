import os
import logging
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

db = None

def init_db(app):
    global db
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/financetrack")
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Attempt to get server info to force connection attempt
        client.server_info()
        db = client['financetrack']
        logging.info("MongoDB connected successfully.")
    except ServerSelectionTimeoutError as err:
        logging.error(f"MongoDB connection failed: {err}")
        db = None
    except Exception as e:
        logging.error(f"An error occurred while connecting to MongoDB: {e}")
        db = None
    
def get_db():
    if db is None:
        raise Exception("Database connection is not initialized.")
    return db
