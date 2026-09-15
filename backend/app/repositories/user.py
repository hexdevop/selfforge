from sqlalchemy import or_, select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.get_by(email=email)

    async def get_by_username(self, username: str) -> User | None:
        return await self.get_by(username=username)

    async def get_by_login(self, login: str) -> User | None:
        """Look up a user by email or username — whichever `login` matches."""
        stmt = select(User).where(or_(User.email == login, User.username == login))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
