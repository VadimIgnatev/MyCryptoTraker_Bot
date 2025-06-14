import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("RAILWAY_POSTGRESQL_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в окружении")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL / RAILWAY_POSTGRESQL_URL не найдены")
