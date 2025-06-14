import logging
import asyncio
from datetime import datetime, date

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
import database
import api  # содержит is_pair_valid и get_current_price

logging.basicConfig(level=logging.INFO)

class AddTx(StatesGroup):
    waiting_for_data = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Добавить транзакцию",   callback_data="add_transaction")],
        [InlineKeyboardButton("💼 Показать портфель",     callback_data="show_portfolio")],
        [InlineKeyboardButton("✏️ Редактировать",         callback_data="edit_transactions")],
        [InlineKeyboardButton("📊 Доля в портфеле",       callback_data="allocation")],
        [InlineKeyboardButton("📝 Сводка инвестиций",     callback_data="summary")],
    ])

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await database.init_db()
    await message.answer(
        "Приветствую, крипто-гений! 💡\n\n"
        "Веди учёт сделок, следи за долями и получай сводку инвестиций! "
        "Все инструменты для умного инвестора собраны в одном боте.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "add_transaction")
async def add_tx_cb(cq: CallbackQuery, state: FSMContext):
    await cq.message.edit_text(
        "📥 Введи через пробел: SYMBOL AMOUNT PRICE [YYYY-MM-DD]\n"
        "Пример: <b>BTC 0.02 50000 2024-06-11</b>\n"
        "Если дата не указана — будет сегодня.",
        parse_mode="HTML"
    )
    await state.set_state(AddTx.waiting_for_data)
    await cq.answer()

@dp.message(AddTx.waiting_for_data)
async def process_tx(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) not in (3, 4):
        return await message.reply("❌ Неверный формат. Попробуйте ещё раз.")

    raw, a_str, p_str = parts[:3]
    d_str = parts[3] if len(parts) == 4 else None

    try:
        amount = float(a_str.replace(",", "."))
        buy_price = float(p_str.replace(",", "."))
    except ValueError:
        return await message.reply("❌ Количество и цена должны быть числами.")

    if d_str:
        try:
            purchase_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            return await message.reply("❌ Дата должна быть в формате YYYY-MM-DD.")
    else:
        purchase_date = date.today()

    symbol = raw.upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"

    if not await api.is_pair_valid(symbol):
        await state.clear()
        return await message.reply(f"❌ Пара {symbol} недоступна на Binance.")

    await database.add_transaction(
        user_id=message.chat.id,
        coin=symbol,
        amount=amount,
        buy_price=buy_price,
        date=purchase_date
    )

    await message.reply(f"✅ Добавлено: {symbol} {amount} @ {buy_price} ({purchase_date})")
    await state.clear()
    await message.answer("Что дальше?", reply_markup=main_menu())

@dp.callback_query(F.data == "show_portfolio")
async def show_portfolio_cb(cq: CallbackQuery):
    recs = await database.get_portfolio(cq.message.chat.id)
    if not recs:
        await cq.message.edit_text("📉 Портфель пуст.", reply_markup=main_menu())
    else:
        lines = []
        total_pnl = 0
        for coin, amt, avg in recs:
            cur = await api.get_current_price(coin)
            pnl = (cur - avg) * amt
            pct = pnl / (avg * amt) * 100
            lines.append(
                f"<b>{coin}</b>:\n"
                f"  • Кол-во: {amt}\n"
                f"  • avg: {avg:.2f}\n"
                f"  • тек: {cur:.2f}\n"
                f"  • PnL: {pnl:+.2f} USDT ({pct:+.2f}%)\n"
            )
            total_pnl += pnl
        text = "\n".join(lines) + f"\n<b>Общий PnL:</b> {total_pnl:.2f} USDT"
        await cq.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    await cq.answer()

@dp.callback_query(F.data == "edit_transactions")
async def edit_transactions_cb(cq: CallbackQuery):
    recs = await database.get_all_transactions(cq.message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(f"{r['coin']} {r['amount']} @ {r['buy_price']}", callback_data=f"del_{r['id']}")]
        for r in recs
    ] + [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
    await cq.message.edit_text("Выберите сделку для удаления:", reply_markup=kb)
    await cq.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_tx_cb(cq: CallbackQuery):
    tx_id = int(cq.data.split("_", 1)[1])
    await database.delete_transaction(tx_id)
    await cq.answer("✅ Удалено")
    return await edit_transactions_cb(cq)

@dp.callback_query(F.data == "allocation")
async def allocation_cb(cq: CallbackQuery):
    recs = await database.get_portfolio(cq.message.chat.id)
    if not recs:
        text = "📉 Портфель пуст."
    else:
        # считаем сумму текущей стоимости
        vals = [(coin, amt * await api.get_current_price(coin)) for coin, amt, _ in recs]
        total = sum(v for _, v in vals)
        # сортируем по убыванию
        vals.sort(key=lambda x: x[1], reverse=True)
        text = "📊 Доля в портфеле:\n\n" + "\n".join(
            f"🔹 {coin}: {v/total*100:.2f}%"
            for coin, v in vals
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ])
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()

@dp.callback_query(F.data == "summary")
async def summary_cb(cq: CallbackQuery):
    recs = await database.get_portfolio(cq.message.chat.id)
    if not recs:
        text = "📉 Нет данных для сводки."
    else:
        lines = []
        invested = 0
        current = 0
        for coin, amt, avg in recs:
            inv = amt * avg
            curv = amt * await api.get_current_price(coin)
            lines.append(f"• {coin}: вложено {inv:.2f} USDT, сейчас {curv:.2f} USDT")
            invested += inv
            current += curv
        lines.append(f"\n<b>Всего вложено:</b> {invested:.2f} USDT")
        lines.append(f"<b>Текущий портфель:</b> {current:.2f} USDT")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ])
    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cq.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(cq: CallbackQuery):
    await cq.message.edit_text("Что дальше?", reply_markup=main_menu())
    await cq.answer()

async def take_snapshot():
    for uid in await database.get_all_chat_ids():
        recs = await database.get_portfolio(uid)
        total = sum(amt * await api.get_current_price(coin) for coin, amt, _ in recs)
        await database.add_snapshot(uid, total)

async def main():
    await database.init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(take_snapshot, "interval", hours=6)
    scheduler.start()
    logging.info("Старт polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
