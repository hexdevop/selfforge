import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

REGISTER_PAYLOAD = {
    "email": "alice@example.com",
    "username": "alice",
    "full_name": "Alice Doe",
    "password": "super-secret-1",
}


async def _register(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201


async def test_register(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["username"] == REGISTER_PAYLOAD["username"]
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_rejected(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "username": "someone-else"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "already_exists"
    assert "email" in detail["fields"]


@pytest.mark.parametrize("login", ["alice@example.com", "alice"])
async def test_login_by_email_or_username(client: AsyncClient, login: str) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/auth/login", json={"login": login, "password": REGISTER_PAYLOAD["password"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/auth/login", json={"login": "alice", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"


async def test_validation_error_uses_unified_format(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "password": "short"}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "validation_error"
    assert "password" in detail["fields"]


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient) -> None:
    await _register(client)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "alice", "password": REGISTER_PAYLOAD["password"]},
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


async def test_refresh_rotates_token_and_old_one_stops_working(client: AsyncClient) -> None:
    await _register(client)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "alice", "password": REGISTER_PAYLOAD["password"]},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["refresh_token"] != old_refresh_token

    reuse_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert reuse_response.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await _register(client)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "alice", "password": REGISTER_PAYLOAD["password"]},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logout_response.status_code == 204

    reuse_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert reuse_response.status_code == 401
