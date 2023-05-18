import datetime

from tailoredscoop.documents import summarize


def get_messages(res, kw):
    today_news = "; ".join(res.values())

    messages = [
        {
            "role": "user",
            "content": "You are an energetic, fun, and witty daily news blogger.",
        },
        {
            "role": "user",
            "content": "Create a morning newsletter using today's news stories",
        },
        {
            "role": "user",
            "content": "Ignore and omit advertisements.",
        },
        {
            "role": "user",
            "content": "Use 10 paragraphs or less.",
        },
        {
            "role": "user",
            "content": "Separate different news topics using different paragraphs. Each bullet point should contain at least three sentences.",
        },
        {"role": "user", "content": "Start each paragraph with a different emoji."},
        {
            "role": "user",
            "content": "Start the newsletter with a greeting, e.g. 'Good Morning!'.",
        },
        # {"role": "user", "content": f"Today is {today}."},
        {
            "role": "user",
            "content": f"Today's news stories: {today_news}.",
        },
        {
            "role": "user",
            "content": "Use 400-600 words.",
        },
        {
            "role": "user",
            "content": """Example:
            Good morning! Here are today's top news stories:

            💻 <headline>

            <story>

            💼 <headline>

            <story>

            💰 <headline>

            <story>

            🐔 <headline>

            <story>

            📚 <headline>

            <story>

            💰 <headline>

            <story>

            🔒 <headline>

            <story>

            👥 <headline>

            <story>

            That's all for today's news. Have a great day!
            """,
        },
        {"role": "user", "content": "The newsletter:"},
    ]

    if kw:
        messages.insert(
            6,
            {
                "role": "user",
                "content": f"Only include stories related to any of these topics: {kw}",
            },
        )
    return messages


def get_tokens(messages):
    num_tokens = summarize.num_tokens_from_messages(messages, model="gpt-3.5-turbo")

    if num_tokens > 2500:
        print(num_tokens)
        raise Exception(
            "Number of Tokens of Hugging Face Summaries is too Large for Open AI to Summarize"
        )

    return num_tokens
