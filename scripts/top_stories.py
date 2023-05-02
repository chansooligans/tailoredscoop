# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")

import openai
import tiktoken
from tailoredscoop.news import api
from tailoredscoop import config
from tailoredscoop.documents import summarize

# %%
secrets = config.setup()
news_downloader = api.NewsAPI(
    api_key = secrets["newsapi"]["api_key"]
)

articles = news_downloader.get_top_news()
res = news_downloader.process(articles, summarizer=summarize.summarizer)

# %%
today_news = "; ".join(res.values())
sources = "- "+"\n- ".join(res.keys())

messages = [
    {"role": "system", "content": "You are an energetic, fun, and witty daily news blogger."},
    {"role": "user", "content": "Please create a morning newsletter based on today's stories, which are stories from today's news."},
    {"role": "user", "content": "Separate different topics using different paragraphs. If the story is not too serious, feel free to include emojis and puns. Each bullet point should contain at least three sentences."},
    {"role": "user", "content": f"Today's stories are: {today_news}. The newsletter:"},
]

# %%
num_tokens = summarize.num_tokens_from_messages(messages, model="gpt-3.5-turbo")

# %%
response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages = messages,
    temperature=0.8,
    max_tokens=4096-num_tokens
)

# %%
print(response["choices"][0]["message"]["content"])

# %%
print(sources)

# %%
