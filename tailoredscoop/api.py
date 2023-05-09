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
import pymongo
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import re
from typing import List, Optional


from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor
from tailoredscoop.documents import summarize
from tailoredscoop.documents import keywords
from tailoredscoop.news.newsapi import NewsAPI

@dataclass
class Articles:
    db:pymongo.database.Database

    def __post_init__(self):
        self.now = datetime.datetime.now()

    def log_shown_articles(self, email, shown_urls):
        try:
            self.db.email_article_log.update_one(
                {"email": email},
                {"$set": {"urls": shown_urls}},
                upsert=True
            )
        except Exception as e:
            print(f"Failed to update article log: {e}")

    def check_shown_articles(self, email, articles):
        shown_urls = self.db.email_article_log.find_one({"email": email})
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

        self.log_shown_articles(email=email, shown_urls=shown_urls)

        return articles_to_summarize

    def get_articles(self, email, news_downloader:NewsAPI, kw:str=None):
        if kw:
            articles = news_downloader.query_news_by_keywords(q=kw, db=self.db)
            if len(articles) <= 5:
                topic = keywords.get_topic(kw)
                articles = articles + news_downloader.get_top_news(category=topic, page_size=10-len(articles), db=self.db)
        else:
            articles = news_downloader.get_top_news(db=self.db)

        return self.check_shown_articles(email=email, articles=articles)

@dataclass
class Summaries(Articles):
    db:pymongo.database.Database

    def __post_init__(self):
        self.now = datetime.datetime.now()
    
    def upload_summary(self, summary, urls, summary_id):
        try:
            self.db.summaries.insert_one({
                "created_at":self.now,
                "summary_id":summary_id,
                "summary":summary,
                "urls":urls
            })
            print(f"Inserted summary: {summary_id}")
        except DuplicateKeyError:
            print(f"Summary with URL already exists: {summary_id}")
        
    def create_summary(self, email, news_downloader:NewsAPI, summary_id, kw=None):
        
        articles = self.get_articles(email=email, news_downloader=news_downloader, kw=kw)
        articles = articles[:10]

        if len(articles) == 0:
            return {"summary":None, "urls":None}
        
        res, urls = news_downloader.process(
            articles, 
            summarizer=summarize.summarizer, 
            db=self.db
        )

        summary = summarize.get_openai_summary(res, kw=kw)
    
        self.upload_summary(summary=summary, urls=urls,summary_id=summary_id)

        return {"summary":summary, "urls":urls}
    
    def summary_hash(self, kw):
        if kw != "":
            return hashlib.sha256((kw + self.now.strftime("%Y-%m-%d")).encode()).hexdigest()
        else:
            return hashlib.sha256((self.now.strftime("%Y-%m-%d")).encode()).hexdigest()
        
    def format_summary(self, saved_summary, email):
        summary = saved_summary["summary"]
        urls = saved_summary["urls"]

        if not summary:
            print('summary is null')
            return
        
        # original sources, HOME | Unsubscribe
        summary += '\n\nOriginal Sources:\n- ' + "\n- ".join(urls)
        summary += f'\n\n[Home](https://apps.chansoos.com/tailoredscoop) | '
        summary += f'[Unsubscribe](https://apps.chansoos.com/tailoredscoop/unsubscribe/{email})'

        return summary

    def get_summary(self, email:str, kw:Optional[List[str]]=None):

        summary_id = self.summary_hash(kw=kw)
        summary = self.db.summaries.find_one({
            "summary_id": summary_id
        })

        if summary:
            print('used cached summary')
        else:
            summary = self.create_summary(
                email=email, 
                news_downloader=self.news_downloader, 
                summary_id=summary_id, 
                kw=kw
            )
        
        return self.format_summary(summary, email)


@dataclass
class EmailSummary(Summaries):
    secrets: dict
    news_downloader: NewsAPI
    db:pymongo.database.Database

    def __post_init__(self):
        self.now = datetime.datetime.now()
    
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
            sg.send(message)
            print("Email sent successfully.")
        except Exception as e:
            print(f"Error sending email: {str(e)}")

    
    def plain_text_to_html(self, text):
        text = text.replace("\n", "<br>")
        
        def link_replacer(match):
            link_text = match.group(1)
            link_url = match.group(2)
            return f'<a href="{link_url}" style="color: #a8a8a8;">{link_text}</a>'
        
        html = re.sub(r'\[(.*?)\]\((.*?)\)', link_replacer, text)
        return f'<html><head></head><body><p>{html}</p></body></html>'

    def send_one(self, email, kw, test):
        
        summary = self.get_summary(email=email, kw=kw)

        if not summary:
            return
        
        if test:
            print(summary)
        else:
            self.send_email(
                to_email=email,
                subject=f"Today's Scoops: {summarize.get_subject(summary)}",
                plain_text_content=summary,
                html_content=self.plain_text_to_html(summary),
                api_key = self.secrets["sendgrid"]["api_key"]
            )

    def send(self, subscribed_users, test=False, *args, **options):
    
        # Send emails to subscribed users
        for _, email, kw in subscribed_users.values:
            print(email)
            self.send_one(email=email, kw=kw, test=test)
            
        print('Successfully sent daily newsletter')
