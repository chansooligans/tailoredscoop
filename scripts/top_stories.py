# %%
from tailoredscoop.news import api
from tailoredscoop import config
import openai

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

sender = api.EmailSummary(secrets=secrets)

# %%
sender.send()


# %%
