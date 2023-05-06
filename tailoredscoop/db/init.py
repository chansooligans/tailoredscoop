from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

class SetupMongoDB:

    def __init__(self, mongo_url):
        self.mongo_url = mongo_url

    def setup_mongodb(self):
        self.client = MongoClient(self.mongo_url)
        self.client.db1.articles.create_index('url', unique=True)
        return self.client
    
    def delete_all(self, collection):
        collection.delete_many({})