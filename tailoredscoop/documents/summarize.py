import datetime
import re

import openai
import tiktoken
from transformers import pipeline

from tailoredscoop import openai_api

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        print(
            "Warning: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301."
        )
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        print(
            "Warning: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314."
        )
        return num_tokens_from_messages(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def get_openai_summary(data) -> str:

    # single param for asyncio
    res = data["res"]
    kw = data["kw"]

    print(datetime.datetime.now(), "get_openai_summary")

    today_news = "; ".join(res.values())

    today = datetime.datetime.today().strftime("%A")

    messages = [
        {
            "role": "user",
            "content": "You are an energetic, fun, and witty daily news blogger.",
        },
        {
            "role": "user",
            "content": "Please create a morning newsletter based on today's news stories",
        },
        {
            "role": "user",
            "content": "Ignore and omit advertisements in the newsletter.",
        },
        {
            "role": "user",
            "content": "Separate different topics using different paragraphs. Each bullet point should contain at least three sentences.",
        },
        {"role": "user", "content": "Start each paragraph with a different emoji."},
        {
            "role": "user",
            "content": "Start the newsletter with a greeting.",
        },
        {"role": "user", "content": f"Today is {today}."},
        {
            "role": "user",
            "content": """Example: ### Good morning! Here are today's top news stories:

            💻 <story>

            💼 <story>

            💰 <story>

            🐔 <story>

            📚 <story>

            💰 <story>

            🔒 <story>

            👥 <story>

            That's all for today's news. Have a great day!
            ###
            """,
        },
        {
            "role": "user",
            "content": f"Today's news stories are: {today_news}. The newsletter:",
        },
    ]

    if kw:
        messages.insert(
            7,
            {
                "role": "user",
                "content": f"Only include stories related to these topics: {kw}",
            },
        )

    num_tokens = num_tokens_from_messages(messages, model="gpt-3.5-turbo")

    if num_tokens > 2500:
        print(num_tokens)
        raise Exception(
            "Number of Tokens of Hugging Face Summaries is too Large for Open AI to Summarize"
        )

    response = openai_api.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.3,
        max_tokens=4096 - num_tokens,
    )

    summary = response["choices"][0]["message"]["content"]
    summary = summary.replace("🔫", "📰")

    return summary


def get_subject(summary):

    print(datetime.datetime.now(), "get_subject")

    messages = [
        {
            "role": "system",
            "content": "You are an energetic, fun, and witty daily news blogger.",
        },
        {
            "role": "system",
            "content": "Given a summary, please create the email subject. Alternate between emojis and subtopics.",
        },
        {
            "role": "system",
            "content": "There should not be more than 2 emojis adjacent.",
        },
        {
            "role": "system",
            "content": "Example of subject: 🏇️ Kentucky Derby, 👑 Royal Coronation, 👮‍♂️ Police Arrests, 🗳️ Local Elections, and More!",
        },
        {"role": "user", "content": f"Summary: {summary}. Subject:"},
    ]

    response = openai_api.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=messages, temperature=0.8, max_tokens=100
    )

    subject = response["choices"][0]["message"]["content"]
    return subject.replace("🔫", "📰")


def convert_urls_to_links(urls):

    messages = [
        {"role": "user", "content": "Given URLs, convert them to links"},
        {
            "role": "user",
            "content": """
            Example:
                urls = [
                    'https://thehill.com/homenews/state-watch/3994010-texas-panel-advances-bill-raising-minimum-age-to-buy-semiautomatic-rifles-after-allen-shooting/',
                    'https://www.cbssports.com/nba/news/will-nikola-jokic-be-suspended-in-nuggets-suns-series-examining-nba-rules-as-mat-ishbia-weighs-in-on-skirmish/',
                ]

            Output:
                - <a href="https://thehill.com/homenews/state-watch/3994010-texas-panel-advances-bill-raising-minimum-age-to-buy-semiautomatic-rifles-after-allen-shooting/">The Hill: Texas Panel Advances Bill Raising Minimum Age to buy Semiautomatic Rifles After Allen Shooting</a>
                - <a href="https://www.cbssports.com/nba/news/will-nikola-jokic-be-suspended-in-nuggets-suns-series-examining-nba-rules-as-mat-ishbia-weighs-in-on-skirmish/">CBS Sports: Will Nikola Jokic Be Suspended In Nuggets Suns Series</a>
        """,
        },
        {"role": "user", "content": f"urls: {urls}"},
        {"role": "system", "content": "outtput:"},
    ]

    response = openai_api.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=messages, temperature=0, max_tokens=2000
    )

    return response["choices"][0]["message"]["content"]


def plain_text_to_html(text, no_head=False):

    text = text.replace("\n", "<br>")

    def link_replacer(match):
        link_text = match.group(1)
        link_url = match.group(2)
        return f'<a href="{link_url}" style="color: #a8a8a8;">{link_text}</a>'

    html = re.sub(r"\[(.*?)\]\((.*?)\)", link_replacer, text)

    if no_head:
        return f"<p>{html}</p>"
    else:
        return f"<html><head></head><body><p>{html}</p></body></html>"


def abridge_summary(summary):

    print(datetime.datetime.now(), "abridge")

    return summarizer(
        summary,
        truncation="only_first",
        min_length=100,
        max_length=140,
        length_penalty=2,
        early_stopping=True,
        num_beams=1,
        # no_repeat_ngram_size=3,
    )[0]["summary_text"]
