# %%
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

fp = "/home/chansoo/projects/tailoredscoop/tailoredscoop/news/fake_news"
routes = [
    Mount("/static", app=StaticFiles(directory=fp), name="static"),
]

app = Starlette(routes=routes)

# uvicorn fakeserver:app --host 0.0.0.0 --port 8080
