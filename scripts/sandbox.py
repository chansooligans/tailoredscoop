# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
from tailoredscoop.news import api
from tailoredscoop import config
from tailoredscoop.documents.process import split_text_into_chunks
from tailoredscoop.documents.summarize import summarizer

# %%
secrets = config.setup()
news_downloader = api.NewsAPI(
    api_key = secrets["newsapi"]["api_key"]
)

# %%
articles = news_downloader.get_top_news()
news_downloader.download(articles["articles"])

# %%
articles = news_downloader.query_news_by_topic("Letitia James")
news_downloader.download(articles["articles"])

# %%
col = news_downloader.mongo_client.db1["articles"]
articles = [article for article in col.find({})]

# %%
res = {}
for article in articles:
    chunks = split_text_into_chunks(article["content"])
    summary_maps = [summarizer(chunk)[0]["summary_text"] for chunk in chunks]
    summary = ", ".join(summary_maps)
    res[article["url"]] = summary

# %%
today_news = "; ".join(res.values())
len(today_news)

# %%
