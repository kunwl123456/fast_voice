import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _env():
    # Ensure repo root is importable as a package root (so `import app.*` works)
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Ensure settings are loaded with test-friendly values BEFORE importing app
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_fast_voice.db")
    os.environ.setdefault("DATABASE_URL_SYNC", "sqlite+pysqlite:///./test_fast_voice.db")
    os.environ.setdefault("AUTO_CREATE_DB", "1")
    os.environ.setdefault("ADMIN_BOOTSTRAP", "1")
    os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
    os.environ.setdefault("ADMIN_PASSWORD", "admin12345")
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
    os.environ.setdefault("API_SECRET_ENC_KEY", "test-enc-key")
    os.environ.setdefault("CREDIT_PRICE_PER_UTF8_BYTE", "1")
    os.environ.setdefault("SIGNATURE_TIME_WINDOW_SECONDS", "300")
    os.environ.setdefault("MAX_TEXT_UTF8_BYTES", "2000")
    yield


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


