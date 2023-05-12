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

print(summary)


# %%
sources = summarize.convert_urls_to_links(urls)
summary += "\n\nSources:\n" + sources

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
    timestamp=datetime.now(),
)
session.add(new_entry)
session.commit()
session.close()


# %%
