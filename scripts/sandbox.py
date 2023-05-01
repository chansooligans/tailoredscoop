# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
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
