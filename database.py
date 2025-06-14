import asyncio
import asyncpg
from config import DATABASE_URL

async def init_db():
    # Ждём готовности БД (до 10 попыток)
    conn = None
    for i in range(10):
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            break
        except Exception:
            await asyncio.sleep(2)
    if not conn:
        raise RuntimeError("Не удалось подключиться к БД")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            coin TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            buy_price DOUBLE PRECISION NOT NULL,
            date DATE NOT NULL
        )
    """)
    # По желанию: таблица для снэпшотов
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            total_value DOUBLE PRECISION NOT NULL,
            ts TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.close()

async def add_transaction(user_id: int, coin: str, amount: float, buy_price: float, date):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO portfolio (user_id, coin, amount, buy_price, date) VALUES ($1,$2,$3,$4,$5)",
        user_id, coin, amount, buy_price, date
    )
    await conn.close()

async def get_portfolio(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT coin, SUM(amount) AS amt, AVG(buy_price) AS avgp "
        "FROM portfolio WHERE user_id=$1 GROUP BY coin",
        user_id
    )
    await conn.close()
    return [(r["coin"], r["amt"], r["avgp"]) for r in rows]

async def get_all_chat_ids():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT DISTINCT user_id FROM portfolio")
    await conn.close()
    return [r["user_id"] for r in rows]

async def add_snapshot(user_id: int, total_value: float):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO snapshots (user_id, total_value) VALUES ($1,$2)",
        user_id, total_value
    )
    await conn.close()
