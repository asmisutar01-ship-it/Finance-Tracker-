import os
from pymongo import MongoClient

db = None

def init_db(app):
    global db
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/financetrack")
    client = MongoClient(mongo_uri)
    db = client['financetrack']
    
def get_db():
    return db
