import asyncio
import datetime
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import aiohttp
import feedparser
import pymongo
from bs4 import BeautifulSoup
from tokenizers import Tokenizer

from tailoredscoop import utils
from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.keywords import get_similar_keywords_from_gpt
from tailoredscoop.documents.process import DocumentProcessor
from tailoredscoop.news.google_news.topics import GOOGLE_TOPICS


class DownloadArticle:
    def __post_init__(self):
        self.logger = logging.getLogger("tailoredscoops.api")

    async def request_with_header(self, url: str, timeout: int = 300) -> str:
        """
        Send a GET request to the given URL with custom headers and return the response text.

        :param url: URL to send the request to.
        :return: Response text from the request.
        """
        # headers = {
        #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        #     "Accept-Language": "en-US,en;q=0.5",
        # }
        headers = {
            "User-Agent": "python-requests/2.20.0",
            "Accept-Language": "en-US,en;q=0.5",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=timeout, allow_redirects=True
                ) as response:
                    return await response.text(), str(response.url)
        except asyncio.TimeoutError:
            (f"Request timed out after {timeout} seconds: {url}")
            raise

    async def extract_article_content(self, url: str) -> Optional[str]:
        """
        Extract the article content from the given URL.

        :param url: URL of the article.
        :return: Extracted content of the article or None if failed.
        """
        ...
        try:
            response, redirect_url = await self.request_with_header(url)
        except Exception:
            self.logger.error(f"request failed: {url}")
            return None, url

        soup = BeautifulSoup(response, "html.parser")
        article_tags = soup.find_all("article")
        if not article_tags:
            article_tags = soup.find_all(class_=lambda x: x and "article" in x)

        if article_tags:
            paragraphs = [
                p for article_tag in article_tags for p in article_tag.find_all("p")
            ]
        else:
            self.logger.error(f"soup parse failed: {redirect_url}")
            return None, url
        content = "\n".join(par.text for par in paragraphs)
        return content, redirect_url

    @staticmethod
    def check_db_for_article(link, db):
        """
        check database if article was already queried
        """
        return db.articles.find_one({"link": link}, {"_id": 0})

    def published_at(self, article):
        return datetime.datetime.strptime(
            article["published"], "%a, %d %b %Y %H:%M:%S %Z"
        )

    def format_articles(self, url, article, article_text, url_hash, rank):
        return {
            "url": url,
            "link": article["link"],
            "published": self.published_at(article),
            "source": article["source"]["title"],
            "title": article["title"],
            "content": article_text,
            "created_at": datetime.datetime.now(),
            "query_id": url_hash,
            "rank": rank,
        }

    async def process_article(
        self,
        article: dict,
        url_hash: str,
        db: pymongo.database.Database,
        rank: int,
    ) -> Optional[dict]:
        """
        Process a single news article and store it in the database.

        :param article: News article data.
        :param url_hash: Hash of the URL used for query_id.
        :param db: MongoDB database instance.
        :return: article is processed successfully, 0 otherwise.
        """

        stored_article = self.check_db_for_article(link=article["link"], db=db)

        if stored_article:
            return stored_article
        else:
            article_text, url = await self.extract_article_content(article["link"])
            if not article_text:
                db.article_download_fails.update_one(
                    {"url": url}, {"$set": {"url": url}}, upsert=True
                )
            else:
                article = self.format_articles(
                    url=url,
                    article=article,
                    article_text=article_text,
                    url_hash=url_hash,
                    rank=rank,
                )
                db.articles.replace_one({"url": url}, article, upsert=True)
                return article


@dataclass
class NewsAPI(SetupMongoDB, DocumentProcessor, DownloadArticle):
    api_key: str
    log: utils.Logger = utils.Logger()

    def __post_init__(self):
        self.now = datetime.datetime.now()
        self.log.setup_logger()
        self.logger = logging.getLogger("tailoredscoops.newsapi")
        self.tokenizer = Tokenizer.from_pretrained("bert-base-uncased")

    async def download(
        self, articles: List[dict], url_hash: str, db: pymongo.database.Database
    ) -> List[int]:
        """
        Download and process the given list of articles.

        :param articles: List of articles.
        :param url_hash: Hash of the URL used for query_id.
        :param db: MongoDB database instance.
        :return: List of processing results (article if success, 0 for failure).
        """
        tasks = []

        for i, article in enumerate(articles):
            tasks.append(
                asyncio.ensure_future(
                    self.process_article(
                        article=article, url_hash=url_hash, db=db, rank=i
                    )
                )
            )

        completed, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        return [task.result() for task in completed]

    async def request_google(
        self, db: pymongo.database.Database, url: str
    ) -> List[dict]:
        """
        Request articles from Google News with the given URL and store them in the database.

        :param db: MongoDB database instance.
        :param url: URL to send the request to.
        :return: List of requested articles.
        """
        url_hash = hashlib.sha256(
            (url + self.now.strftime("%Y-%m-%d")).encode()
        ).hexdigest()
        if db.articles.find_one({"query_id": url_hash}):
            self.logger.info(f"Query already requested: {url_hash}")
            return list(db.articles.find({"query_id": url_hash}).sort("created_at", -1))

        articles = feedparser.parse(url).entries[:15]
        if articles:
            await self.download(articles, url_hash, db)
            return list(db.articles.find({"query_id": url_hash}).sort("created_at", -1))
        else:
            logging.error("no articles")
            return []

    async def query_news_by_keywords(
        self, db: pymongo.database.Database, q: str = "Apples"
    ) -> Tuple[List[dict], str]:
        """
        Query news articles by given keywords.

        :param db: MongoDB database instance.
        :param q: Keywords to query news articles.
        :return: Tuple containing a list of news articles and the used query.
        """
        results = []
        used_q = ""
        for query in q.split(","):
            query = query.lower()
            if query in GOOGLE_TOPICS.keys():
                url = f"""https://news.google.com/rss/topics/{GOOGLE_TOPICS[query]}"""
            else:
                url = f"""https://news.google.com/rss/search?q="{quote(query)}"%20when%3A1d"""

            self.logger.info(f"query for [{query}]; url: {url}")
            articles = await self.request_google(db=db, url=url)
            if len(articles) <= 5:
                new_q = get_similar_keywords_from_gpt(query)
                if len(new_q) == 0:
                    return [], q
                new_query = "OR".join([f'"{x.strip()}"' for x in new_q.split(",")])
                url = f"https://news.google.com/rss/search?q={quote(new_query)}%20when%3A1d"
                self.logger.info(
                    f"alternate query for [{query}]; using {new_q}; url: {url}"
                )
                articles = await self.request_google(db=db, url=url)
                used_q = used_q + ", " + new_q
            else:
                used_q = used_q + query
            results += articles
        return results, q
