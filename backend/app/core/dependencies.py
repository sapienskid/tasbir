from fastapi import Request

from app.db.session import AsyncSession, async_sessionmaker


async def get_db(request: Request) -> AsyncSession:
    pool: async_sessionmaker[AsyncSession] = request.app.state.pool
    async with pool() as session:
        yield session
