"""Root entrypoint for Vercel's FastAPI preset, which looks for `app` in main.py."""
from api.index import app

__all__ = ["app"]
