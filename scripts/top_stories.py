#!/usr/bin/python
# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
from tailoredscoop.news import users
from tailoredscoop import api, config
from tailoredscoop.news.newsapi import NewsAPI
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

newsapi = NewsAPI(
    api_key=secrets["newsapi"]["api_key"]
)

mongodb = SetupMongoDB(
    mongo_url=secrets["mongodb"]["url"]
)
mongo_client = mongodb.setup_mongodb()


sender = api.EmailSummary(
    secrets=secrets,
    news_downloader=newsapi,
    db=mongo_client.db1
)

# %% [markdown]
"""
Send Email
"""

# %%
df_users = users.Users().get(emails=["chansoosong@gmail.com"])
if len(df_users) > 100:
    raise Exception("suspicious, too many users")

# %%
sender.send(subscribed_users=df_users)

# %%
