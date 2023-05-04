# %% [markdown]
"""
Delete
"""

# %%
from pymongo import MongoClient
# Connect to MongoDB
client = MongoClient()
db = client.db1  # Specify your MongoDB database name
collection = db.articles  # Specify your collection name

# Delete all documents in the collection
result = collection.delete_many({})

# Print the number of deleted documents
print(f"Deleted {result.deleted_count} documents from the collection.")

# Close the MongoDB connection
client.close()

# %%
