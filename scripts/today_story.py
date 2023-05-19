#!/usr/bin/python
import asyncio
import logging
import multiprocessing
from datetime import datetime

import openai
import pytz
from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from transformers import pipeline

from tailoredscoop import api, config, utils
from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents import summarize

utils.Logger().setup_logger()
logger = logging.getLogger("tailoredscoops.testing")

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

num_cpus = multiprocessing.cpu_count()
logger.info(f"Number of CPUs: {num_cpus}")


# %%
newsapi = api.NewsAPI(api_key=secrets["newsapi"]["api_key"])

mongo_client = SetupMongoDB(mongo_url=secrets["mongodb"]["url"]).setup_mongodb()
db = mongo_client.db1

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
sender = api.EmailSummary(news_downloader=newsapi, db=db, summarizer=summarizer)

articles, kw = asyncio.run(sender.get_articles(email="", news_downloader=newsapi))

# %%
res, urls, encoded_urls = newsapi.process(
    articles[:8], summarizer=summarizer, db=db, email="today_story"
)

# %%
summary = summarize.get_openai_summary({"res": res, "kw": None})

summary_id = sender.summary_hash(kw=None)
sender.upload_summary(
    summary=summary,
    encoded_urls=encoded_urls,
    titles=[article["title"] for article in articles],
    summary_id=summary_id,
    kw=kw,
)

headlines = summarize.get_url_headlines(urls).split("\n")
sources = []
for url, headline in zip(urls, headlines):
    sources.append(f"""- <a href="{url}">{headline}</a>""")

summary += "\n\nSources:\n" + "\n".join(sources)

# %%
user = f"{secrets['mysql']['username']}:{secrets['mysql']['password']}"
host = f"{secrets['mysql']['host']}/{secrets['mysql']['database']}"
engine = create_engine(f"mysql+mysqlconnector://{user}@{host}")

# %%
Base = declarative_base()


class Today(Base):
    __tablename__ = "today"
    id = Column(Integer, primary_key=True)
    content = Column(String(8096), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


# %%
with engine.connect() as connection:
    connection.execute(
        text(
            "ALTER TABLE apps.today  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
    )

# %%
Session = sessionmaker(bind=engine)
session = Session()
new_entry = Today(
    content=summarize.plain_text_to_html(summary, no_head=True),
    timestamp=datetime.now(pytz.utc),
)
session.add(new_entry)
session.commit()
session.close()
# %%
