import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _create_user(
    db_session: AsyncSession, *, username: str, is_superuser: bool = False
) -> User:
    user = User(
        email=f"{username}@example.com",
        username=username,
        hashed_password=hash_password("super-secret-1"),
        is_superuser=is_superuser,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"login": username, "password": "super-secret-1"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]  # type: ignore[no-any-return]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_list_users_requires_superuser(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, username="regular")
    token = await _login(client, "regular")

    response = await client.get("/api/v1/users", headers=_auth_headers(token))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


async def test_list_users_as_superuser(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, username="admin", is_superuser=True)
    await _create_user(db_session, username="regular")
    token = await _login(client, "admin")

    response = await client.get("/api/v1/users", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_get_user_is_cached(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await _create_user(db_session, username="cached")
    token = await _login(client, "cached")

    first = await client.get(f"/api/v1/users/{user.id}", headers=_auth_headers(token))
    second = await client.get(f"/api/v1/users/{user.id}", headers=_auth_headers(token))

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


async def test_user_can_update_own_profile(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await _create_user(db_session, username="self-editor")
    token = await _login(client, "self-editor")

    response = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"full_name": "Updated Name"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


async def test_user_cannot_update_others_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    victim = await _create_user(db_session, username="victim")
    await _create_user(db_session, username="attacker")
    token = await _login(client, "attacker")

    response = await client.patch(
        f"/api/v1/users/{victim.id}",
        json={"full_name": "Hacked"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 403


async def test_delete_user_requires_superuser(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    target = await _create_user(db_session, username="target")
    await _create_user(db_session, username="regular")
    token = await _login(client, "regular")

    response = await client.delete(f"/api/v1/users/{target.id}", headers=_auth_headers(token))

    assert response.status_code == 403
