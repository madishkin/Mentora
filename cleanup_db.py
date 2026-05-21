import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def cleanup():
    engine = create_async_engine(
        "postgresql+asyncpg://educraft:educraft_pass@localhost:5433/educraft"
    )
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS usage_records CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS jobs CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS user_quotas CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS user_role CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS file_type CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS document_status CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS job_status CASCADE"))
    await engine.dispose()
    print("Database cleaned!")

asyncio.run(cleanup())
