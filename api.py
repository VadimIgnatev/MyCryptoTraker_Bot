import asyncio
from binance import AsyncClient, BinanceAPIException

# Минимальный клиент-одиночка
_client = None

async def _get_client():
    global _client
    if _client is None:
        _client = await AsyncClient.create()
    return _client

async def is_pair_valid(symbol: str) -> bool:
    client = await _get_client()
    try:
        await client.get_symbol_ticker(symbol=symbol)
        return True
    except BinanceAPIException:
        return False

async def get_current_price(symbol: str) -> float:
    client = await _get_client()
    data = await client.get_symbol_ticker(symbol=symbol)
    return float(data["price"])
