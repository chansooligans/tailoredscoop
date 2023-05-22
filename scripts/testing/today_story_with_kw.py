#!/usr/bin/python
# %%
from IPython import get_ipython

if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
import multiprocessing

import nest_asyncio
import openai
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
db = mongo_client.db1

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
sender = api.EmailSummary(news_downloader=newsapi, db=db, summarizer=summarizer)


# %%
kw = "Economy,world news,sports"
articles, q = await newsapi.query_news_by_keywords(q=kw, db=db)
assert len(articles) > 0

# %%
res, titles, encoded_urls = newsapi.process(
    articles, summarizer=summarizer, db=db, max_articles=8, email="today_story"
)

# %%
summary = sender.openai_summarizer.get_openai_summary({"res": res, "kw": kw})

# %%
sources = []
for url, headline in zip(encoded_urls, titles):
    sources.append(f"""- <a href="{url}">{headline}</a>""")
summary += "\n\nSources:\n" + "\n".join(sources)

# %%
print(summary)
