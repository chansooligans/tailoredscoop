# %%
import requests
import yaml
from pathlib import Path
import os
import hashlib
import datetime
from functools import cached_property
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from sqlalchemy import create_engine
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor
from tailoredscoop.documents import summarize
from tailoredscoop.documents import keywords

@dataclass
class NewsAPI(SetupMongoDB, DocumentProcessor):
    api_key: str

    def __post_init__(self):
        self.mongo_client = self.setup_mongodb()
        self.db = self.mongo_client.db1  # Specify your MongoDB database name

        now = datetime.datetime.now()
        time_48_hours_ago = now - datetime.timedelta(days=2)
        self.time_48_hours_ago = time_48_hours_ago.isoformat()

    def get_top_news(self, country="us", category=None, page_size=10):
        if category:
            url = f"https://newsapi.org/v2/top-headlines?country={country}&category={category}&pageSize={page_size}&apiKey={self.api_key}"
        else:
            url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={page_size}&apiKey={self.api_key}"
        now = datetime.datetime.now()
        url_hash = hashlib.sha256((url + now.strftime("%Y-%m-%d %H")).encode()).hexdigest()

        if self.db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return list(self.db.articles.find({"query_id": url_hash}))

        print("GET: ", url)
        response = requests.get(url)

        if response.status_code == 200:
            articles = response.json()
            self.download(articles["articles"], url_hash)
            return list(self.db.articles.find({"query_id": url_hash}))
        else:
            print(f"Error: {response.status_code}")
            return None
        
    def query_news_by_keywords(self, q="Apples", page_size=10):
        query = '" OR "'.join(q.split(","))
        url = (
            f'https://newsapi.org/v2/everything?q="{query}"&pageSize={page_size}&from={self.time_48_hours_ago}&apiKey={self.api_key}'
        )
        
        now = datetime.datetime.now()
        url_hash = hashlib.sha256((url + now.strftime("%Y-%m-%d %H")).encode()).hexdigest()

        if self.db.articles.find_one({"query_id": url_hash}):
            print(f"Query already requested: {url_hash}")
            return list(self.db.articles.find({"query_id": url_hash}))
        
        print("GET: ", url)
        response = requests.get(url)

        if response.status_code == 200:
            articles = response.json()
            self.download(articles["articles"], url_hash)
            return list(self.db.articles.find({"query_id": url_hash}))
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
                    result = self.db.articles.replace_one({"url": url}, article, upsert=True)
                    if result.modified_count == 0 and result.upserted_id is None:
                        print(f"Article already exists: {url}")
                    else:
                        print(f"Inserted/Updated article with URL: {url}")
                except Exception as e:
                    print(f"Error inserting/updating article: {e}")



@dataclass
class EmailSummary:
    secrets: dict

    @cached_property
    def engine(self):
        user = self.secrets['mysql']['username']
        password = self.secrets['mysql']['password']
        host = self.secrets['mysql']['host']
        database = self.secrets['mysql']['database']
        return create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{database}')
    
    def send_email(self, to_email, subject, plain_text_content, api_key, html_content=None):
        message = Mail(
            from_email="chansoosong@gmail.com",
            to_emails=to_email,
            subject=subject,
            plain_text_content=plain_text_content,
            html_content=html_content
        )

        try:
            sg = SendGridAPIClient(api_key)
            response = sg.send(message)
            print("Email sent successfully.")
        except Exception as e:
            print(f"Error sending email: {str(e)}")

    def get_articles(self, email, news_downloader, kw=None):
        if kw:
            articles = news_downloader.query_news_by_keywords(kw)
            topic = keywords.get_topic(kw)
            articles = articles + news_downloader.get_top_news(category=topic)
        else:
            articles = news_downloader.get_top_news()

        shown_urls = news_downloader.db.email_article_log.find_one({"email": email})
        if isinstance(shown_urls, dict):
            shown_urls = shown_urls.get("urls", [])
            if not shown_urls:
                shown_urls = []
        else:
            shown_urls = []
        
        articles_to_summarize = []
        for article in articles:
            url = article.get("url")
            if url not in shown_urls:
                articles_to_summarize.append(article)
                shown_urls.append(url)
        
        try:
            news_downloader.db.email_article_log.update_one(
                {"email": email},
                {"$set": {"urls": shown_urls}},
                upsert=True
            )
        except Exception as e:
            print(f"Failed to update article log: {e}")

        return articles_to_summarize

    def save_summary(self, email, news_downloader, date, hash, kw=None):
        
        articles = self.get_articles(email, news_downloader, kw)
        articles = articles[:10]

        if len(articles) == 0:
            return
        
        res = news_downloader.process(articles, summarizer=summarize.summarizer)
        
        summary = summarize.get_openai_summary(res)

        summary_obj = {
            "created_at":date,
            "summary_id":hash,
            "summary":summary
        }
        try:
            news_downloader.db.summaries.insert_one(summary_obj)
            print(f"Inserted summary: {hash}")
        except DuplicateKeyError:
            print(f"Summary with URL already exists: {hash}")
        return summary

        
    def send(self, *args, **options):
        
        news_downloader = NewsAPI(api_key=self.secrets["newsapi"]["api_key"])

        # Fetch all subscribed users from the database
        query = 'SELECT * FROM tailorscoop_newslettersubscription'
        subscribed_users = pd.read_sql_query(query, self.engine)

        now = datetime.datetime.now()

        if len(subscribed_users) > 100:
            raise Exception("suspicious, too many users")
    
        # Send emails to subscribed users
        for _, email, keywords in subscribed_users.values:
            print(email)
            
            if keywords != "":
                summary_hash = hashlib.sha256((keywords + now.strftime("%Y-%m-%d %H")).encode()).hexdigest()
            else:
                summary_hash = hashlib.sha256((now.strftime("%Y-%m-%d %H")).encode()).hexdigest()
                
            if news_downloader.db.summaries.find_one({"summary_id": summary_hash}):
                print('used cached summary')
                summary = news_downloader.db.summaries.find_one({"summary_id": summary_hash})["summary"]
            else:
                summary = self.save_summary(email, news_downloader, now, summary_hash, kw=keywords)

            if not summary:
                print('summary is null')
                continue

            self.send_email(
                to_email=email,
                subject="Today's Tailored Scoop",
                plain_text_content=summary,
                api_key = self.secrets["sendgrid"]["api_key"]
            )

        print('Successfully sent daily newsletter')
