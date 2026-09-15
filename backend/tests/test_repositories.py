import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.schemas.pagination import PageParams

pytestmark = pytest.mark.asyncio


async def _seed_users(session: AsyncSession, repo: UserRepository, count: int) -> None:
    for i in range(count):
        await repo.create(
            email=f"user{i}@example.com",
            username=f"user{i}",
            hashed_password="hashed",
            is_active=i % 2 == 0,
        )
    await session.commit()


async def test_pagination_returns_correct_page(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    await _seed_users(db_session, repo, count=5)

    page = await repo.list(pagination=PageParams(page=2, size=2))

    assert page.total == 5
    assert page.pages == 3
    assert len(page.items) == 2


async def test_filters_support_lookup_operators(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    await _seed_users(db_session, repo, count=5)

    active_only = await repo.list(filters={"is_active": True})
    assert active_only.total == 3

    ilike_match = await repo.list(filters={"email__ilike": "%USER1%"})
    assert ilike_match.total == 1
    assert ilike_match.items[0].username == "user1"


async def test_get_by_login_matches_email_or_username(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    await repo.create(email="bob@example.com", username="bob", hashed_password="hashed")
    await db_session.commit()

    by_email = await repo.get_by_login("bob@example.com")
    by_username = await repo.get_by_login("bob")

    assert by_email is not None and by_username is not None
    assert by_email.id == by_username.id
