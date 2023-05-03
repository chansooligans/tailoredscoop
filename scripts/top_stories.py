# %%
from tailoredscoop.news import api
from tailoredscoop import config
from tailoredscoop.documents import summarize
import openai
from django.core.mail import send_mail

email = "chansoosong@gmail.com" # email here
keywords = "" # keywords here

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]
news_downloader = api.NewsAPI(
    api_key = secrets["newsapi"]["api_key"]
)

if keywords == "":
    articles = news_downloader.get_top_news()
else:
    articles = news_downloader.query_news_by_topic(keywords)

print("articles")
print(articles)


res = news_downloader.process(articles, summarizer=summarize.summarizer)

print("res")
print(res)

summary = summarize.get_openai_summary(res)

print("summary")
print(summary)
