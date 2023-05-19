import datetime

import mongomock
import pytest
from aiohttp.test_utils import make_mocked_coro
from aioresponses import aioresponses

from tailoredscoop.news.newsapi_with_google_kw import NewsAPI


class MockResponse:
    def __init__(self, text, status):
        self._text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self


@pytest.fixture
def content():
    return [
        b"""<html></head><body><article><p>Pod of Dolphins Spotted off Miami Beach</p></article></body></html>""",
        b"""<html></head><body><article><p>Lions in the African Savannah</p></article></body></html>""",
    ]


@pytest.fixture
def mock_articles():
    return [
        {
            "link": "news.google/rss/1",
            "url": "mock://example.com/article1",
            "published": "Fri, 19 May 2023 21:40:11 GMT",
            "source": {"title": "Example News"},
            "title": "Example Article",
            "content": "Pod of Dolphins Spotted off Miami Beach",
        },
        {
            "link": "news.google/rss/2",
            "url": "mock://example.com/article2",
            "published": "Fri, 19 May 2023 21:40:11 GMT",
            "source": {"title": "Example News"},
            "title": "Another Article",
            "content": "Lions in the African Savannah",
        },
    ]


@pytest.fixture
def expected_processed_articles():
    return [
        {
            "url": "mock://example.com/article1",
            "link": "news.google/rss/1",
            "published": datetime.datetime(2023, 5, 19, 21, 40, 11),
            "source": "Example News",
            "title": "Example Article",
            "content": "Pod of Dolphins Spotted off Miami Beach",
            "created_at": datetime.datetime(2023, 5, 19, 17, 42, 44, 612498),
            "query_id": "sample_url_hash",
            "rank": 0,
        },
        {
            "url": "mock://example.com/article2",
            "link": "news.google/rss/2",
            "published": datetime.datetime(2023, 5, 19, 21, 40, 11),
            "source": "Example News",
            "title": "Another Article",
            "content": "Lions in the African Savannah",
            "created_at": datetime.datetime(2023, 5, 19, 17, 42, 44, 612872),
            "query_id": "sample_url_hash",
            "rank": 1,
        },
    ]


@pytest.fixture(scope="module")
def news_api() -> NewsAPI:
    return NewsAPI(api_key="")


@pytest.fixture
def db() -> mongomock.database.Database:
    client = mongomock.MongoClient()
    db = client.news_test
    entries = [
        {
            "link": "news.google/rss/3",
            "url": "mock://example.com/article3",
            "published": "2023-01-02T00:00:00Z",
            "source": "Example News",
            "title": "Another Article",
            "description": "Description for Another Article",
            "author": "Another Author",
            "content": "This was already in the database",
        }
    ]

    # Insert the fake entries into the "sent" collection
    for entry in entries:
        db.articles.insert_one(entry)

    return db


@pytest.mark.asyncio
async def test_download(
    mocker,
    content,
    mock_articles,
    expected_processed_articles,
    news_api: NewsAPI,
    db: mongomock.database.Database,
):
    resp = MockResponse(content[0], 200)
    resp.url = "mock://example.com/article1"
    resp2 = MockResponse(content[1], 200)
    resp2.url = "mock://example.com/article2"
    mocker.patch("aiohttp.ClientSession.get", side_effect=[resp, resp2])
    url_hash = "sample_url_hash"

    results = await news_api.download(mock_articles, url_hash, db)
    assert len(results) == len(mock_articles)

    results = sorted(results, key=lambda d: d["url"])

    for key in [
        "url",
        "published",
        "source",
        "title",
        "content",
    ]:
        for article, result in zip(expected_processed_articles, results):
            assert result[key] == article[key]

    stored_article = db.articles.find_one({"url": mock_articles[0]["url"]})
    assert stored_article is not None
    assert stored_article["query_id"] == url_hash


@pytest.mark.parametrize(
    ("link,expected"),
    [
        ("www.cantfindthis.com", None),
        (
            "news.google/rss/3",
            {
                "link": "news.google/rss/3",
                "url": "mock://example.com/article3",
                "published": "2023-01-02T00:00:00Z",
                "source": "Example News",
                "title": "Another Article",
                "description": "Description for Another Article",
                "author": "Another Author",
                "content": "This was already in the database",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_check_db_for_article(link, expected, news_api, db):
    article_check = news_api.check_db_for_article(link=link, db=db)
    assert article_check == expected


@pytest.mark.asyncio
async def test_process_article(mocker, content, mock_articles, news_api, db):
    resp = MockResponse(content[0], 200)
    resp.url = "mock://example.com/article1"
    resp2 = MockResponse(content[1], 200)
    resp2.url = "mock://example.com/article2"
    mocker.patch("aiohttp.ClientSession.get", side_effect=[resp, resp2])

    await news_api.process_article(
        article=mock_articles[0], url_hash="url_hash", db=db, rank=100
    )

    stored_article = db.articles.find_one({"link": mock_articles[0]["link"]})
    assert stored_article["rank"] == 100
