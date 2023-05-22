import logging
import time

import openai

from tailoredscoop import utils

log = utils.Logger()
log.setup_logger()
logger = logging.getLogger("tailoredscoops.openai_api")


class ChatCompletion:
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
            except openai.Error as e:
                num_retries += 1
                logger.error(f"Error: {e}")
                if num_retries < 2:
                    print("Retrying in 30 seconds...")
                    time.sleep(30)
        logger.error("API call failed after 2 retries. Exiting.")
