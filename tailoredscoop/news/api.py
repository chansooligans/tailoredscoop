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

    def save_summary(self, news_downloader, date, hash, kw=None):
        if kw:
            articles = news_downloader.query_news_by_topic(kw)
        else:
            articles = news_downloader.get_top_news()
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

        if len(subscribed_users) > 1000:
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
                summary = self.save_summary(news_downloader, now, summary_hash, kw=keywords)

            self.send_email(
                to_email="chansoosong@gmail.com",
                subject="Today's Tailored Scoop",
                plain_text_content=summary,
                api_key = self.secrets["sendgrid"]["api_key"]
            )

        print('Successfully sent daily newsletter')
