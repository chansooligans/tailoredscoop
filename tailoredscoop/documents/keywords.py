import openai

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