import asyncio
import re
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pymongo
import pytest
from botocore.exceptions import ClientError

from tailoredscoop.api import EmailSummary
from tailoredscoop.news.newsapi_with_google_kw import NewsAPI


@pytest.fixture
def news_api_mock():
    return MagicMock(spec=NewsAPI)


@pytest.fixture
def db_mock():
    return MagicMock(spec=pymongo.database.Database)


@pytest.fixture
def subscribed_users():
    return pd.DataFrame(
        {
            "id": [1, 1],
            "email": ["test1@example.com", "test2@example.com"],
            "kw": ["test_keyword1", "test_keyword2"],
            "hashed_email": [1, 1],
        }
    )


@pytest.mark.asyncio
async def test_cleanup():
    email_summary = EmailSummary()
    text = "This is a [sample] text with [brackets] and content inside."
    cleaned_text = email_summary.cleanup(text)
    assert re.search(r"\[.*?\]", cleaned_text) is None
    assert cleaned_text == "This is a  text with  and content inside."


@pytest.mark.asyncio
async def test_send(news_api_mock, db_mock, subscribed_users):
    email_summary = EmailSummary(news_api_mock, db_mock)
    email_summary.send_one = AsyncMock()

    await email_summary.send(subscribed_users, test=False)

    assert email_summary.send_one.call_count == len(subscribed_users)
