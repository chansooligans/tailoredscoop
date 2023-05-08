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


from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor
from tailoredscoop.documents import summarize
from tailoredscoop.documents import keywords
from tailoredscoop.news.newsapi import NewsAPI

@dataclass
class Summaries:

    def get_articles(self, email, news_downloader:NewsAPI, db:pymongo.database.Database, kw:str=None):
        if kw:
            articles = news_downloader.query_news_by_keywords(kw, db=db)
            if len(articles) <= 5:
                topic = keywords.get_topic(kw)
                articles = articles + news_downloader.get_top_news(category=topic, page_size=10-len(articles), db=db)
        else:
            articles = news_downloader.get_top_news(db=db)

        shown_urls = db.email_article_log.find_one({"email": email})
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
            db.email_article_log.update_one(
                {"email": email},
                {"$set": {"urls": shown_urls}},
                upsert=True
            )
        except Exception as e:
            print(f"Failed to update article log: {e}")

        return articles_to_summarize

    def save_summary(self, email, news_downloader:NewsAPI, db:pymongo.database.Database, date, hash, kw=None):
        
        articles = self.get_articles(email=email, news_downloader=news_downloader, db=db, kw=kw)
        articles = articles[:10]

        if len(articles) == 0:
            return {"summary":None, "urls":None}
        
        res = news_downloader.process(articles, summarizer=summarize.summarizer, db=db)
        
        summary = summarize.get_openai_summary(res)

        summary_obj = {
            "created_at":date,
            "summary_id":hash,
            "summary":summary,
            "urls":list(res.keys())
        }
        try:
            db.summaries.insert_one(summary_obj)
            print(f"Inserted summary: {hash}")
        except DuplicateKeyError:
            print(f"Summary with URL already exists: {hash}")
        return {"summary":summary, "urls":list(res.keys())}



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
            response = sg.send(message)
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

        
    def send(self, subscribed_users, *args, **options):
    
        # Send emails to subscribed users
        for _, email, keywords in subscribed_users.values:
            
            print(email)
            
            if keywords != "":
                summary_hash = hashlib.sha256((keywords + self.now.strftime("%Y-%m-%d")).encode()).hexdigest()
            else:
                summary_hash = hashlib.sha256((self.now.strftime("%Y-%m-%d")).encode()).hexdigest()
                
            saved_summary = self.db.summaries.find_one({"summary_id": summary_hash})
            if saved_summary:
                print('used cached summary')
            else:
                saved_summary = self.save_summary(
                    email=email, 
                    news_downloader=self.news_downloader, 
                    db=self.db,
                    date=self.now, 
                    hash=summary_hash, 
                    kw=keywords
                )
            
            summary = saved_summary["summary"]
            urls = saved_summary["urls"]

            if not summary:
                print('summary is null')
                continue
            
            # original sources
            summary += '\n\nOriginal Sources:\n- ' + "\n- ".join(urls)
            # unsubscribe option
            summary += f'\n\n[Home](https://apps.chansoos.com/tailoredscoop) | [Unsubscribe](https://apps.chansoos.com/tailoredscoop/unsubscribe/{email})'

            self.send_email(
                to_email=email,
                subject=f"Today's Scoops: {summarize.get_subject(summary)}",
                plain_text_content=summary,
                html_content=self.plain_text_to_html(summary),
                api_key = self.secrets["sendgrid"]["api_key"]
            )

        print('Successfully sent daily newsletter')
