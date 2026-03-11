"""
Root conftest.py — stubs out modules that are not installed in the test
environment (sqlalchemy, fastapi, etc.) so that service modules can be
imported during unit tests without a real database or web framework.
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


# ── sqlalchemy ────────────────────────────────────────────────────────────────
if "sqlalchemy" not in sys.modules:
    sa = _stub("sqlalchemy")
    sa.text = MagicMock(side_effect=lambda q: q)  # passthrough for SQL strings
    sa.Column = MagicMock()
    sa.Integer = MagicMock()
    sa.String = MagicMock()
    sa.Text = MagicMock()
    sa.DateTime = MagicMock()
    sa.Boolean = MagicMock()
    sa.ForeignKey = MagicMock()
    sa.create_engine = MagicMock()

    sa_orm = _stub("sqlalchemy.orm")
    sa_orm.sessionmaker = MagicMock()
    sa_orm.declarative_base = MagicMock(return_value=MagicMock())
    sa_orm.Session = MagicMock()
    sa_orm.relationship = MagicMock()

    _stub("sqlalchemy.dialects")
    _stub("sqlalchemy.dialects.postgresql")

# ── database (our own module — depends on sqlalchemy) ────────────────────────
if "database" not in sys.modules:
    db_mod = _stub(
        "database",
        SessionLocal=MagicMock(),
        get_db=MagicMock(),
        Base=MagicMock(),
        engine=MagicMock(),
    )

# ── models (depends on sqlalchemy + database) ────────────────────────────────
if "models" not in sys.modules:
    _stub(
        "models",
        Document=MagicMock(),
        DocumentChunk=MagicMock(),
        User=MagicMock(),
    )

# ── fastapi ───────────────────────────────────────────────────────────────────
if "fastapi" not in sys.modules:
    fa = _stub("fastapi")
    fa.FastAPI = MagicMock()
    fa.APIRouter = MagicMock()
    fa.Depends = MagicMock()
    fa.HTTPException = type("HTTPException", (Exception,), {"status_code": None, "detail": None})
    fa.BackgroundTasks = MagicMock()
    fa.status = types.SimpleNamespace(
        HTTP_200_OK=200,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_422_UNPROCESSABLE_ENTITY=422,
    )

    _stub("fastapi.middleware")
    cors = _stub("fastapi.middleware.cors")
    cors.CORSMiddleware = MagicMock()

    _stub("fastapi.testclient")  # real httpx is present, so TestClient may work

# ── starlette ─────────────────────────────────────────────────────────────────
if "starlette" not in sys.modules:
    _stub("starlette")
    _stub("starlette.testclient")

# ── config (our own module — reads DATABASE_URL) ─────────────────────────────
if "config" not in sys.modules:
    _stub("config", DATABASE_URL="postgresql://test:test@localhost/test")

# ── auth (our own module) ─────────────────────────────────────────────────────
if "auth" not in sys.modules:
    _stub("auth", get_current_user=MagicMock())