#!/usr/bin/python
from IPython import get_ipython

if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
import multiprocessing

import openai

from tailoredscoop import api, config
from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.news import base, newsapi_with_google_kw, users

# %% [markdown]
"""
Configuration
"""

# %%
num_cpus = multiprocessing.cpu_count()
print("Number of CPUs: ", num_cpus)

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

newsapi = newsapi_with_google_kw.NewsAPI(api_key=secrets["newsapi"]["api_key"])

mongo_client = SetupMongoDB(mongo_url=secrets["mongodb"]["url"]).setup_mongodb()
db = mongo_client.db1

sender = api.EmailSummary(secrets=secrets, news_downloader=newsapi, db=db)

# %% [markdown]
"""
Send Email
"""

# %%
df_users = users.Users().get(["chansoosong01+fail@gmail.com"])
if len(df_users) > 100:
    raise Exception("suspicious, too many users")

# %%
sender.send(subscribed_users=df_users)


# %%
