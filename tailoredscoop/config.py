import yaml
from pathlib import Path
import os

def setup():
    with open(
        Path(__file__).resolve().parent.parent.joinpath("secrets.yml"), "r"
    ) as file:
        secrets = yaml.load(file, Loader=yaml.FullLoader)
    os.environ["OPENAI_API_KEY"] = secrets["openai"]["api_key"]
    return secrets