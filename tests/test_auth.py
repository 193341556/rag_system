import pytest


@pytest.mark.anyio
class TestAuth:

    # ── 正常流 ────────────────────────────────────────────────────────────

    async def test_register_success(self, client):
        """正常注册，返回 201 和用户信息。"""
        resp = await client.post(
            "/api/auth/register",
            json={"username": "newuser_001", "password": "pass123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["username"] == "newuser_001"

    async def test_login_success(self, client):
        """正常登录，返回 access_token。"""
        await client.post(
            "/api/auth/register",
            json={"username": "loginuser", "password": "pass123"},
        )
        resp = await client.post(
            "/api/auth/login",
            json={"username": "loginuser", "password": "pass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_token_is_string(self, client):
        """登录返回的 token 是非空字符串。"""
        await client.post(
            "/api/auth/register",
            json={"username": "tokenuser", "password": "pass123"},
        )
        resp = await client.post(
            "/api/auth/login",
            json={"username": "tokenuser", "password": "pass123"},
        )
        token = resp.json()["access_token"]
        assert isinstance(token, str)
        assert len(token) > 0

    # ── 异常流 ────────────────────────────────────────────────────────────

    async def test_register_duplicate_username(self, client):
        """重复注册同一用户名，返回 400。"""
        payload = {"username": "dupuser", "password": "pass123"}
        await client.post("/api/auth/register", json=payload)
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 400
        assert "已被注册" in resp.json()["detail"]

    async def test_login_wrong_password(self, client):
        """密码错误，返回 401。"""
        await client.post(
            "/api/auth/register",
            json={"username": "wrongpwuser", "password": "correct"},
        )
        resp = await client.post(
            "/api/auth/login",
            json={"username": "wrongpwuser", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        """不存在的用户名登录，返回 401。"""
        resp = await client.post(
            "/api/auth/login",
            json={"username": "ghost_user_xyz", "password": "any"},
        )
        assert resp.status_code == 401

    # ── 边界值 ────────────────────────────────────────────────────────────

    async def test_register_missing_password(self, client):
        """缺少 password 字段，返回 422。"""
        resp = await client.post(
            "/api/auth/register",
            json={"username": "nopwuser"},
        )
        assert resp.status_code == 422

    async def test_register_missing_username(self, client):
        """缺少 username 字段，返回 422。"""
        resp = await client.post(
            "/api/auth/register",
            json={"password": "pass123"},
        )
        assert resp.status_code == 422
