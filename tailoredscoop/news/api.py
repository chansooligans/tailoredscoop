# %%
import requests
import yaml
from pathlib import Path
import os
import hashlib
import datetime
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor

@dataclass
class NewsAPI(SetupMongoDB, DocumentProcessor):
    api_key: str

    def __post_init__(self):
        self.mongo_client = self.setup_mongodb()
        self.db = self.mongo_client.db1  # Specify your MongoDB database name

    def get_top_news(self, country="us", category="general", page_size=10):
        url = f"https://newsapi.org/v2/top-headlines?country={country}&category={category}&pageSize={page_size}&apiKey={self.api_key}"
        now = datetime.datetime.now()
        url_hash = hashlib.sha256((url + now.strftime("%Y-%m-%d %H")).encode()).hexdigest()

        if self.db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return self.db.articles.find({"query_id": url_hash})

        response = requests.get(url)

        if response.status_code == 200:
            articles = response.json()
            self.download(articles["articles"], url_hash)
            return self.db.articles.find({"query_id": url_hash})
        else:
            print(f"Error: {response.status_code}")
            return None
        
    def query_news_by_topic(self, q="Apples", page_size=10):
        url = (
            f"https://newsapi.org/v2/everything?q={q}&pageSize={page_size}&apiKey={self.api_key}"
        )
        
        now = datetime.datetime.now()
        url_hash = hashlib.sha256((url + now.strftime("%Y-%m-%d %H")).encode()).hexdigest()

        if self.db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return self.db.articles.find({"query_id": url_hash})
        
        response = requests.get(url)

        if response.status_code == 200:
            articles = response.json()
            self.download(articles["articles"], url_hash)
            return self.db.articles.find({"query_id": url_hash})
        else:
            print(f"Error: {response.status_code}")
            return None
    
    def extract_article_content(self, url):
        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            article_tag = soup.find("article")

            if article_tag:
                paragraphs = article_tag.find_all("p")
            else:
                article_tag = soup.find("div", class_="article-content")
                if article_tag:
                    paragraphs = article_tag.find_all("p")
                else:
                    return None

            content = "\n".join(par.text for par in paragraphs)
            return content
        else:
            print(f"Error: {response.status_code}")
            return None
        
    def download(self, articles, url_hash):
        
        
        for i, news_article in enumerate(articles):
            url = news_article["url"]
            article_text = self.extract_article_content(url)
            if article_text:
                article = {
                    "url": url,
                    "publishedAt": news_article["publishedAt"],
                    "source": news_article["source"],
                    "title": news_article["title"],
                    "description": news_article["description"],
                    "author": news_article["author"],
                    "content": article_text,
                    "query_id": url_hash
                }
                try:
                    self.db.articles.insert_one(article)
                    print(f"Inserted article with URL: {url}")
                except DuplicateKeyError:
                    print(f"Article with URL already exists: {url}")




# %%


