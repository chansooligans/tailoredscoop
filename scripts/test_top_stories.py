#!/usr/bin/python
from IPython import get_ipython

if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
import asyncio
import datetime
import multiprocessing

import numpy as np
import openai
import pandas as pd
from transformers import pipeline

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

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
sender = api.EmailSummary(news_downloader=newsapi, db=db, summarizer=summarizer)

# %% [markdown]
"""
Send Email
"""


# %%
# already sent
query = {
    "created_at": {
        "$gte": datetime.datetime.combine(
            datetime.date.today(), datetime.datetime.min.time()
        ),
    }
}

sent = list(db.sent.find(query, {"email": 1, "_id": 0}))

# %%
df_users = users.Users().get()

df_users = df_users.loc[
    df_users["email"].isin(["chansoosong01+economy@gmail.com"])
].copy()


if len(df_users) > 100:
    raise Exception("suspicious, too many users")

if sent:
    df_sent = pd.DataFrame(sent)["email"]
    df_users = df_users.loc[~df_users["email"].isin(df_sent)]

# %%
df_list = np.array_split(df_users, max(len(df_users) // 100, 1))

for chunk in df_list:
    asyncio.run(sender.send(subscribed_users=chunk))
