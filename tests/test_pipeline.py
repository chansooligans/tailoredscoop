import asyncio
import datetime
import hashlib
import unittest
from typing import List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import mongomock
import numpy as np
import pandas as pd
import pymongo
import pytest

from tailoredscoop.api import EmailSummary
from tailoredscoop.news import newsapi_with_google_kw, users
from tailoredscoop.news.newsapi_with_google_kw import NewsAPI

# %% [markdown]
"""
Configuration
"""


# %%
@pytest.fixture(scope="module")
def newsapi() -> NewsAPI:
    return NewsAPI(api_key="")


@pytest.fixture
def summarizer():
    summarizer_mock = MagicMock()
    summarizer_mock.get_openai_summary = AsyncMock()
    summarizer_mock.get_openai_summary.return_value = "summary"
    return summarizer_mock


@pytest.fixture
def abridge_summary():
    with patch("tailoredscoop.api.Subjects.abridge_summary") as mock_abridge_summary:
        yield mock_abridge_summary


@pytest.fixture
def get_subject():
    with patch(
        "tailoredscoop.documents.summarize.OpenaiSummarizer.get_subject"
    ) as get_subject:
        yield get_subject


@pytest.fixture
def db():
    db = mongomock.MongoClient().db
    entries = [
        {
            "email": "user1@example.com",
            "created_at": datetime.datetime.now(),
            "summary_id": "123456",
        },
        {
            "email": "user2@example.com",
            "created_at": datetime.datetime.now(),
            "summary_id": "789012",
        },
    ]

    # Insert the fake entries into the "sent" collection
    for entry in entries:
        db.sent.insert_one(entry)

    return db


@pytest.fixture
def client():
    with patch("tailoredscoop.api.boto3.client") as client:
        client.send_email = MagicMock()
        yield client


@pytest.fixture
def sender(newsapi, db, summarizer, abridge_summary, get_subject, client):
    abridge_summary.return_value = "abridged_summary"
    get_subject.return_value = "openai generated subject"
    client.send_email.return_value = {"MessageID": 1}
    sender = EmailSummary(news_downloader=newsapi, db=db, summarizer=summarizer)
    sender.get_summary = AsyncMock()
    sender.get_summary.return_value = ("this is the summary", "summary_id")
    return sender


@pytest.fixture
def df_users():
    df_users = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "email": [
                "user1@example.com",
                "user2@example.com",
                "user3@example.com",
            ],
            "keywords": ["keyword1", "keyword2", "keyword3"],
        }
    )
    df_users["hashed_email"] = df_users["email"].apply(
        lambda x: hashlib.sha256(x.encode()).hexdigest()
    )

    return df_users


@pytest.fixture
def df_list(db, df_users):
    query = {
        "created_at": {
            "$gte": datetime.datetime.combine(
                datetime.date.today(), datetime.datetime.min.time()
            ),
        }
    }

    sent = list(db.sent.find(query, {"email": 1, "_id": 0}))

    if sent:
        df_sent = pd.DataFrame(sent)["email"]
        df_users = df_users.loc[~df_users["email"].isin(df_sent)]

    return np.array_split(df_users, max(len(df_users) // 100, 1))


class EmailSummaryTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_client = patch("tailoredscoop.api.boto3.client")

    @pytest.fixture(autouse=True)
    def prepare_fixture(self, df_list, sender):
        self.df_list = df_list
        self.sender = sender

    def test_send(self):
        for chunk in self.df_list:
            asyncio.run(self.sender.send(subscribed_users=chunk))
        sent = pd.DataFrame(list(self.sender.db.sent.find({})))

        assert sent["created_at"].nunique() == 2
