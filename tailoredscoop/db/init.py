from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

class SetupMongoDB:

    def setup_mongodb(self):
        # Connect to MongoDB
        client = MongoClient()
        db = client.db1  # Specify your MongoDB database name
        collection = db.articles  # Specify your collection name

        # Create a unique index on the 'url' field
        collection.create_index("url", unique=True)
        return client
    