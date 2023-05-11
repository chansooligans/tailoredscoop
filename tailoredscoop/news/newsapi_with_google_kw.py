import datetime
import hashlib
from dataclasses import dataclass
from functools import cached_property
from urllib.parse import quote

import feedparser
import pymongo
import requests
from bs4 import BeautifulSoup

from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.keywords import get_similar_keywords_from_gpt
from tailoredscoop.documents.process import DocumentProcessor


@dataclass
class NewsAPI(SetupMongoDB, DocumentProcessor):
    api_key: str

    def __post_init__(self):
        self.now = datetime.datetime.now()
        time_24_hours_ago = self.now - datetime.timedelta(days=1)
        self.time_24_hours_ago = time_24_hours_ago.isoformat()

    def request_with_header(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.5",
        }
        try:
            response = requests.get(url, headers=headers, timeout=5)
            # Process the response here
            return response
        except requests.exceptions.Timeout:
            # Handle the timeout here
            print(f"Request timed out after 5 seconds: {url}")
            raise requests.exceptions.Timeout

    def extract_article_content(self, url):

        try:
            response = self.request_with_header(url)
        except Exception:
            print(f"extract_article_content request failed: {url}")
            return None

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            article_tags = soup.find_all("article")
            if not article_tags:
                article_tags = soup.find_all(class_=lambda x: x and "article" in x)

            if article_tags:
                paragraphs = [
                    p for article_tag in article_tags for p in article_tag.find_all("p")
                ]
            else:
                print(f"extract_article_content soup parse failed: {url}")
                return None
            content = "\n".join(par.text for par in paragraphs)
            return content
        else:
            print(f"Error: {response.status_code}; {url}")
            return None

    def download(self, articles, url_hash, db: pymongo.database.Database):
        success = 0
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
                    "created_at": datetime.datetime.now(),
                    "query_id": url_hash,
                }
                try:
                    db.articles.replace_one({"url": url}, article, upsert=True)
                    success += 1
                except Exception as e:
                    print(f"Error inserting/updating article: {e}")
            else:
                db.article_download_fails.update_one(
                    {"url": url}, {"$set": {"url": url}}, upsert=True
                )
            if success > 8:
                break

    def request(self, db: pymongo.database.Database, url):
        url_hash = hashlib.sha256(
            (url + self.now.strftime("%Y-%m-%d %H")).encode()
        ).hexdigest()
        if db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return list(db.articles.find({"query_id": url_hash}).sort("created_at", -1))

        response = self.request_with_header(url)

        if response.status_code == 200:
            articles = response.json()
            self.download(articles["articles"], url_hash, db=db)
            return list(db.articles.find({"query_id": url_hash}).sort("created_at", -1))
        else:
            print(f"Error: {response.status_code}")
            return None

    def true_url(self, url):
        response = requests.get(url, timeout=5)
        return response.url

    def reformat_google(self, article):
        published_at = datetime.datetime.strptime(
            article["published"], "%a, %d %b %Y %H:%M:%S %Z"
        )

        try:
            true_url = self.true_url(article["link"])
        except Exception as e:
            print(e)
            print("cannot get true url")
            true_url = article["link"]

        return {
            "url": true_url,
            "content": None,
            "publishedAt": published_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": article["source"]["title"],
            "title": article["title"],
            "description": None,
            "author": None,
        }

    def request_google(self, db: pymongo.database.Database, url):
        url_hash = hashlib.sha256(
            (url + self.now.strftime("%Y-%m-%d %H")).encode()
        ).hexdigest()
        if db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return list(db.articles.find({"query_id": url_hash}).sort("created_at", -1))

        try:
            articles = feedparser.parse(url).entries[:10]
        except Exception as e:
            print(f"Error with google rss: {url}")
            print(e)
            return []

        articles = [self.reformat_google(article) for article in articles]

        self.download(articles, url_hash, db=db)
        return list(db.articles.find({"query_id": url_hash}).sort("created_at", -1))

    def get_top_news(
        self, db: pymongo.database.Database, country="us", category=None, page_size=10
    ):
        if category:
            url = f"https://newsapi.org/v2/top-headlines?country={country}&category={category}&pageSize={page_size}&apiKey={self.api_key}"
        else:
            url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={page_size}&apiKey={self.api_key}"
        print("query url: ", url)
        return self.request(db=db, url=url)

    def query_news_by_keywords(
        self, db: pymongo.database.Database, q="Apples", page_size=10
    ):
        results = []
        for query in q.split(","):
            url = f"https://news.google.com/rss/search?q={quote(query)}%20when%3A1d"
            print("query url: ", url)
            articles = self.request_google(db=db, url=url)
            if len(articles) <= 5:
                new_q = get_similar_keywords_from_gpt(q)
                if len(new_q) == 0:
                    return [], q
                query = "%20OR%20".join(
                    [x.strip().replace(" ", "%20") for x in new_q.split(",")]
                )
                url = f"https://news.google.com/rss/search?q={query}%20when%3A1d"
                print("query url: ", url)
                articles = self.request_google(db=db, url=url)
                q = q + ", " + new_q
            results += articles
        return articles, q
