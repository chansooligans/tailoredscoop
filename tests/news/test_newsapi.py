import asyncio
import os
from typing import List, Optional

import mongomock
import pymongo
import pytest

from tailoredscoop.news.newsapi_with_google_kw import NewsAPI


@pytest.fixture(scope="module")
def news_api() -> NewsAPI:
    return NewsAPI(api_key="")


@pytest.fixture(scope="module")
def db() -> mongomock.database.Database:
    client = mongomock.MongoClient()
    return client.news_test


def create_mock_articles(n: int) -> List[dict]:
    articles = []
    for i in range(n):
        article = {
            "url": f"https://example.com/article{i}",
            "publishedAt": "2023-01-01T00:00:00Z",
            "source": "Example News",
            "title": f"Example Article {i}",
            "description": f"Description for Example Article {i}",
            "author": "Example Author",
            "content": f"Content for Example Article {i}",
        }
        articles.append(article)
    return articles


@pytest.mark.asyncio
async def test_download(news_api: NewsAPI, db: mongomock.database.Database):
    mock_articles = create_mock_articles(3)
    url_hash = "sample_url_hash"

    results = await news_api.download(mock_articles, url_hash, db)

    assert len(results) == len(mock_articles)
    assert all(result == 1 for result in results)

    for mock_article in mock_articles:
        url = mock_article["url"]
        stored_article = db.articles.find_one({"url": url})
        assert stored_article is not None
        assert stored_article["query_id"] == url_hash
