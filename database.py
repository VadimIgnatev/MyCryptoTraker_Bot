import asyncpg
from config import DATABASE_URL

async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    # Создаём таблицу с полем purchase_date (DATE)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            symbol TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            buy_price DOUBLE PRECISION NOT NULL,
            purchase_date DATE NOT NULL DEFAULT CURRENT_DATE
        );
    """)
    await conn.close()

async def add_transaction(chat_id: int, symbol: str, amount: float, buy_price: float, purchase_date):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO portfolio(chat_id, symbol, amount, buy_price, purchase_date) VALUES($1, $2, $3, $4, $5)",
        chat_id, symbol, amount, buy_price, purchase_date
    )
    await conn.close()

async def get_transactions(chat_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT id, symbol, amount, buy_price, purchase_date FROM portfolio WHERE chat_id = $1",
        chat_id
    )
    await conn.close()
    return [
        (r["id"], r["symbol"], r["amount"], r["buy_price"], r["purchase_date"])
        for r in rows
    ]

async def delete_transaction(tx_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM portfolio WHERE id = $1", tx_id)
    await conn.close()
