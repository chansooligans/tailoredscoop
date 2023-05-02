# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")
from tailoredscoop.news import api
from tailoredscoop import config

from tailoredscoop.documents.summarize import summarizer

# %%
secrets = config.setup()
news_downloader = api.NewsAPI(
    api_key = secrets["newsapi"]["api_key"]
)

articles = news_downloader.query_news_by_topic("Letitia James")
res = news_downloader.process(articles, summarizer=summarizer)

# %%
today_news = "; ".join(res.values())
len(today_news)

# %%
print(
    f"""
You are an energetic, fun, and witty daily news blogger. 
Please create a morning newsletter based on the following information, which are stories from today's news.
Separate different topics using different paragraphs. If the story is not too serious, feel free to include emojis and puns. Each bullet point should contain at least three sentences.
{today_news}
"""
)
# %%
