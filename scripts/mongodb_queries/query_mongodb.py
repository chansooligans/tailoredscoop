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
articles = [x for x in articles]
# Close the MongoDB connection
db.close()


# %% [markdown]
"""
# email article
"""

# %%
db = MongoClient()
email="chansoosong@gmail.com"
shown_urls = db.db1.email_article_log.find_one({"email": email})
shown_urls

shown_urls = db.db1.email_article_log.find_one({"email": email})
shown_urls = shown_urls.get("urls")

# %% [markdown]
"""
# summaries
"""
# %%
import pandas as pd
db = MongoClient()
check = pd.DataFrame([x for x in db.db1.summaries.find({})]).sort_values('created_at')
print(check.loc[2, "summary"])
# %%
from bson.objectid import ObjectId
db.db1.summaries.delete_one({"_id": ObjectId("6453088dbe3dc0d6516925da")})
# %%
