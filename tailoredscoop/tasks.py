from tailoredscoop.news import api
from tailoredscoop import config
import openai
from celery import Celery

from celery.schedules import crontab

app = Celery('tailoredscoops', broker="redis://0.0.0.0:6379/0", backend="redis://0.0.0.0:6379/0")

@app.task(name="send_summary_task")
def send_summary():

    secrets = config.setup()
    openai.api_key = secrets["openai"]["api_key"]

    sender = api.EmailSummary(secrets=secrets)
    sender.send()

app.conf.timezone = 'UTC'
app.conf.beat_schedule = {
    'send_summary_task': {
        'task': 'send_summary_task',
        'schedule': crontab(hour=11, minute=0),
        # 'schedule': 60.0
    },
}
