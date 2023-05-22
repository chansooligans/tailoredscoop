import asyncio
import datetime
from dataclasses import replace
from unittest.mock import MagicMock, patch

import mongomock
import pytest

from tailoredscoop.api import Summaries
from tailoredscoop.documents.summarize import OpenaiSummarizer
from tailoredscoop.openai_api import ChatCompletion


@pytest.fixture
def db():
    return mongomock.MongoClient().db


@pytest.fixture
def summaries_fixture(db):
    summarizer_mock = MagicMock()
    summarizer_mock.get_openai_summary = MagicMock()
    summarizer_mock.get_openai_summary.return_value = "summary"
    return Summaries(
        db=db,
        summarizer=summarizer_mock,
        now=datetime.datetime.now(),
        openai_summarizer=OpenaiSummarizer(openai_api=ChatCompletion()),
    )


@pytest.fixture
def saved_summary_fixture():
    return {
        "summary": "Sample summary",
        "titles": ["Title 1", "Title 2"],
        "encoded_urls": ["https://example.com/1", "https://example.com/2"],
    }


def test_upload_summary(db, summaries_fixture):
    summaries_fixture.upload_summary(
        summary_id="123456",
        summary="This is the summary",
        titles=["Title 1", "Title 2", "Title 3"],
        encoded_urls=["url1", "url2", "url3"],
        kw="Keyword",
    )

    assert len(list(db.summaries.find({}))) == 1

    summaries_fixture.upload_summary(
        summary_id="123456",
        summary="updated",
        titles=["Title 1", "Title 2", "Title 3"],
        encoded_urls=["url1", "url2", "url3"],
        kw="Keyword",
    )

    assert list(db.summaries.find({}))[0]["summary"] == "updated"


@pytest.mark.parametrize(
    "summary,expected",
    [
        ("", True),
        ("Sorry, there is no summary available.", True),
        ("Good morning! Your stories: Unfortunately, there are none.", True),
        ("This is a normal summary.", False),
    ],
)
def test_summary_error(summaries_fixture, summary, expected):
    assert summaries_fixture.summary_error(summary) is expected


def test_format_summary(summaries_fixture, saved_summary_fixture):
    email = "test@example.com"
    formatted_summary = summaries_fixture.format_summary(saved_summary_fixture, email)
    assert "Sample summary" in formatted_summary
    assert "Title 1" in formatted_summary
    assert "Title 2" in formatted_summary
    assert '<a href="https://example.com/1">Title 1</a>' in formatted_summary
    assert '<a href="https://example.com/2">Title 2</a>' in formatted_summary
    assert (
        '<a href="https://tailoredscoops.com/tailoredscoop/unsubscribe/'
        in formatted_summary
    )


@pytest.mark.parametrize(
    "return_value,expected",
    [
        (([], None), {"summary": None, "titles": None, "encoded_urls": None}),
        (
            ([{"title": "test"}], None),
            {
                "summary": "This is a mocked summary.",
                "titles": ["test"],
                "encoded_urls": "encoded_urls",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_create_summary(summaries_fixture, return_value, expected):
    with patch(
        "tailoredscoop.documents.summarize.OpenaiSummarizer.get_openai_summary"
    ) as mocked_get_openai_summary:
        mocked_get_openai_summary.return_value = "This is a mocked summary."
        email = "test@example.com"
        news_downloader_mock = MagicMock()
        news_downloader_mock.process = MagicMock()
        news_downloader_mock.process.return_value = (None, ["test"], "encoded_urls")

        async def get_articles(email, news_downloader, kw=None):
            return return_value

        # In the test code
        summaries_fixture.get_articles = get_articles
        summaries_fixture.upload_summary = MagicMock()

        summary = await summaries_fixture.create_summary(
            email, news_downloader_mock, "test_summary_id"
        )

        assert summary == expected


@pytest.mark.asyncio
async def test_get_summary(summaries_fixture):
    kw = "keyword"
    summary_id = summaries_fixture.summary_hash(kw)
    summaries_fixture.db.summaries.insert_one(
        {
            "created_at": datetime.datetime.now(),
            "summary_id": summary_id,
            "summary": "HELLO!",
            "titles": ["title 1"],
            "encoded_urls": ["encoded_url1"],
            "kw": "keyword",
        }
    )

    summary, check_id = await summaries_fixture.get_summary(
        email="user1@email.com", kw=kw
    )
    assert summary.startswith("HELLO!")
    assert check_id == summary_id
