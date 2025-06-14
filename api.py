import aiohttp

BINANCE_BASE = "https://api.binance.com/api/v3"

async def is_pair_valid(symbol: str) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BINANCE_BASE}/exchangeInfo") as resp:
            data = await resp.json()
    return symbol.upper() in {item['symbol'] for item in data.get('symbols', [])}

async def get_current_price(symbol: str) -> float:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BINANCE_BASE}/ticker/price?symbol={symbol}") as resp:
            data = await resp.json()
    return float(data['price'])

async def resolve_symbol(raw: str) -> str | None:
    """
    Пытается найти корректный символ:
      - raw (e.g. "BTC")
      - raw+USDT ("BTCUSDT")
    Возвращает валидный тикер или None.
    """
    sym = raw.upper()
    if await is_pair_valid(sym):
        return sym
    sym_usdt = sym + "USDT"
    if await is_pair_valid(sym_usdt):
        return sym_usdt
    return None