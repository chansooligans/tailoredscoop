# %%
from IPython import get_ipython

if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
import multiprocessing
import re

import nest_asyncio
import openai
import tqdm
import utils as du
from transformers import pipeline

from tailoredscoop import api, config
from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents import summarize
from tailoredscoop.news import newsapi_with_google_kw

nest_asyncio.apply()

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]


num_cpus = multiprocessing.cpu_count()
print("Number of CPUs: ", num_cpus)

# %%
newsapi = newsapi_with_google_kw.NewsAPI(api_key=secrets["newsapi"]["api_key"])

mongo_client = SetupMongoDB(mongo_url=secrets["mongodb"]["url"]).setup_mongodb()
db = mongo_client.db_test

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
sender = api.EmailSummary(news_downloader=newsapi, db=db, summarizer=summarizer)


# %% [markdown]
"""
Testing
"""


# %%
res_list = []
responses = []
kwlist = ["economy"]
for kw in tqdm.tqdm(kwlist):
    articles, kw = await sender.get_articles(
        email="chansoosong01@gmail.com", news_downloader=newsapi, kw=kw
    )
    if len(articles) == 0:
        continue
    res, titles, encoded_urls = newsapi.process(
        articles,
        summarizer=summarizer,
        max_articles=8,
        db=db,
        email="chansoosong01@gmail.com",
    )
    res_list.append(res)
    messages = du.get_messages(res=res, kw=kw)
    num_tokens = du.get_tokens(messages)
    response = openai.ChatCompletion().create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.2,
        max_tokens=4096 - num_tokens,
    )

    responses.append(response)

# %%
for response in responses:
    content = response["choices"][0]["message"]["content"]
    print(len(content.split()))

# %%

for response in responses:
    content = response["choices"][0]["message"]["content"]
    print(content)


# %%
