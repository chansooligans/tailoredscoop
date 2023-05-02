# %% [markdown]
"""
Query 
"""

# %%
from pymongo import MongoClient

# Connect to MongoDB
db = MongoClient()
col = db["db1"]["articles"]

# Perform a query to check if articles exist
query = {}  # Empty query to retrieve all documents
articles = col.find(query)

count = col.count_documents({})
if count > 0:
    print("Articles found in the collection:")
    for article in articles:
        print(article["content"])
else:
    print("No articles found in the collection")

# Close the MongoDB connection
db.close()


# %%

# %% [markdown]
"""
Delete
"""
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
