import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, close_db


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    """CI环境里手动建表。"""
    await init_db()
    yield
    await close_db()


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
async def auth_token(client):
    """注册 + 登录，返回 access_token。密码用短字符串避免 bcrypt 72字节限制。"""
    await client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "Test1234"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "Test1234"},
    )
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture(scope="session", autouse=True)
async def flush_redis():
    """每次测试session开始时清空Redis缓存，避免上次残留影响。"""
    import redis
    r = redis.Redis(host="localhost", port=6379, db=0)
    r.flushdb()
    yield
