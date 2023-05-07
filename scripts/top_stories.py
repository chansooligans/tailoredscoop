#!/usr/bin/python
from tailoredscoop.news import api
from tailoredscoop import config
import openai

import multiprocessing
num_cpus = multiprocessing.cpu_count()
print("Number of CPUs: ", num_cpus)

secrets = config.setup()
openai.api_key = secrets["openai"]["api_key"]

sender = api.EmailSummary(secrets=secrets)

# %%
sender.send()


# %%
