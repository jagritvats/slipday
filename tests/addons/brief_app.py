"""The entry's app with the brief router included, for tests and the browser check until api.py registers it.

    python -m uvicorn tests.addons.brief_app:app --port 8481
"""
from slipday.api import app
from slipday.addons import brief

if not any(getattr(r, "path", "") == "/api/addons/brief" for r in app.routes):
    app.include_router(brief.router)
