#!/usr/bin/python
# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
from tailoredscoop import api, config
from tailoredscoop.news import users, base
from tailoredscoop.db.init import SetupMongoDB
import openai
import multiprocessing

# %% [markdown]
"""
Configuration
"""

# %%
num_cpus = multiprocessing.cpu_count()
print("Number of CPUs: ", num_cpus)

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

newsapi = base.TestNewsAPI(
    api_key=secrets["newsapi"]["api_key"]
)

mongo_client = SetupMongoDB(
    mongo_url=secrets["mongodb"]["url"]
).setup_mongodb()
db = mongo_client.db_test

sender = api.EmailSummary(
    secrets=secrets,
    news_downloader=newsapi,
    db=db
)

# %% [markdown]
"""
Send Email
"""

# %%
df_users = users.Users().get(emails=["chansoosong01@gmail.com"])
if len(df_users) > 100:
    raise Exception("suspicious, too many users")

# %%
sender.send(subscribed_users=df_users)

# %%
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
db = client.db_test  # Specify your MongoDB database name
for collection in [db.email_article_log, db.articles, db.summaries]:  # Specify your collection name

    # Delete all documents in the collection
    result = collection.delete_many({})

    # Print the number of deleted documents
    print(f"Deleted {result.deleted_count} documents from the collection.")

    # Close the MongoDB connection
client.close()

# %%
