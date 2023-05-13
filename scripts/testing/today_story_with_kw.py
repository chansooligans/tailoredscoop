#!/usr/bin/python
# %%
from IPython import get_ipython

if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
import multiprocessing
from datetime import datetime

import openai
from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from tailoredscoop import api, config
from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents import summarize
from tailoredscoop.news import newsapi_with_google_kw, users

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]


num_cpus = multiprocessing.cpu_count()
print("Number of CPUs: ", num_cpus)

# %%
newsapi = newsapi_with_google_kw.NewsAPI(api_key=secrets["newsapi"]["api_key"])

mongo_client = SetupMongoDB(mongo_url=secrets["mongodb"]["url"]).setup_mongodb()
db = mongo_client.db1

kw = "taylor swift"
sender = api.EmailSummary(secrets=secrets, news_downloader=newsapi, db=db)
articles, q = newsapi.query_news_by_keywords(q=kw, db=db)
assert len(articles) > 0
# articles = newsapi.get_top_news(db=db)

res, urls = newsapi.process(articles[:8], summarizer=summarize.summarizer, db=db)

# %%
summary = summarize.get_openai_summary({"res": res, "kw": kw})

# %%
headlines = summarize.get_url_headlines(urls).split("\n")
sources = []
for url, headline in zip(urls, headlines):
    sources.append(f"""- <a href="{url}">{headline}</a>""")
summary += "\n\nSources:\n" + "\n".join(sources)

# %%
print(summary)
