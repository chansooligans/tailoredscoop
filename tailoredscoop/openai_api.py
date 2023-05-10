import time

import openai


class ChatCompletion:
    @staticmethod
    def create(messages, model="gpt-3.5-turbo", temperature=0.3, max_tokens=4096):

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
                print(f"Error: {e}")
                if num_retries < 2:
                    print("Retrying in 30 seconds...")
                    time.sleep(30)
        print("API call failed after 2 retries. Exiting.")
