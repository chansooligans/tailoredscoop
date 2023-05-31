# %%
import time
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# docker run -d -p 4444:4444 -p 7900:7900 --shm-size="2g" --name selenium-container selenium/standalone-chrome:latest

# Configure Selenium to connect to the Docker container
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Remote(
    command_executor="http://localhost:4444/wd/hub",
    desired_capabilities=options.to_capabilities(),
)


# %%
with open("queries.txt", "r") as f:
    queries = f.readlines()

match = {}
for query in queries:

    # Navigate to the URL
    query = query.strip().lower()
    driver.get(
        f"https://news.google.com/search?q={quote(query)}&hl=en-US&gl=US&ceid=US%3Aen"
    )

    time.sleep(1)
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, "html.parser")
    elements = soup.find_all("a", class_="boy4he")

    for element in elements:
        if element["aria-label"].lower() == query:
            match[query] = element["href"].split("?hl")[0].split("/")[-1]


# %%
match
# %%

# %%
