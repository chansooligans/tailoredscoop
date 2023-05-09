import openai

def get_similar_keywords_from_gpt(kw):

    messages = [
        {"role": "system", "content": "Generate at least 5 similar keywords to query news articles so that it's likely to find recent results"},
        {"role": "system", "content": "Return keywords in comma separated format"},
        {"role": "system", "content": "Example input: 'supreme court'"},
        {"role": "system", "content": "Example output: 'SCOTUS, justice, judiciary, constitutional law, courts'"},
        {"role": "system", "content": "If error, return ''"},
        {"role": "user", "content": f"keywords: {kw}"},
        {"role": "system", "content": "keywords:"},
    ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages = messages,
        temperature=0.7,
        max_tokens=50
    )

    return response["choices"][0]["message"]["content"]

def get_topic(kw):

    messages = [
        {"role": "system", "content": "You are a classification tool."},
        {"role": "system", "content": "Given keywords, please classify them to a common news subcategory. The subcategory must be one of: business, entertainment, general, health, science, sports, technology"},
        {"role": "user", "content": f"keywords: {kw}"},
        {"role": "system", "content": "subcategory:"},
    ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages = messages,
        temperature=0.1,
        max_tokens=2
    )

    return response["choices"][0]["message"]["content"]