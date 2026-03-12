"""
Root conftest.py — stubs out modules that are not installed or not reachable in
the test environment so that service/router modules can be imported during unit
tests without a real database connection or external services.

Specifically:
  - `config`  : supplies DATABASE_URL without reading .env
  - `database`: prevents SQLAlchemy from attempting to connect to PostgreSQL
                (psycopg2 may not be installed, or the server may be absent)
  - `models`  : ORM models depend on a live engine via Base.metadata; stub them
  - `auth`    : depends on database + models at import time
"""
import sys
import types
from unittest.mock import MagicMock


def _stub(name: str, **attrs):
    """Insert a lightweight stub module into sys.modules."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── config ────────────────────────────────────────────────────────────────────
if "config" not in sys.modules:
    _stub("config", DATABASE_URL="postgresql://test:test@localhost/test")

# ── database ──────────────────────────────────────────────────────────────────
# Must be stubbed before any service module is imported, because
# `from database import SessionLocal` triggers create_engine() which requires
# psycopg2 (not always present in the test env).
if "database" not in sys.modules:
    _stub(
        "database",
        SessionLocal=MagicMock(),
        get_db=MagicMock(),
        Base=MagicMock(),
        engine=MagicMock(),
    )

# ── models ────────────────────────────────────────────────────────────────────
if "models" not in sys.modules:
    class _ChatMessage:
        """Minimal ChatMessage stub: stores constructor kwargs as attributes."""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    _stub(
        "models",
        Document=MagicMock(),
        DocumentChunk=MagicMock(),
        User=MagicMock(),
        ChatMessage=_ChatMessage,
    )

# ── auth ──────────────────────────────────────────────────────────────────────
if "auth" not in sys.modules:
    _stub("auth", get_current_user=MagicMock())