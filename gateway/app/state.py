"""Shared in-memory point store.

A plain dict is enough: FastAPI's event loop is single-threaded and cooperative, and every
writer here does a single atomic dict assignment with no `await` in between, so there's no
window for readers to see a half-written point. History (SQLite) lands in M6.
"""
from __future__ import annotations

points: dict[str, dict] = {}
