import datetime
import logging
import re
from dataclasses import dataclass

import openai
import tiktoken
from transformers import pipeline

from tailoredscoop import openai_api, utils


@dataclass
class OpenaiSummarizer:
    openai_api: openai_api.ChatCompletion
    log: utils.Logger = utils.Logger()

    def __post_init__(self):
        self.log.setup_logger()
        self.logger = logging.getLogger("tailoredscoops.OpenaiSummarizer")

    def num_tokens_from_messages(self, messages, model="gpt-3.5-turbo-0301"):
        """Returns the number of tokens used by a list of messages."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.logger.error("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        if model == "gpt-3.5-turbo":
            return self.num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
        elif model == "gpt-4":
            return self.num_tokens_from_messages(messages, model="gpt-4-0314")
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

    def get_openai_summary(self, data) -> str:
        # single param for asyncio
        res = data["res"]

        today_news = "; ".join(res.values())

        messages = [
            {
                "role": "user",
                "content": "Create a morning newsletter using today's news stories",
            },
            {
                "role": "user",
                "content": "Separate different news topics using different paragraphs. Each bullet point should contain at least three sentences.",
            },
            {
                "role": "user",
                "content": f"Today's news stories: {today_news}.",
            },
            {
                "role": "system",
                "content": "Write up to 600 words. Include at least 6 stories. Start the newsletter with a greeting, e.g. 'Good Morning!'.",
            },
            {
                "role": "system",
                "content": "Generate a headline for each story. Ignore and omit advertisements.",
            },
            {
                "role": "system",
                "content": """Example:
                Good morning! Here are today's top news stories:

                💻 <headline of story 1>

                <story of story 1>

                💼 <headline of story 2>

                <story of story 2>

                💰 <headline of story 3>

                <story of story 3>

                🐔 <headline of story 4>

                <story of story 4>

                📚 <headline of story 5>

                <story of story 5>

                💰 <headline of story 6>

                <story of story 6>

                🔒 <headline of story 7>

                <story story 7>

                👥 <headline story 8>

                <story story 8>

                That's all for today's news. Have a great day!
                """,
            },
            {"role": "system", "content": "The newsletter:"},
        ]

        num_tokens = self.num_tokens_from_messages(messages, model="gpt-3.5-turbo")

        if num_tokens > 2500:
            raise Exception(
                f"Number of Tokens of Hugging Face Summaries is too Large for Open AI to Summarize | n_tokens = {num_tokens}"
            )

        response = self.openai_api.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.2,
            max_tokens=4096 - num_tokens,
        )

        summary = response["choices"][0]["message"]["content"]
        summary = summary.replace("🔫", "📰")

        return summary

    def get_subject(self, summary):
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

        response = self.openai_api.create(
            model="gpt-3.5-turbo", messages=messages, temperature=0.8, max_tokens=100
        )

        subject = response["choices"][0]["message"]["content"]
        return subject.replace("🔫", "📰")

    # def get_url_headlines(self, urls):
    #     messages = [
    #         {"role": "user", "content": "Given URLs, convert them to headlines"},
    #         {
    #             "role": "user",
    #             "content": """
    #             Example:
    #                 urls = [
    #                     'https://thehill.com/homenews/state-watch/3994010-texas-panel-advances-bill-raising-minimum-age-to-buy-semiautomatic-rifles-after-allen-shooting/',
    #                     'https://www.cbssports.com/nba/news/will-nikola-jokic-be-suspended-in-nuggets-suns-series-examining-nba-rules-as-mat-ishbia-weighs-in-on-skirmish/',
    #                 ]

    #             Output:
    #                 The Hill: Texas Panel Advances Bill Raising Minimum Age to buy Semiautomatic Rifles After Allen Shooting
    #                 CBS Sports: Will Nikola Jokic Be Suspended In Nuggets Suns Series
    #         """,
    #         },
    #         {"role": "user", "content": f"urls: {urls}"},
    #         {"role": "system", "content": "outtput:"},
    #     ]

    #     response = openai_api.ChatCompletion.create(
    #         model="gpt-3.5-turbo", messages=messages, temperature=0, max_tokens=2000
    #     )

    #     return response["choices"][0]["message"]["content"]
