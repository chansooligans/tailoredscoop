# %% [markdown]
"""
Delete
"""

# %%
from tailoredscoop import config
secrets = config.setup()
from pymongo import MongoClient
# Connect to MongoDB
client = MongoClient(secrets["mongodb"]["url"])
db = client.db1  # Specify your MongoDB database name
collection = db.email_article_log  # Specify your collection name

# Delete all documents in the collection
result = collection.delete_many({})

# Print the number of deleted documents
print(f"Deleted {result.deleted_count} documents from the collection.")

# Close the MongoDB connection
client.close()

# %%
# %% [markdown]
"""
Delete all
"""

# %%
# %%
from tailoredscoop import config
secrets = config.setup()
from pymongo import MongoClient
# Connect to MongoDB
client = MongoClient(secrets["mongodb"]["url"])
db = client.db1  # Specify your MongoDB database name
for collection in [db.email_article_log, db.articles, db.summaries]:  # Specify your collection name

    # Delete all documents in the collection
    result = collection.delete_many({})

    # Print the number of deleted documents
    print(f"Deleted {result.deleted_count} documents from the collection.")

    # Close the MongoDB connection
client.close()

# %%