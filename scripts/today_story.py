#!/usr/bin/python
from tailoredscoop.news import api
from tailoredscoop import config
from tailoredscoop.documents import summarize
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
import openai
from datetime import datetime

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

import multiprocessing
num_cpus = multiprocessing.cpu_count()
print("Number of CPUs: ", num_cpus)

# %%
sender = api.EmailSummary(secrets=secrets)
news_downloader = api.NewsAPI(
    api_key=secrets["newsapi"]["api_key"],
    mongo_url=secrets["mongodb"]["url"]
)
articles = news_downloader.get_top_news(category="general")
assert  len(articles) > 0
    
res = news_downloader.process(articles[:10], summarizer=summarize.summarizer)

# %%
summary = summarize.get_openai_summary(res)
urls = list(res.keys())

summary += '\n\nSources:\n- ' + "\n- ".join(urls)

# %%
user = secrets['mysql']['username']
password = secrets['mysql']['password']
host = secrets['mysql']['host']
database = secrets['mysql']['database']
engine = create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{database}?charset=utf8mb4')

# %%
Base = declarative_base()
class Today(Base):
    __tablename__ = 'today'
    id = Column(Integer, primary_key=True)
    content = Column(String(8096), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    __table_args__ = {
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci'
    }

# %%
with engine.connect() as connection:
    connection.execute(text("ALTER TABLE apps.today  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))

# %%
Session = sessionmaker(bind=engine)
session = Session()
new_entry = Today(content=summary, timestamp=datetime.now())
session.add(new_entry)
session.commit()
session.close()

# %%
# import pandas as pd
# pd.read_sql("SELECT * FROM today order by timestamp desc", con=engine)["content"][0]
