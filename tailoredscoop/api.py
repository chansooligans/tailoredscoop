# %%
import asyncio
import datetime
import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import boto3
import pandas as pd
import pymongo
from botocore.exceptions import ClientError
from pymongo.errors import DuplicateKeyError
from transformers import pipeline

from tailoredscoop.documents import summarize
from tailoredscoop.news.newsapi_with_google_kw import NewsAPI

_no_default = object()


@dataclass
class Articles:
    db: pymongo.database.Database
    now: datetime.datetime

    def log_shown_articles(self, email: str, shown_urls: List[str]) -> None:
        """Log the shown articles for the given email."""
        try:
            self.db.email_article_log.update_one(
                {"email": email}, {"$set": {"urls": shown_urls}}, upsert=True
            )
        except Exception as e:
            print(f"Failed to update article log: {e}")

    def check_shown_articles(self, email: str, articles: List[dict]) -> List[dict]:
        """Check if article has been shown and return the articles to be summarized."""
        shown_urls = self.db.email_article_log.find_one({"email": email})
        if shown_urls:
            shown_urls = shown_urls.get("urls", [])
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

    async def get_articles(
        self, email: str, news_downloader: NewsAPI, kw: Optional[str] = None
    ) -> Tuple[List[dict], Optional[str]]:
        """Get the articles for the given email and keyword."""
        if kw:
            articles, kw = await news_downloader.query_news_by_keywords(
                q=kw, db=self.db
            )
        else:
            articles, kw = await news_downloader.query_news_by_keywords(
                q="us,business,entertainment", db=self.db
            )

        return (self.check_shown_articles(email=email, articles=articles), kw)


@dataclass
class Summaries(Articles):
    db: pymongo.database.Database
    summarizer: pipeline
    now: datetime.datetime

    def upload_summary(
        self,
        summary: str,
        encoded_urls: List[str],
        titles: List[str],
        summary_id: str,
        kw: str,
    ) -> None:
        """Upload the summary to the database."""
        try:
            summary_data = {
                "created_at": self.now,
                "summary_id": summary_id,
                "summary": summary,
                "titles": titles,
                "encoded_urls": encoded_urls,
                "kw": kw,
            }

            filter_query = {"summary_id": summary_id}

            update_query = {"$set": summary_data}

            self.db.summaries.update_one(filter_query, update_query, upsert=True)
            print(f"Inserted summary: {summary_id}")
        except DuplicateKeyError:
            print(f"Summary with URL already exists: {summary_id}")

    def summary_hash(self, kw: Optional[str]) -> str:
        """Generate a hash for the summary based on the keyword and current date."""
        if kw is not None:
            return hashlib.sha256(
                (kw + self.now.strftime("%Y-%m-%d")).encode()
            ).hexdigest()
        else:
            return hashlib.sha256((self.now.strftime("%Y-%m-%d")).encode()).hexdigest()

    def summary_error(self, summary: str) -> bool:
        """Check if the summary is an error message."""
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

    def format_summary(self, saved_summary: dict, email: str) -> str:
        """Format the saved summary with additional information and links."""

        summary = saved_summary["summary"]
        titles = saved_summary["titles"]
        encoded_urls = saved_summary["encoded_urls"]

        if self.summary_error(summary):
            print("summary is null")
            return

        sources = []
        for encoded_url, title in zip(encoded_urls, titles):
            sources.append(f"""- <a href="{encoded_url}">{title}</a>""")

        summary += "\n\nSources:\n" + "\n".join(sources)
        summary += (
            """\n\n<a href="https://tailoredscoops.com/tailoredscoop">Home</a> | """
        )

        hashed_email = hashlib.sha256(email.encode("utf-8")).hexdigest()
        summary += f"""<a href="https://tailoredscoops.com/tailoredscoop/unsubscribe/{hashed_email}">Unsubscribe</a>"""

        return summary

    async def create_summary(
        self,
        email: str,
        news_downloader: NewsAPI,
        summary_id: str,
        kw: Optional[str] = None,
    ) -> dict:
        """Create a summary for the given email using the news downloader and summarizer."""

        articles, topic = await self.get_articles(
            email=email, news_downloader=news_downloader, kw=kw
        )
        articles = articles[:8]

        if len(articles) == 0:
            return {"summary": None, "urls": None}

        res, urls, encoded_urls = news_downloader.process(
            articles, summarizer=self.summarizer, db=self.db, email=email
        )

        loop = asyncio.get_running_loop()
        summary = await loop.run_in_executor(
            None, summarize.get_openai_summary, {"res": res, "kw": topic}
        )

        self.upload_summary(
            summary=summary,
            encoded_urls=encoded_urls,
            titles=[article["title"] for article in articles],
            summary_id=summary_id,
            kw=kw,
        )

        return {
            "summary": summary,
            "titles": [article["title"] for article in articles],
            "encoded_urls": encoded_urls,
        }

    async def get_summary(self, email: str, kw: Optional[str] = None) -> str:
        """Get the summary for the given email and keyword."""

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

        return self.format_summary(summary, email), summary_id


@dataclass
class EmailSummary(Summaries):
    news_downloader: NewsAPI = _no_default
    db: pymongo.database.Database = _no_default
    summarizer: pipeline = _no_default
    now: datetime.datetime = datetime.datetime.now()

    def cleanup(self, text: str) -> str:
        """Remove square brackets and their contents from the given text."""
        text = re.sub(r"\[.*?\]", "", text)
        return text

    async def send_email(
        self, to_email: str, plain_text_content: str, summary_id: str
    ) -> None:
        """Send an email with newsletter to the specified email address."""
        loop = asyncio.get_running_loop()
        abridged = summarize.abridge_summary(
            plain_text_content, summarizer=self.summarizer
        )
        subject = await loop.run_in_executor(None, summarize.get_subject, abridged)
        html_content = self.cleanup(summarize.plain_text_to_html(plain_text_content))
        client = boto3.client("ses", region_name="us-east-1")
        try:
            # Provide the contents of the email.
            client.send_email(
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
        except ClientError as e:
            print(e.response["Error"]["Message"])
        else:
            self.db.sent.insert_one(
                {
                    "email": to_email,
                    "created_at": datetime.datetime.now(),
                    "summary_id": summary_id,
                }
            )
            print("Email sent! ", to_email)

    async def send_one(self, email: str, kw: str, test: bool) -> None:
        try:
            summary, summary_id = await self.get_summary(email=email, kw=kw)

            if not summary:
                error_msg = f"""We couldn't find any matches for "<b>{kw}</b>" today. Don't worry, though! Here are some exciting general headlines for you to enjoy:\n\n"""
                summary, summary_id = await self.get_summary(email=email)
                if not summary:
                    return
                else:
                    summary = error_msg + summary

            await self.send_email(
                to_email=email, plain_text_content=summary, summary_id=summary_id
            )
        except Exception as e:
            print(e)
            return

    async def send(self, subscribed_users: pd.DataFrame, test: bool = False) -> None:
        """Send emails to subscribed users"""

        tasks = []
        for _, email, kw, _ in subscribed_users.values:
            print(email)
            tasks.append(
                asyncio.create_task(self.send_one(email=email, kw=kw, test=test))
            )

        await asyncio.gather(*tasks)

        print("emails delivered")
