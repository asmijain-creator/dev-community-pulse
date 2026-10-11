"""Root entrypoint for Vercel's FastAPI preset.

Vercel auto-detects FastAPI by looking for `app` in main.py / app.py at
the project root. We re-export it from api/index.py so the whole FastAPI
app (routes + lib imports) is served.
"""
from api.index import app

__all__ = ["app"]
