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
            "url": "mock://example.com/article1",
            "publishedAt": "2023-01-01T00:00:00Z",
            "source": "Example News",
            "title": "Example Article",
            "description": "Description for Example Article",
            "author": "Example Author",
            "content": "Pod of Dolphins Spotted off Miami Beach",
        },
        {
            "url": "mock://example.com/article2",
            "publishedAt": "2023-01-02T00:00:00Z",
            "source": "Example News",
            "title": "Another Article",
            "description": "Description for Another Article",
            "author": "Another Author",
            "content": "Lions in the African Savannah",
        },
    ]


@pytest.fixture(scope="module")
def news_api() -> NewsAPI:
    return NewsAPI(api_key="")


@pytest.fixture(scope="module")
def db() -> mongomock.database.Database:
    client = mongomock.MongoClient()
    db = client.news_test
    entries = [
        {
            "url": "mock://example.com/article3",
            "publishedAt": "2023-01-02T00:00:00Z",
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
    mocker, content, mock_articles, news_api: NewsAPI, db: mongomock.database.Database
):
    resp = MockResponse(content[0], 200)
    resp2 = MockResponse(content[1], 200)
    mocker.patch("aiohttp.ClientSession.get", side_effect=[resp, resp2])
    url_hash = "sample_url_hash"

    results = await news_api.download(mock_articles, url_hash, db)
    assert len(results) == len(mock_articles)

    results = sorted(results, key=lambda d: d["url"])
    for key in [
        "url",
        "publishedAt",
        "source",
        "title",
        "description",
        "author",
        "content",
    ]:
        assert all(
            result[key] == article[key]
            for article, result in zip(mock_articles, results)
        )

    stored_article = db.articles.find_one({"url": mock_articles[0]["url"]})
    assert stored_article is not None
    assert stored_article["query_id"] == url_hash


@pytest.mark.parametrize(
    ("url,expected"),
    [
        ("www.cantfindthis.com", 0),
        ("mock://example.com/article3", 1),
    ],
)
@pytest.mark.asyncio
async def test_check_db_for_article(url, expected, news_api, db):
    article_check = news_api.check_db_for_article(url=url, db=db)
    assert len(article_check) == expected


@pytest.mark.asyncio
async def test_process_article(mocker, content, mock_articles, news_api, db):
    resp = MockResponse(content[0], 200)
    resp2 = MockResponse(content[1], 200)
    mocker.patch("aiohttp.ClientSession.get", side_effect=[resp, resp2])

    await news_api.process_article(
        news_article=mock_articles[0], url_hash="url_hash", db=db, rank=100
    )

    stored_article = db.articles.find_one({"url": mock_articles[0]["url"]})
    assert stored_article["rank"] == 100
