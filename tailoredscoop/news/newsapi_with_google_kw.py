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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.5",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    return await response.text()
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
            response = await self.request_with_header(url)
        except Exception:
            self.logger.error(f"request failed: {url}")
            return None

        soup = BeautifulSoup(response, "html.parser")
        article_tags = soup.find_all("article")
        if not article_tags:
            article_tags = soup.find_all(class_=lambda x: x and "article" in x)

        if article_tags:
            paragraphs = [
                p for article_tag in article_tags for p in article_tag.find_all("p")
            ]
        else:
            self.logger.error(f"soup parse failed: {url}")
            return None
        content = "\n".join(par.text for par in paragraphs)
        return content

    @staticmethod
    def check_db_for_article(url, db):
        """
        check database if article was already queried
        """
        return list(db.articles.find({"url": url}).sort("publishedAt", -1))

    async def process_article(
        self,
        news_article: dict,
        url_hash: str,
        db: pymongo.database.Database,
        rank: int,
    ) -> int:
        """
        Process a single news article and store it in the database.

        :param news_article: News article data.
        :param url_hash: Hash of the URL used for query_id.
        :param db: MongoDB database instance.
        :return: article is processed successfully, 0 otherwise.
        """
        url = news_article["url"]
        article_check = self.check_db_for_article(url=url, db=db)

        if not article_check:
            article_text = await self.extract_article_content(url)
        else:
            article_text = article_check[0]["content"]

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
                "rank": rank,
            }
            try:
                db.articles.replace_one({"url": url}, article, upsert=True)
                return article
            except Exception as e:
                self.logger.error(f"Error inserting/updating article: {e}")
        else:
            db.article_download_fails.update_one(
                {"url": url}, {"$set": {"url": url}}, upsert=True
            )
        return 0


class GoogNewsReFormat:
    def __post_init__(self):
        self.logger = logging.getLogger("tailoredscoops.api")

    async def true_url(
        self, session: aiohttp.ClientSession, article: dict, timeout: int = 300
    ) -> Optional[dict]:
        """
        Retrieve the true URL of the article and its publication time.

        :param session: aiohttp client session.
        :param article: Article data.
        :return: Updated article data with true URL and publication time, or None if failed.
        """
        try:
            headers = {
                "User-Agent": "python-requests/2.20.0",
                "Accept-Language": "en-US,en;q=0.5",
            }
            published_at = datetime.datetime.strptime(
                article["published"], "%a, %d %b %Y %H:%M:%S %Z"
            )
            async with session.get(
                article["link"], headers=headers, timeout=timeout, allow_redirects=True
            ) as response:
                return {
                    "url": str(response.url),
                    "content": None,
                    "publishedAt": published_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "source": article["source"]["title"],
                    "title": article["title"],
                    "description": None,
                    "author": None,
                }
        except Exception:
            logging.error(f"true_url not found for {article['link']}")
            return None

    async def reformat_google(self, articles: List[dict]) -> List[dict]:
        """
        Reformat the given articles with true URLs and publication times.

        :param articles: List of articles.
        :return: List of reformatted articles.
        """
        async with aiohttp.ClientSession() as session:
            tasks = []
            for article in articles:
                task = asyncio.create_task(self.true_url(session, article))
                tasks.append(task)
            return [_ for _ in await asyncio.gather(*tasks) if _]


@dataclass
class NewsAPI(SetupMongoDB, DocumentProcessor, DownloadArticle, GoogNewsReFormat):
    api_key: str
    log: utils.Logger = utils.Logger()

    def __post_init__(self):
        self.now = datetime.datetime.now()
        self.log.setup_logger()
        self.logger = logging.getLogger("tailoredscoops.newsapi")

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

        for i, news_article in enumerate(articles):
            tasks.append(
                asyncio.ensure_future(
                    self.process_article(
                        news_article=news_article, url_hash=url_hash, db=db, rank=i
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

        articles = feedparser.parse(url).entries[:10]
        articles = await self.reformat_google(articles)
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

            self.logger.info(f"query url: {url}")
            articles = await self.request_google(db=db, url=url)
            if len(articles) <= 5:
                new_q = get_similar_keywords_from_gpt(query)
                if len(new_q) == 0:
                    return [], q
                new_query = "OR".join([f'"{x.strip()}"' for x in new_q.split(",")])
                url = f"https://news.google.com/rss/search?q={quote(new_query)}%20when%3A1d"
                self.logger.info(f"query url: {url}")
                articles = await self.request_google(db=db, url=url)
                used_q = used_q + ", " + new_q
            else:
                used_q = used_q + query
            results += articles
        return results, q
