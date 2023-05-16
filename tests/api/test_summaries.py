import asyncio
import datetime
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from tailoredscoop.api import Summaries

# Replace "your_module" with the actual name of the module containing the Summaries class.


@pytest.fixture
def summaries_fixture():
    db_mock = MagicMock()
    summarizer_mock = MagicMock()
    summarizer_mock.get_openai_summary = MagicMock()
    summarizer_mock.get_openai_summary.return_value = "summary"
    return Summaries(
        db=db_mock, summarizer=summarizer_mock, now=datetime.datetime.now()
    )


@pytest.fixture
def saved_summary_fixture():
    return {
        "summary": "Sample summary",
        "titles": ["Title 1", "Title 2"],
        "encoded_urls": ["https://example.com/1", "https://example.com/2"],
    }


@pytest.mark.parametrize(
    "return_value,expected",
    [
        (([], None), {"summary": None, "urls": None}),
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
        "tailoredscoop.documents.summarize.get_openai_summary"
    ) as mocked_get_openai_summary:
        mocked_get_openai_summary.return_value = "This is a mocked summary."
        email = "test@example.com"
        news_downloader_mock = MagicMock()
        news_downloader_mock.process = MagicMock()
        news_downloader_mock.process.return_value = (None, None, "encoded_urls")

        async def get_articles(email, news_downloader, kw=None):
            return return_value

        # In the test code
        summaries_fixture.get_articles = get_articles
        summaries_fixture.upload_summary = MagicMock()

        summary = await summaries_fixture.create_summary(
            email, news_downloader_mock, "test_summary_id"
        )

        assert summary == expected


def test_format_summary(summaries_fixture, saved_summary_fixture):
    email = "test@example.com"
    formatted_summary = summaries_fixture.format_summary(saved_summary_fixture, email)
    assert "Sample summary" in formatted_summary
    assert "Title 1" in formatted_summary
    assert "Title 2" in formatted_summary
    assert '<a href="https://example.com/1">Title 1</a>' in formatted_summary
    assert '<a href="https://example.com/2">Title 2</a>' in formatted_summary
    assert "[Unsubscribe](https://apps.chansoos.com/" in formatted_summary


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
