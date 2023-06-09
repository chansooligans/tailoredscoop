# %%
import asyncio
import datetime
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import boto3
import pandas as pd
import pymongo
from botocore.exceptions import ClientError
from pymongo.errors import DuplicateKeyError
from transformers import pipeline

from tailoredscoop import utils
from tailoredscoop.documents.summarize import OpenaiSummarizer
from tailoredscoop.news.newsapi_with_google_kw import NewsAPI
from tailoredscoop.openai_api import ChatCompletion

_no_default = object()


@dataclass
class Articles:
    db: pymongo.database.Database
    now: datetime.datetime

    def __post_init__(self):
        self.logger = logging.getLogger("tailoredscoops.api")

    def log_shown_articles(self, email: str, shown_urls: List[str]) -> None:
        """Log the shown articles for the given email."""
        try:
            self.db.email_article_log.update_one(
                {"email": email}, {"$set": {"urls": shown_urls}}, upsert=True
            )
        except Exception as e:
            self.logger.error(f"Failed to update article log: {e}")

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
            articles = await news_downloader.query_news_by_keywords(q=kw, db=self.db)
        else:
            articles = await news_downloader.query_news_by_keywords(
                q="us,business", db=self.db
            )

        # sort by rank
        articles = sorted(articles, key=lambda x: x["rank"])

        # return (self.check_shown_articles(email=email, articles=articles), kw)
        return articles


@dataclass
class Summaries(Articles):
    db: pymongo.database.Database
    summarizer: pipeline
    now: datetime.datetime
    openai_summarizer: OpenaiSummarizer

    def __post_init__(self):
        self.logger = logging.getLogger("tailoredscoops.api")

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
            self.logger.info(f"Inserted summary: {summary_id}")
        except DuplicateKeyError:
            self.logger.error(f"Summary with URL already exists: {summary_id}")

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
            self.logger.error(f"summary is null for {email}")
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
    ) -> Dict[str, Union[str, List[str], None]]:
        """Create a summary for the given email using the news downloader and summarizer."""

        articles = await self.get_articles(
            email=email, news_downloader=news_downloader, kw=kw
        )

        if len(articles) <= 4:
            self.logger.error(f"not enough articles | {email} | {kw}")
            return {"summary": None, "titles": None, "encoded_urls": None}

        res, titles, encoded_urls = news_downloader.process(
            articles,
            summarizer=self.summarizer,
            max_articles=8,
            db=self.db,
            email=email,
        )

        if len(res) <= 4:
            self.logger.error(f"not enough processed | {email} | {kw}")
            return {"summary": None, "titles": None, "encoded_urls": None}

        loop = asyncio.get_running_loop()
        summary = await loop.run_in_executor(
            None, self.openai_summarizer.get_openai_summary, {"res": res}
        )

        self.upload_summary(
            summary=summary,
            encoded_urls=encoded_urls,
            titles=titles,
            summary_id=summary_id,
            kw=kw,
        )

        return {
            "summary": summary,
            "titles": titles,
            "encoded_urls": encoded_urls,
        }

    async def get_summary(self, email: str, kw: Optional[str] = None) -> str:
        """Get the summary for the given email and keyword."""

        summary_id = self.summary_hash(kw=kw)
        summary = self.db.summaries.find_one({"summary_id": summary_id})

        if summary:
            self.logger.info("used cached summary")
        else:
            summary = await self.create_summary(
                email=email,
                news_downloader=self.news_downloader,
                summary_id=summary_id,
                kw=kw,
            )

        return self.format_summary(summary, email), summary_id


@dataclass
class Subjects:
    db: pymongo.database.Database
    now: datetime.datetime
    summarizer: pipeline
    openai_summarizer: OpenaiSummarizer

    def __post_init__(self):
        self.logger = logging.getLogger("tailoredscoops.api")

    def check_exists(self, summary_id):
        return self.db.subjects.find_one({"summary_id": summary_id})

    def add_subject(self, summary_id, subject):
        summary_data = {
            "created_at": self.now,
            "summary_id": summary_id,
            "subject": subject,
        }

        filter_query = {"summary_id": summary_id}

        update_query = {"$set": summary_data}

        self.db.subjects.update_one(filter_query, update_query, upsert=True)
        self.logger.info(f"Inserted subject: {summary_id}")

    def abridge_summary(self, summary, summarizer):
        return summarizer(
            summary,
            truncation="only_first",
            min_length=100,
            max_length=140,
            length_penalty=2,
            early_stopping=True,
            num_beams=1,
            # no_repeat_ngram_size=3,
        )[0]["summary_text"]

    async def get_subject(self, plain_text_content, summary_id):
        loop = asyncio.get_running_loop()
        subject = self.check_exists(summary_id)
        if subject:
            return subject["subject"]
        else:
            abridged = self.abridge_summary(
                plain_text_content, summarizer=self.summarizer
            )
            subject = await loop.run_in_executor(
                None, self.openai_summarizer.get_subject, abridged
            )
            self.add_subject(summary_id, subject)
            return subject


@dataclass
class EmailSummary(Summaries, Subjects):
    news_downloader: NewsAPI = _no_default
    db: pymongo.database.Database = _no_default
    summarizer: pipeline = _no_default
    now: datetime.datetime = datetime.datetime.now()
    log: utils.Logger = utils.Logger()
    openai_summarizer: OpenaiSummarizer = OpenaiSummarizer(openai_api=ChatCompletion())

    def __post_init__(self):
        self.log.setup_logger()
        self.logger = logging.getLogger("tailoredscoops.api")

    def cleanup(self, text: str) -> str:
        """Remove square brackets and their contents from the given text."""
        text = re.sub(r"\[.*?\]", "", text)
        return text

    def plain_text_to_html(self, text, no_head=False):
        text = text.replace("\n", "<br>")

        def link_replacer(match):
            link_text = match.group(1)
            link_url = match.group(2)
            return f'<a href="{link_url}" style="color: #a8a8a8;">{link_text}</a>'

        html = re.sub(r"\[(.*?)\]\((.*?)\)", link_replacer, text)

        if no_head:
            return f"<p>{html}</p>"
        else:
            return f"<html><head></head><body><p>{html}</p></body></html>"

    async def send_email(
        self, to_email: str, plain_text_content: str, summary_id: str
    ) -> None:
        """Send an email with newsletter to the specified email address."""
        subject = await self.get_subject(
            plain_text_content=plain_text_content, summary_id=summary_id
        )
        html_content = self.cleanup(self.plain_text_to_html(plain_text_content))
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
                        "Data": subject,
                    },
                },
                Source="Tailored Scoop <apps.tailoredscoop@gmail.com>",
            )
        except ClientError as e:
            self.logger.error(f"""{e.response["Error"]["Message"]} | {to_email}""")
        else:
            self.db.sent.insert_one(
                {
                    "email": to_email,
                    "created_at": datetime.datetime.now(),
                    "summary_id": summary_id,
                }
            )
            self.logger.info(f"Email sent! {to_email}")

    async def send_one(self, email: str, kw: str, test: bool) -> None:
        try:
            summary, summary_id = await self.get_summary(email=email, kw=kw)

            if not summary:
                self.logger.error(f"no summary for email:{email} | kw:{kw}")
                self.db.no_summary_emails.insert_one(
                    {
                        "email": email,
                        "kw": kw,
                        "created_at": datetime.datetime.now(),
                    }
                )
                return

            await self.send_email(
                to_email=email, plain_text_content=summary, summary_id=summary_id
            )
        except Exception as e:
            self.logger.error(f"{email} | {e}")
            return

    async def send(self, subscribed_users: pd.DataFrame, test: bool = False) -> None:
        """Send emails to subscribed users"""

        tasks = []
        for _, email, kw, _ in subscribed_users.values:
            self.logger.info(email)
            tasks.append(
                asyncio.create_task(self.send_one(email=email, kw=kw, test=test))
            )

        await asyncio.gather(*tasks)
