from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

class SetupMongoDB:

    def setup_mongodb(self):
        self.client = MongoClient()
        self.client.db1.articles.create_index('url', unique=True)
        return self.client
    
    def delete_all(self, collection):
        collection.delete_many({})