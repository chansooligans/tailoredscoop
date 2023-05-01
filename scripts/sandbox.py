# %%
from tailoredscoop.news import api
import yaml
from pathlib import Path
import os

# %%
with open(
    Path(__file__).resolve().parent.parent.joinpath("secrets.yml"), "r"
) as file:
    secrets = yaml.load(file, Loader=yaml.FullLoader)
os.environ["OPENAI_API_KEY"] = secrets["openai"]["api_key"]

# %%
news_downloader = api.NewsAPI(
    api_key = secrets["newsapi"]["api_key"]
)

# %%
articles = news_downloader.get_top_news()

# %%
news_downloader.download(articles["articles"])

# %%
