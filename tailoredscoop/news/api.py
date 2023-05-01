# %%
import requests
import yaml
from pathlib import Path
import os
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from tailoredscoop.db.init import SetupMongoDB

@dataclass
class NewsAPI(SetupMongoDB):
    api_key: str

    def __post_init__(self):
        self.mongo_client = self.setup_mongodb()

    def get_top_news(self, country="us", category="general", page_size=10):
        url = f"https://newsapi.org/v2/top-headlines?country={country}&category={category}&pageSize={page_size}&apiKey={self.api_key}"
        print(url)
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None
        
    def query_news_by_topic(self, q="Apples", page_size=10):
        url = (
            f"https://newsapi.org/v2/everything?q={q}&pageSize={page_size}&apiKey={self.api_key}"
        )
        print(url)
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()
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
        
    def download(self, articles):
        db = self.mongo_client.db1  # Specify your MongoDB database name
        
        for i, news_article in enumerate(articles):
            url = news_article["url"]
            article_text = self.extract_article_content(url)
            if article_text:
                article = {
                    "url": url,
                    "content": article_text
                }
                try:
                    db.articles.insert_one(article)
                    print(f"Inserted article with URL: {url}")
                except DuplicateKeyError:
                    print(f"Article with URL already exists: {url}")




# %%


