from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent / ".runtime" / str(os.getpid())
if TEST_ROOT.exists():
    shutil.rmtree(TEST_ROOT)
TEST_ROOT.mkdir(parents=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

os.environ["BUILI_ENVIRONMENT"] = "test"
os.environ["BUILI_DATABASE_URL"] = f"sqlite+aiosqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["BUILI_STORAGE_BACKEND"] = "local"
os.environ["BUILI_STORAGE_ROOT"] = str(TEST_ROOT / "storage")
os.environ["BUILI_MALWARE_SCANNER_BACKEND"] = "test"
os.environ["BUILI_PUBLIC_API_URL"] = "http://testserver"
os.environ["BUILI_JWT_SECRET"] = "test-secret-that-is-long-enough-for-jwt-signing"
os.environ["BUILI_DEMO_MODE"] = "true"
os.environ["BUILI_DEMO_EVIDENCE_PATH"] = str(Path(__file__).resolve().parents[3] / "buili_demo_evidence")
os.environ.pop("OPENAI_API_KEY", None)

import httpx  # noqa: E402
import pytest  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402

from buili_api.main import app  # noqa: E402


@pytest.fixture(scope="session")
async def client():
    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as value:
            yield value


@pytest.fixture(scope="session")
async def account(client: httpx.AsyncClient):
    response = await client.post(
        "/v1/auth/signup?transport=body",
        json={
            "email": "builder@example.com",
            "password": "ProductionTest123!",
            "display_name": "Avery Builder",
            "organization_name": "Avery Construction",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()["data"]
    return {
        "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        "refresh_token": payload["refresh_token"],
        "user": payload["user"],
    }
