import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

import pymongo

from tailoredscoop import utils

from .summarize import num_tokens_from_messages


@dataclass
class DocumentProcessor:
    def __post_init__(self):
        self.logger = logging.getLogger("tailoredscoops.DocumentProcessor")

    def split_text_into_chunks(self, text, max_chunk_size=3000):
        chunks = []
        current_chunk = ""

        # Split the text into words
        words = text.split()

        for word in words:
            # If adding the current word exceeds the maximum chunk size, start a new chunk
            if len(current_chunk) + len(word) + 1 > max_chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Add the word to the current chunk
            current_chunk += word + " "

        # Append the last chunk
        chunks.append(current_chunk.strip())

        return chunks

    @staticmethod
    def encode_urls(urls, email: Optional[str] = None):

        base = "https://apps.chansoos.com/tailoredscoop/log_click/"
        hashed_email = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return [
            f"{base}/{base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')}/{hashed_email}"
            for url in urls
        ]

    def process(
        self,
        articles,
        summarizer,
        db: pymongo.database.Database,
        email: Optional[str] = None,
    ):
        res = {}
        for article in articles:
            self.logger.info(f"summarizing with hf: {article['url']}")
            # chunks = self.split_text_into_chunks(article["content"])
            # summary_maps = [summarizer(chunk)[0]["summary_text"] for chunk in chunks]
            # summary = ", ".join(summary_maps)
            summary = summarizer(
                article["content"],
                truncation="only_first",
                min_length=140,
                max_length=200,
                length_penalty=2,
                early_stopping=True,
                num_beams=1,
                # no_repeat_ngram_size=3,
            )[0]["summary_text"]
            self.logger.info(
                f'summarized length: {num_tokens_from_messages(messages=[{"content":summary}])}'
            )
            res[article["url"]] = summary
            db.articles.update_one(
                {"_id": article["_id"]}, {"$set": {"summary": summary}}
            )
        urls = list(res.keys())

        if email:
            return res, urls, self.encode_urls(urls, email=email)
        else:
            return res, urls
