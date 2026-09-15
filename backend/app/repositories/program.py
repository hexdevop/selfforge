from app.models.program import Program
from app.repositories.base import BaseRepository


class ProgramRepository(BaseRepository[Program]):
    model = Program
