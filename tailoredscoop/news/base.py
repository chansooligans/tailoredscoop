# %%
import requests
import hashlib
import datetime
from functools import cached_property
from bs4 import BeautifulSoup
from dataclasses import dataclass
import os


from tailoredscoop.db.init import SetupMongoDB
from tailoredscoop.documents.process import DocumentProcessor

@dataclass
class TestNewsAPI(SetupMongoDB, DocumentProcessor):
    api_key: str
    mongo_url: str

    def __post_init__(self):
        self.mongo_client = self.setup_mongodb()
        self.db = self.mongo_client.db_test  # Specify your MongoDB database name

        now = datetime.datetime.now()
        time_24_hours_ago = now - datetime.timedelta(days=1)
        self.time_24_hours_ago = time_24_hours_ago.isoformat()

    @property
    def fake_news(self):
        dir_path = "./fake_news"
        file_contents = []
        for filename in os.listdir(dir_path):
            if filename.endswith(".txt"):
                with open(os.path.join(dir_path, filename), "r") as f:
                    file_contents.append(f.read())

    def get_top_news(self, country="us", category=None, page_size=10):
        return
        
    def query_news_by_keywords(self, q="Apples", page_size=10):
        return
    
    def extract_article_content(self, url):
        return
        
    def download(self, articles, url_hash):
        return
    
# %%
TestNewsAPI()