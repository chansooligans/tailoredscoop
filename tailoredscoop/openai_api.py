import logging
import time
from dataclasses import dataclass

import openai

from tailoredscoop import utils


@dataclass
class ChatCompletion:
    log: utils.Logger = utils.Logger()

    def __post_init__(self):
        self.log.setup_logger()
        self.logger = logging.getLogger("tailoredscoops.openai_api.ChatCompletion")

    def create(self, messages, model="gpt-3.5-turbo", temperature=0.3, max_tokens=4096):

        num_retries = 0
        while num_retries < 2:
            try:
                return openai.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                num_retries += 1
                self.logger.error(f"Error: {e}")
                if num_retries < 2:
                    self.logger.info("Retrying in 30 seconds...")
                    time.sleep(30)
        self.logger.error("API call failed after 2 retries. Exiting.")
