
from transformers import pipeline
import openai
import tiktoken

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        print("Warning: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        print("Warning: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
        return num_tokens_from_messages(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

def get_openai_summary(res):

    today_news = "; ".join(res.values())
    sources = "- "+"\n- ".join(res.keys())

    messages = [
        {"role": "system", "content": "You are an energetic, fun, and witty daily news blogger."},
        {"role": "user", "content": "Please create a morning newsletter based on today's news stories"},
        {"role": "system", "content": "Ignore advertisements and omit advertisements in the newsletter."},
        {"role": "system", "content": "Separate different topics using different paragraphs. If the story is not too serious, feel free to use puns. Each bullet point should contain at least three sentences."},
        {"role": "system", "content": "Start the newsletter with a 'good morning' and cute greeting about today's scoops. Start each paragraph with an emoji."},
        {"role": "user", "content": f"Today's news stories are: {today_news}. The newsletter:"},
    ]

    num_tokens = num_tokens_from_messages(messages, model="gpt-3.5-turbo")

    if num_tokens > 2500:
        print(num_tokens)
        raise Exception("Number of Tokens of Hugging Face Summaries is too Large for Open AI to Summarize")

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages = messages,
        temperature=0.8,
        max_tokens=4096-num_tokens
    )

    return response["choices"][0]["message"]["content"]

def get_subject(summary):
    messages = [
        {"role": "system", "content": "You are an energetic, fun, and witty daily news blogger."},
        {"role": "system", "content": "Given a summary, please create the email subject. Alternate between emojis and subtopics."},
        {"role": "system", "content": "There should not be more than 2 emojis adjacent."},
        {"role": "system", "content": "Example of subject: 🏇️ Kentucky Derby, 👑 Royal Coronation, 👮‍♂️ Police Arrests, 🗳️ Local Elections, and More!"},
        {"role": "user", "content": f"Summary: {summary}. Subject:"},
    ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages = messages,
        temperature=0.8,
        max_tokens=100
    )

    return response["choices"][0]["message"]["content"]