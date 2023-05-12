# %%
import asyncio
import datetime
import hashlib
import os
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import List, Optional

import boto3
import pandas as pd
import pymongo
import requests
import yaml
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents import keywords, summarize
from tailoredscoop.documents.process import DocumentProcessor
from tailoredscoop.news.newsapi import NewsAPI


@dataclass
class Articles:
    db: pymongo.database.Database

    def __post_init__(self):
        self.now = datetime.datetime.now()

    def log_shown_articles(self, email, shown_urls):
        try:
            self.db.email_article_log.update_one(
                {"email": email}, {"$set": {"urls": shown_urls}}, upsert=True
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

    def get_articles(self, email, news_downloader: NewsAPI, kw: str = None):
        if kw:
            articles, kw = news_downloader.query_news_by_keywords(q=kw, db=self.db)
        else:
            articles = news_downloader.get_top_news(db=self.db)

        return (self.check_shown_articles(email=email, articles=articles), kw)


@dataclass
class Summaries(Articles):
    db: pymongo.database.Database

    def __post_init__(self):
        self.now = datetime.datetime.now()

    def upload_summary(self, summary, urls, summary_id):
        try:
            self.db.summaries.insert_one(
                {
                    "created_at": self.now,
                    "summary_id": summary_id,
                    "summary": summary,
                    "urls": urls,
                }
            )
            print(f"Inserted summary: {summary_id}")
        except DuplicateKeyError:
            print(f"Summary with URL already exists: {summary_id}")

    def summary_hash(self, kw):
        if kw is not None:
            return hashlib.sha256(
                (kw + self.now.strftime("%Y-%m-%d")).encode()
            ).hexdigest()
        else:
            return hashlib.sha256((self.now.strftime("%Y-%m-%d")).encode()).hexdigest()

    def summary_error(self, summary):
        if not summary:
            return True
        summary = summary.split(":")[-1].strip().lower()
        if (
            ("as an ai" in summary[:30])
            or ("sorry" in summary[:15])
            or ("unfortunately" in summary[:15])
            or ("none" in summary[:5])
            or ("there are no news stories related to" in summary)
        ):
            return True
        return False

    def format_summary(self, saved_summary, email):

        summary = saved_summary["summary"]
        urls = saved_summary["urls"]

        if self.summary_error(summary):
            print("summary is null")
            return

        # original sources, HOME | Unsubscribe
        sources = summarize.convert_urls_to_links(urls)
        summary += "\n\nSources:\n" + sources
        summary += "\n\n[Home](https://apps.chansoos.com/tailoredscoop) | "

        hashed_email = hashlib.sha256(email.encode("utf-8")).hexdigest()
        summary += f"[Unsubscribe](https://apps.chansoos.com/tailoredscoop/unsubscribe/{hashed_email})"

        return summary

    async def create_summary(
        self, email, news_downloader: NewsAPI, summary_id, kw=None
    ):

        print(datetime.datetime.now(), "create_summary")

        articles, topic = self.get_articles(
            email=email, news_downloader=news_downloader, kw=kw
        )
        articles = articles[:8]

        if len(articles) == 0:
            return {"summary": None, "urls": None}

        res, urls = news_downloader.process(
            articles, summarizer=summarize.summarizer, db=self.db
        )

        loop = asyncio.get_running_loop()
        summary = await loop.run_in_executor(
            None, summarize.get_openai_summary, {"res": res, "kw": topic}
        )

        self.upload_summary(summary=summary, urls=urls, summary_id=summary_id)

        return {"summary": summary, "urls": urls}

    async def get_summary(self, email: str, kw: Optional[List[str]] = None):

        summary_id = self.summary_hash(kw=kw)
        summary = self.db.summaries.find_one({"summary_id": summary_id})

        if summary:
            print("used cached summary")
        else:
            summary = await self.create_summary(
                email=email,
                news_downloader=self.news_downloader,
                summary_id=summary_id,
                kw=kw,
            )

        return self.format_summary(summary, email)


@dataclass
class EmailSummary(Summaries):
    secrets: dict
    news_downloader: NewsAPI
    db: pymongo.database.Database

    def __post_init__(self):
        self.now = datetime.datetime.now()

    async def send_email(self, to_email, plain_text_content):
        loop = asyncio.get_running_loop()
        abridged = summarize.abridge_summary(plain_text_content)
        subject = await loop.run_in_executor(None, summarize.get_subject, abridged)

        html_content = self.cleanup(summarize.plain_text_to_html(plain_text_content))

        print(datetime.datetime.now(), "send_email")
        client = boto3.client("ses", region_name="us-east-1")
        try:
            # Provide the contents of the email.
            response = client.send_email(
                Destination={
                    "ToAddresses": [
                        to_email,
                    ],
                },
                Message={
                    "Body": {
                        "Html": {
                            "Charset": "UTF-8",
                            "Data": html_content,
                        },
                        "Text": {
                            "Charset": "UTF-8",
                            "Data": plain_text_content,
                        },
                    },
                    "Subject": {
                        "Charset": "UTF-8",
                        "Data": f"Today's Scoops: {subject}",
                    },
                },
                Source="Tailored Scoop <apps.tailoredscoop@gmail.com>",
            )
        # Display an error if something goes wrong.
        except ClientError as e:
            print(e.response["Error"]["Message"])
        else:
            self.db.sent.insert_one(
                {"email": to_email, "created_at": datetime.datetime.now()}
            )
            print("Email sent! Message ID:", response["MessageId"]),

    def cleanup(self, text):
        text = re.sub(r"\[.*?\]", "", text)
        return text

    async def send_one(self, email, kw, test):

        try:
            summary = await self.get_summary(email=email, kw=kw)

            if not summary:
                error_msg = f"""We couldn't find any matches for "<b>{kw}</b>" today. Don't worry, though! Here are some exciting general headlines for you to enjoy:\n\n"""
                summary = await self.get_summary(email=email)
                if not summary:
                    return
                else:
                    summary = error_msg + summary

            if test:
                print(summary)
            else:
                await self.send_email(
                    to_email=email,
                    plain_text_content=summary,
                )
        except Exception as e:
            print(e)
            return

    async def send(self, subscribed_users, test=False, *args, **options):

        print(datetime.datetime.now(), "start batch")

        tasks = []
        # Send emails to subscribed users
        for _, email, kw, _ in subscribed_users.values:
            print(email)
            tasks.append(
                asyncio.create_task(self.send_one(email=email, kw=kw, test=test))
            )

        await asyncio.gather(*tasks)

        print(datetime.datetime.now(), "end batch")
