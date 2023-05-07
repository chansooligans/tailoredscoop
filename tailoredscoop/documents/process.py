from .summarize import num_tokens_from_messages

class DocumentProcessor:

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

    def process(self, articles, summarizer):
        res = {}
        for article in articles:
            print(f"summarizing with hf: {article['url']}")
            # chunks = self.split_text_into_chunks(article["content"])
            # summary_maps = [summarizer(chunk)[0]["summary_text"] for chunk in chunks]
            # summary = ", ".join(summary_maps)
            summary = summarizer(
                article["content"], 
                truncation="only_first",
                min_length=100,
                max_length=140,
                length_penalty=2,
                early_stopping=True,
                num_beams=1,
                # no_repeat_ngram_size=3,
            )[0]["summary_text"]
            print(f'summarized length: {num_tokens_from_messages(messages=[{"content":summary}])}')
            res[article["url"]] = summary
            self.db.articles.update_one({"_id": article["_id"]}, {"$set": {"summary": summary}})
        return res