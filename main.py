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
import database, api

logging.basicConfig(level=logging.INFO)

class AddTx(StatesGroup):
    waiting_for_data = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить транзакцию",   callback_data="add_transaction")],
        [InlineKeyboardButton(text="💼 Показать портфель",     callback_data="show_portfolio")],
        [InlineKeyboardButton(text="✏️ Редактировать",         callback_data="edit_transactions")],
        [InlineKeyboardButton(text="📊 Доля в портфеле",       callback_data="allocation")],
        [InlineKeyboardButton(text="📝 Сводка инвестиций",     callback_data="summary")],
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
async def add_transaction_cb(cq: CallbackQuery, state: FSMContext):
    text = (
        "📥 Введи через пробел: SYMBOL AMOUNT PRICE [YYYY-MM-DD]\n"
        "Пример: <b>BTC 0.02 50000 2024-06-11</b>\n"
        "Если дата не указана — будет сегодня."
    )
    await cq.message.edit_text(text, parse_mode="HTML")
    await state.set_state(AddTx.waiting_for_data)
    await cq.answer()

@dp.callback_query(F.data == "allocation")
async def allocation_cb(cq: CallbackQuery):
    # Получаем все транзакции пользователя
    recs = await database.get_transactions(cq.message.chat.id)
    if not recs:
        await cq.answer("Портфель пуст.", show_alert=True)
        return

    # Считаем стоимость по монетам
    data: dict[str, float] = {}
    for _, symbol, amount, buy_price, _ in recs:
        price = await api.get_current_price(symbol)
        data[symbol] = data.get(symbol, 0.0) + price * amount

    total = sum(data.values())
    # Сортируем по убыванию стоимости
    sorted_items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)

    lines = []
    for idx, (symbol, value) in enumerate(sorted_items, start=1):
        pct = value / total * 100
        if idx == 1:
            emoji = "🥇"
        elif idx == 2:
            emoji = "🥈"
        elif idx == 3:
            emoji = "🥉"
        else:
            emoji = "🔹"
        lines.append(f"{emoji} {symbol} — {pct:.1f}% ({value:.2f} USDT)")

    text = "📊 <b>Доля в портфеле:</b>\n\n" + "\n".join(lines)
    # прикрепляем кнопку «Назад»
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await cq.answer()

@dp.callback_query(F.data == "summary")
async def summary_cb(cq: CallbackQuery):
    recs = await database.get_transactions(cq.message.chat.id)
    if not recs:
        await cq.answer("Портфель пуст.", show_alert=True)
        return

    invested = 0.0
    current_value = 0.0
    for _id, symbol, amount, buy_price, _ in recs:
        invested += amount * buy_price
        price = await api.get_current_price(symbol)
        current_value += amount * price

    pnl = current_value - invested
    pct = (pnl / invested * 100) if invested else 0.0

    text = (
        f"📝 <b>Сводка инвестиций</b>\n\n"
        f"💰 Всего инвестировано: <b>{invested:.2f} USDT</b>\n"
        f"📈 Текущая стоимость: <b>{current_value:.2f} USDT</b>\n"
        f"🔀 PnL: <b>{pnl:+.2f} USDT</b> (<b>{pct:+.2f}%</b>)"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cq.answer()


@dp.message(AddTx.waiting_for_data)
async def process_tx(message: Message, state: FSMContext):
    parts = message.text.split()
    if len(parts) not in (3, 4):
        return await message.reply("Неверный формат. Попробуй ещё раз.")
    raw, a_str, p_str = parts[:3]
    d_str = parts[3] if len(parts) == 4 else None

    try:
        amount = float(a_str)
        buy_price = float(p_str)
    except ValueError:
        return await message.reply("Количество и цена должны быть числами.")

    if d_str:
        try:
            purchase_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            return await message.reply("Дата должна быть в формате YYYY-MM-DD.")
    else:
        purchase_date = date.today()

    symbol = await api.resolve_symbol(raw)
    if not symbol:
        await state.clear()
        return await message.reply("Неизвестный тикер.")

    await database.add_transaction(
        message.chat.id, symbol, amount, buy_price, purchase_date
    )
    await message.reply(
        f"✅ Добавлено: {symbol} {amount} @ {buy_price} ({purchase_date})"
    )
    await state.clear()
    await message.answer("Что дальше?", reply_markup=main_menu())

@dp.callback_query(F.data == "show_portfolio")
async def show_portfolio_cb(cq: CallbackQuery):
    recs = await database.get_transactions(cq.message.chat.id)
    if not recs:
        await cq.answer()
        return await cq.message.answer("📭 Портфель пуст.", reply_markup=main_menu())

    summary = {}
    for _id, sym, amt, bp, dt in recs:
        rec = summary.setdefault(sym, {"amt": 0.0, "cost": 0.0})
        rec["amt"] += amt
        rec["cost"] += amt * bp

    lines = []
    total_cost = 0.0
    total_pnl = 0.0
    for sym, rec in summary.items():
        avg = rec["cost"] / rec["amt"]
        cur = await api.get_current_price(sym)
        pnl = (cur - avg) * rec["amt"]
        total_cost += rec["cost"]
        total_pnl += pnl
        pct = (cur / avg - 1) * 100

        lines.append(
            f"<b>{sym}</b>\n"
            f"  Кол-во: {rec['amt']:.6f} @ avg {avg:.2f}\n"
            f"  Текущая цена: {cur:.2f} USDT\n"
            f"  Стоимость сейчас: {cur * rec['amt']:.2f} USDT\n"
            f"  PnL: {pnl:.2f} USDT ({pct:.2f}% )"
        )

    overall_pct = (total_pnl / total_cost) * 100 if total_cost else 0.0
    text = "\n\n".join(lines) + f"\n\n<b>Общий PnL:</b> {total_pnl:.2f} USDT ({overall_pct:.2f}% )"
    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    await cq.answer()

@dp.callback_query(F.data == "edit_transactions")
async def edit_transactions_cb(cq: CallbackQuery):
    recs = await database.get_transactions(cq.message.chat.id)
    if not recs:
        await cq.answer()
        return await cq.message.edit_text("Нет транзакций.", reply_markup=main_menu())

    buttons = []
    for tx_id, sym, amt, bp, dt in recs:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {sym} {amt}@{bp} ({dt})",
                callback_data=f"del_{tx_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await cq.message.edit_text("Выбери для удаления:", reply_markup=kb)
    await cq.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_tx_cb(cq: CallbackQuery):
    tx = int(cq.data.split("_")[1])
    await database.delete_transaction(tx)
    await cq.answer("Удалено")
    return await edit_transactions_cb(cq)

@dp.callback_query(F.data == "main_menu")
async def back_to_main(cq: CallbackQuery):
    await cq.message.edit_text("Выбери действие:", reply_markup=main_menu())
    await cq.answer()


async def take_snapshot():
    chat_ids = await database.get_all_chat_ids()
    for chat_id in chat_ids:
        recs = await database.get_transactions(chat_id)
        total = 0.0
        for _, sym, amt, _, _ in recs:
            total += await api.get_current_price(sym) * amt
        await database.add_snapshot(chat_id, total)

async def main():
    await database.init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(take_snapshot, 'interval', hours=6)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
