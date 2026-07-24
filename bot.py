import sqlite3
import asyncio
import datetime
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ⚙️ Загрузка токена
TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError(
        "🛑 Ошибка! Переменная окружения API_TOKEN не найдена.\nПроверьте настройки вашего сервера."
    )

DB_NAME = "casino.db"
DAILY_START = 10_000
DAILY_INCREMENT = 10_000  # пока не используется, можно задействовать позже


# --- БАЗА ДАННЫХ (синхронная, вызывается через run_in_executor) ---

def init_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 10000,
                    last_daily DATE,
                    current_game TEXT
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    price INTEGER,
                    description TEXT
                );
            ''')
            if cursor.execute('SELECT COUNT(*) FROM shop').fetchone()[0] == 0:
                items = [
                    ("Счастливая монета", 50_000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75_000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200_000, "Открывает эксклюзивные игры"),
                ]
                cursor.executemany('INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items)
        print("[INFO] Database initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")


def _get_user_sync(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Регистрируем пользователя, если его нет
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
            (user_id, "")
        )
        conn.commit()
        data = cursor.execute(
            'SELECT balance, last_daily, current_game FROM users WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        if data:
            return {"balance": data[0], "last_daily": data[1], "current_game": data[2]}
        return None


async def get_user(update):
    if isinstance(update, int):
        user_id = update
    else:
        user_id = update.effective_user.id
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_user_sync, user_id)


def _save_balance_sync(user_id: int, new_balance: int | None, game: str | None = None):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if new_balance is None:
            # Только сброс игры
            cursor.execute('UPDATE users SET current_game = NULL WHERE user_id = ?', (user_id,))
        elif game is not None:
            # Баланс + активная игра
            cursor.execute(
                'UPDATE users SET balance = ?, current_game = ? WHERE user_id = ?',
                (new_balance, game, user_id),
            )
        else:
            # Просто баланс, сбрасываем игру
            cursor.execute(
                'UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?',
                (new_balance, user_id),
            )
        conn.commit()


async def save_balance(user_id: int, new_balance: int | None, game: str | None = None):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _save_balance_sync, user_id, new_balance, game)


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = await get_user(update)
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="show_balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{update.effective_user.first_name}*!\nВыбери действие:"

    try:
        await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)
    except AttributeError:
        await update.callback_query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)


async def show_balance(query):
    # query — это CallbackQuery, у него есть .message и .from_user
    user_data = await get_user(query)
    if user_data is None:
        return

    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]]
    await query.edit_message_text(
        text=f"Твой текущий баланс:\n*{user_data['balance']:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def casino_keyboard(query):
    game_buttons = [
        [InlineKeyboardButton("Орел / Решка 🤏", callback_data="coin_flip")],
        [InlineKeyboardButton("Кости 🎲", callback_data="dice_roll")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")],
    ]
    await query.edit_message_text(
        text="*Выберите игру:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(game_buttons),
    )


# --- ОБРАБОТЧИК КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    match query.data:
        case "mainmenu":
            await main_menu(update, context)

        case "show_balance":
            await show_balance(query)

        case "daily":
            await daily(update, context)

        case "shop":
            await show_shop(query, context)

        case "casino":
            await casino_keyboard(query)

        case "coin_flip" | "dice_roll":
            game_name_map = {
                "coin_flip": "Орел / Решка 🤏",
                "dice_roll": "Кости 🎲",
            }
            game_name = game_name_map[query.data]
            user_data = await get_user(update)
            if user_data is None:
                return

            # Сохраняем активную игру в БД
            await save_balance(user_data["user_id"], None, game=query.data)

            msg = (
                f"Введите сумму ставки для игры \"*{game_name}*\":\n\n"
                f"Текущий баланс: *{user_data['balance']:,}* 🪙"
            )
            await query.edit_message_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

        case "cancel":
            # Отменяем активную игру
            user_data = await get_user(update)
            if user_data:
                await save_balance(user_data["user_id"], None, game=None)
                await query.edit_message_text("Ставка отменена. Возвращаемся в главное меню.", parse_mode="Markdown")
                await main_menu(update, context)
            else:
                await query.edit_message_text("Ошибка: пользователь не найден.")

        case "back_to_main":
            await main_menu(update, context)

        case buy_item if buy_item.startswith("buy_"):
            await process_purchase(update, context)


# --- ЛИДЕРЫ И ЕЖЕДНЕВНЫЙ БОНУС ---

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def _top_sync():
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
            return cursor.fetchall()

    leaders = await asyncio.to_thread(_top_sync)
    msg = "🏆 Топ самых богатых игроков:\n"
    for i, (username, bal) in enumerate(leaders, 1):
        name = username or "Аноним"
        msg += f"{i}. {name}: {bal:,} 🪙\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today().isoformat()
    user_data = await get_user(update)
    if user_data is None:
        return

    last_date_str = user_data["last_daily"]
    if last_date_str is None or str(last_date_str) != str(today):
        bonus = DAILY_START
        new_balance = user_data["balance"] + bonus

        # Обновляем баланс и дату бонуса
        def _daily_sync(user_id: int, balance: int, date_str: str):
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?",
                    (balance, date_str, user_id),
                )
                conn.commit()

        await asyncio.to_thread(_daily_sync, user_data["user_id"], new_balance, today)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Успех! Вы получили свой дневной бонус: *{bonus:,}* 🪙.\nНовый баланс: *{new_balance:,}* 🪙",
            parse_mode="Markdown",
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Вы уже забрали бонус сегодня.",
            parse_mode="Markdown",
        )


# --- МАГАЗИН ---

async def show_shop(query, context: ContextTypes.DEFAULT_TYPE):
    def _shop_sync():
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            rows = list(cur.execute("SELECT item_id, name, price FROM shop"))
            details = list(cur.execute("SELECT name, price, description FROM shop"))
        return rows, details

    buttons = []
    rows, details = await asyncio.to_thread(_shop_sync)

    for item_id, name, _price in rows:
        button_name = f"{name} \U0001f4b8 {_price:,}"
        buttons.append([InlineKeyboardButton(button_name, callback_data=f"buy_{item_id}")])

    buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")])

    text = "*Добро пожаловать в магазин!*\n"
    for name, price, desc in details:
        text += f"\n• {name}\nЦена: {price:,} 🪙\n{desc}"

    await query.edit_message_text(
        text=text,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, item_id_str = query.data.split("_")
    item_id = int(item_id_str)

    def _purchase_sync(item_id: int):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, price FROM shop WHERE item_id = ?", (item_id,))
            result = cursor.fetchone()
            return result

    result = await asyncio.to_thread(_purchase_sync, item_id)
    if not result:
        await query.edit_message_text("❌ Ошибка: товар не найден!")
        return

    item_name, item_price = result
    user_data = await get_user(update)
    if user_data is None:
        return

    current_balance = user_data["balance"]
    if current_balance < item_price:
        await query.edit_message_text(
            f"❌ Недостаточно средств для покупки '{item_name}'. Ваш баланс: {current_balance:,}",
            parse_mode="Markdown",
        )
        return

    new_balance = current_balance - item_price
    await save_balance(user_data["user_id"], new_balance)

    await query.edit_message_text(
        f"✅ Вы купили '{item_name}' за {item_price:,} монет!\nВаш новый баланс: *{new_balance:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    await main_menu(update, context)


# --- ИГРОПРОВОДНИК ---

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = await get_user(update)
    if user_data is None:
        return

    selected_game = user_data.get("current_game")
    if not selected_game:
        # Если нет активной игры — просто игнорируем или предлагаем меню
        await update.message.reply_text("Сначала выберите игру в казино.", parse_mode="Markdown")
        return

    bet_text = update.message.text.replace(",", "").replace(" ", "")
    try:
        bet = int(bet_text)
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите числовое значение.", parse_mode="Markdown")
        return

    if bet <= 0:
        await update.message.reply_text("Ставка должна быть больше нуля!", parse_mode="Markdown")
        return

    if bet > user_data["balance"]:
        await update.message.reply_text("❌ Недостаточно средств на балансе.", parse_mode="Markdown")
        return

    result_msg = ""
    win_amount = 0

    # Логика игр
    if selected_game == "coin_flip":
        choice = random.choice(["орёл", "решка"])
        coin = random.choice(["орёл", "решка"])
        won = choice == coin
        multiplier =

