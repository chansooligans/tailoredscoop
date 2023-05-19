import datetime

from tailoredscoop.documents import summarize


def get_messages(res, kw):
    today_news = "; ".join(res.values())

    messages = [
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
            "content": "Separate different news topics using different paragraphs. Each bullet point should contain at least three sentences.",
        },
        {"role": "user", "content": "Start each paragraph with a different emoji."},
        {"role": "user", "content": "Generate a headline for each story."},
        {
            "role": "user",
            "content": "Start the newsletter with a greeting, e.g. 'Good Morning!'.",
        },
        {
            "role": "user",
            "content": f"Today's news stories: {today_news}.",
        },
        {
            "role": "user",
            "content": "Write up to 600 words.",
        },
        {
            "role": "user",
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
