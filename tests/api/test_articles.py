import asyncio
import datetime
from typing import List, Optional, Tuple
from unittest.mock import MagicMock

import mongomock
import pymongo
import pytest

from tailoredscoop.api import Articles


# Fixture for the mock MongoDB database
@pytest.fixture
def db():
    return mongomock.MongoClient().db


# Fixture for the Articles class
@pytest.fixture
def articles(db):
    return Articles(db=db, now=datetime.datetime.now())


# Fixture for the NewsAPI class (a MagicMock object)
@pytest.fixture
def news_downloader():
    return MagicMock()


async def query_news_by_keywords_mock(q, db):
    return ([{"url": "https://example.com/article1"}], "test")


async def get_top_news(q, db):
    return [
        {"url": "https://example.com/article2"},
        {"url": "https://example.com/article3"},
    ]


def test_check_shown_articles(articles):
    email = "test@example.com"

    articles.db.email_article_log.insert_one(
        {"email": email, "urls": ["https://example.com/article1"]}
    )

    articles_list = [
        {"url": "https://example.com/article1"},
        {"url": "https://example.com/article2"},
        {"url": "https://example.com/article3"},
    ]

    result = articles.check_shown_articles(email=email, articles=articles_list)
    assert len(result) == 2
    assert result[0]["url"] == "https://example.com/article2"
    assert result[1]["url"] == "https://example.com/article3"


@pytest.mark.asyncio
async def test_get_articles(articles, news_downloader):
    email = "test@example.com"

    # Mock the query_news_by_keywords method of the news_downloader
    news_downloader.query_news_by_keywords.return_value = asyncio.create_task(
        query_news_by_keywords_mock(q="test", db=None)
    )

    # Mock the get_top_news method of the news_downloader
    news_downloader.get_top_news.return_value = asyncio.create_task(
        get_top_news(q="test", db=None)
    )

    # Test get_articles with a keyword
    result, kw = await articles.get_articles(
        email=email, news_downloader=news_downloader, kw="test"
    )

    assert len(result) == 1

    # Test get_articles without a keyword
    result = await articles.get_articles(email=email, news_downloader=news_downloader)

    assert len(result) == 2
