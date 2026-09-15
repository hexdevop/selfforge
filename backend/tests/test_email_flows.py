import re
from email.message import EmailMessage

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

PASSWORD = "super-secret-1"
REGISTER_PAYLOAD = {"email": "alice@example.com", "username": "alice", "password": PASSWORD}


def _token_from(message: EmailMessage) -> str:
    match = re.search(r"token=(\S+)", message.get_content())
    assert match is not None
    return match.group(1)


async def _login(client: AsyncClient, password: str = PASSWORD) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"login": "alice", "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]  # type: ignore[no-any-return]


async def test_register_sends_verification_and_link_verifies(
    client: AsyncClient, outbox: list[EmailMessage]
) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.json()["is_verified"] is False

    assert len(outbox) == 1
    assert outbox[0]["To"] == "alice@example.com"
    assert "/verify-email?token=" in outbox[0].get_content()

    verify = await client.post("/api/v1/auth/verify-email", json={"token": _token_from(outbox[0])})
    assert verify.status_code == 204

    token = await _login(client)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["is_verified"] is True


async def test_verify_email_rejects_garbage_and_foreign_token_types(
    client: AsyncClient,
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    access_token = await _login(client)

    for token in ("not-a-token", access_token):
        response = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_link"


async def test_resend_verification_requires_auth(
    client: AsyncClient, outbox: list[EmailMessage]
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert (await client.post("/api/v1/auth/verify-email/resend")).status_code == 401

    token = await _login(client)
    response = await client.post(
        "/api/v1/auth/verify-email/resend", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 202
    assert len(outbox) == 2


async def test_password_reset_for_unknown_email_looks_the_same(
    client: AsyncClient, outbox: list[EmailMessage]
) -> None:
    response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert response.status_code == 202
    assert outbox == []


async def test_password_reset_changes_password_once_and_revokes_sessions(
    client: AsyncClient, outbox: list[EmailMessage]
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    await _login(client)
    old_refresh = client.cookies["refresh_token"]

    await client.post("/api/v1/auth/password-reset/request", json={"email": "alice@example.com"})
    reset_token = _token_from(outbox[-1])
    new_password = "brand-new-pass-2"

    confirm = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": new_password},
    )
    assert confirm.status_code == 204

    reuse = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "another-pass-3"},
    )
    assert reuse.status_code == 400

    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    old_login = await client.post(
        "/api/v1/auth/login", json={"login": "alice", "password": PASSWORD}
    )
    assert old_login.status_code == 401
    await _login(client, new_password)
