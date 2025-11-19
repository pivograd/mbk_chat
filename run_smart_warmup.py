import asyncio
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from openai_agents.crons.smart_warm_up import smart_warm_up
from settings import DATABASE_URL


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        await smart_warm_up(session)

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
