import datetime
import os
from dataclasses import dataclass

import pymongo
import requests

from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor


@dataclass
class TestNewsAPI(SetupMongoDB, DocumentProcessor):
    api_key: str = None

    @property
    def fake_news(self):
        dir_path = "/home/chansoo/projects/tailoredscoop/tailoredscoop/news/fake_news"
        file_contents = []
        for filename in os.listdir(dir_path):
            if filename.endswith(".txt"):
                with open(os.path.join(dir_path, filename), "r") as f:
                    print(filename)
                    article = {
                        "url": f"http://127.0.0.1:8080/static/{filename}",
                        "content": f.read(),
                        "publishedAt": datetime.datetime.now(),
                        "source": "fakenews",
                        "title": "article title",
                        "description": "description",
                        "created_at": datetime.datetime.now(),
                        "author": "fake author",
                    }
                    file_contents.append(article)
        return file_contents

    def get_top_news(
        self, db: pymongo.database.Database, country="us", category=None, page_size=10
    ):
        articles = self.fake_news
        self.download(articles, url_hash="test_url_hash", db=db)
        return list(
            db.articles.find(
                {
                    "query_id": "test_url_hash",
                }
            ).sort("created_at", -1)
        )

    def query_news_by_keywords(
        self, db: pymongo.database.Database, q="Apples", page_size=10
    ):
        articles = self.fake_news
        self.download(articles, url_hash="test_url_hash", db=db)
        return (
            list(
                db.articles.find(
                    {
                        "query_id": "test_url_hash",
                    }
                ).sort("created_at", -1)
            ),
            q,
        )

    def extract_article_content(self, url):
        return requests.get(url).content.decode()

    def download(self, articles, url_hash, db: pymongo.database.Database):
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
                    "query_id": url_hash,
                }
                try:
                    result = db.articles.replace_one({"url": url}, article, upsert=True)
                    if result.modified_count == 0 and result.upserted_id is None:
                        print(f"Article already exists: {url}")
                    else:
                        print(f"Inserted/Updated article with URL: {url}")
                except Exception as e:
                    print(f"Error inserting/updating article: {e}")
