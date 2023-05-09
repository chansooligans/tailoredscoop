import requests
import hashlib
import datetime
from functools import cached_property
from bs4 import BeautifulSoup
from dataclasses import dataclass
import pymongo
import feedparser

from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor
from tailoredscoop.documents.keywords import get_similar_keywords_from_gpt

@dataclass
class NewsAPI(SetupMongoDB, DocumentProcessor):
    api_key: str

    def __post_init__(self):
        self.now = datetime.datetime.now()
        time_24_hours_ago = self.now - datetime.timedelta(days=1)
        self.time_24_hours_ago = time_24_hours_ago.isoformat()
        
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
           
    def download(self, articles, url_hash, db:pymongo.database.Database):
        
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
                    "query_id": url_hash
                }
                try:
                    result = db.articles.replace_one({"url": url}, article, upsert=True)
                    if result.modified_count == 0 and result.upserted_id is None:
                        print(f"Article already exists: {url}")
                    else:
                        print(f"Inserted/Updated article with URL: {url}")
                    success+=1
                except Exception as e:
                    print(f"Error inserting/updating article: {e}")
            if success > 10:
                break

    def request(self, db:pymongo.database.Database, url):
        url_hash = hashlib.sha256((url + self.now.strftime("%Y-%m-%d %H")).encode()).hexdigest()
        if db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return list(db.articles.find({"query_id": url_hash}))

        print("GET: ", url)
        response = requests.get(url)

        if response.status_code == 200:
            articles = response.json()
            self.download(articles["articles"], url_hash, db=db)
            return list(db.articles.find({"query_id": url_hash}))
        else:
            print(f"Error: {response.status_code}")
            return None
        
    def true_url(self, url):
        response = requests.get(url)
        return response.url
        
    def reformat_google(self, article):
        published_at = datetime.datetime.strptime(article["published"], '%a, %d %b %Y %H:%M:%S %Z')

        try: 
            true_url = self.true_url(article["link"])
        except Exception as e:
            print(e)
            print("cannot get true url")
            true_url = article["link"]

        return {
            "url":true_url,
            "content":None,
            "publishedAt":published_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "source":article["source"]["title"],
            "title": article["title"],
            "description": None,
            "author": None,
        }

    def request_google(self, db:pymongo.database.Database, url):
        url_hash = hashlib.sha256((url + self.now.strftime("%Y-%m-%d %H")).encode()).hexdigest()
        if db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return list(db.articles.find({"query_id": url_hash}))

        try:
            articles = [
                self.reformat_google(article)
                for article in feedparser.parse(url).entries
            ]
            
            self.download(articles, url_hash, db=db)
            return list(db.articles.find({"query_id": url_hash}))
        except Exception as e:
            print(f"Error with google rss: {url}")
            print(e)
            return None

    def get_top_news(self, db:pymongo.database.Database, country="us", category=None, page_size=10):
        if category:
            url = f"https://newsapi.org/v2/top-headlines?country={country}&category={category}&pageSize={page_size}&apiKey={self.api_key}"
        else:
            url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={page_size}&apiKey={self.api_key}"
        return self.request(db=db, url=url)
        
    def query_news_by_keywords(self, db:pymongo.database.Database, q="Apples", page_size=10):
        query = '%20OR%20'.join([x.strip().replace(' ','%20') for x in q.split(",")])
        url = f'https://news.google.com/rss/search?q={query}%20when%3A1d'
        articles = self.request_google(db=db, url=url)
        if not articles:
            new_q = get_similar_keywords_from_gpt(q)
            query = '%20OR%20'.join([x.strip().replace(' ','%20') for x in new_q.split(",")])
            url = f'https://news.google.com/rss/search?q={query}%20when%3A1d'
            articles = self.request_google(db=db, url=url)
        return articles
        
    
    
    