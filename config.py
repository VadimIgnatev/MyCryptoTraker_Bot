import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
# берем либо стандартный DATABASE_URL (если вы все же его связали),
# либо подставляем Railway Provided
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("RAILWAY_POSTGRESQL_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в окружении")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL и RAILWAY_POSTGRESQL_URL не найдены — проверьте переменные Railway"
    )
