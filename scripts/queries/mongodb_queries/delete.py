# %% [markdown]
"""
Delete all
"""

# %%
from pymongo import MongoClient

from tailoredscoop import config

secrets = config.setup()

# Connect to MongoDB
client = MongoClient(secrets["mongodb"]["url"])
db = client.db  # Specify your MongoDB database name
for collection in [
    db.email_article_log,
    db.articles,
    db.summaries,
    db.article_download_fails,
]:  # Specify your collection name

    # Delete all documents in the collection
    result = collection.delete_many({})

    # Print the number of deleted documents
    print(f"Deleted {result.deleted_count} documents from the collection.")

    # Close the MongoDB connection
client.close()


# %%
