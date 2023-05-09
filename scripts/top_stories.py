#!/usr/bin/python
from tailoredscoop import api, config
from tailoredscoop.news import users, newsapi_with_google_kw, base
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

newsapi = newsapi_with_google_kw.NewsAPI(
    api_key=secrets["newsapi"]["api_key"]
)

mongo_client = SetupMongoDB(
    mongo_url=secrets["mongodb"]["url"]
).setup_mongodb()
db = mongo_client.db1

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
df_users = users.Users().get()
if len(df_users) > 100:
    raise Exception("suspicious, too many users")

# %%
sender.send(subscribed_users=df_users)
