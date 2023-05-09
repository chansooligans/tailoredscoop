import os
from pathlib import Path

import yaml


def setup():
    secrets_file = Path(__file__).resolve().parent.parent.joinpath("secrets.yml")
    if os.path.isfile(secrets_file):
        with open(secrets_file, "r") as file:
            secrets = yaml.load(file, Loader=yaml.FullLoader)
        os.environ["OPENAI_API_KEY"] = secrets["openai"]["api_key"]
    else:
        secrets = {
            "openai": {"api_key": os.environ["OPENAI_API_KEY"]},
            "newsapi": {"api_key": os.environ["NEWSAPI_API_KEY"]},
            "mysql": {
                "username": os.environ["MYSQL_USERNAME"],
                "password": os.environ["MYSQL_PASSWORD"],
                "host": os.environ["MYSQL_HOST"],
                "database": os.environ["MYSQL_DATABASE"],
            },
            # "sendgrid": {"api_key": os.environ["SENDGRID_API_KEY"]},
            "mongodb": {"url": os.environ["MONGODB_URL"]},
        }
    return secrets
