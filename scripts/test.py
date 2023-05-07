from tailoredscoop.news import api
from tailoredscoop import config
from tailoredscoop.documents import summarize
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
import openai
from datetime import datetime

print('abc')

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

from pymongo import MongoClient

print('123')

# Connect to MongoDB
db = MongoClient(secrets["mongodb"]["url"])
col = db["db1"]["articles"]
db.close()

print('hello')

sender = api.EmailSummary(secrets=secrets)

print('a')

news_downloader = api.NewsAPI(
    api_key=secrets["newsapi"]["api_key"],
    mongo_url=secrets["mongodb"]["url"]
)

print('b')

articles = news_downloader.get_top_news(category="general")

print('c')

print(len(articles))

