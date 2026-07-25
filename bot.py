import sqlite3  # Для работы с базой данных SQLite
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import datetime
import random


# ⚙️ Загрузка токена из системной переменной API_TOKEN
import os
TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError(
        "🛑 Ошибка! Переменная окружения API_TOKEN не найдена."
        "\nПроверьте настройки вашего сервера."
    )


# --- НАСТРОЙКИ ---
DB_NAME = "casino.db"
DAILY_START = 10_000   # Начальный бонус за день
DAILY_INCREMENT = 10_000  # Прибавка за каждый пропущенный день


# --- БАЗА ДАННЫХ ---
def init_db():
    """Инициализация базы данных"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Создадим таблицу пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 10000,
                    last_daily DATE,
                    current_game TEXT
                );
            ''')
            
            # Таблица магазина предметов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    price INTEGER,
                    description TEXT
                );
            ''')
            
            # Заполним магазин базовыми предметами, если он пуст
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


async def get_user(update):
    """
    Получаем данные пользователя из базы.
    Возвращает словарь с ключами: user_id, username, balance, last_daily, current_game
    """
    try:
        # Определяем user_id
        if isinstance(update, int):
            user_id = update
        elif hasattr(update, 'effective_user'):
            user_id = update.effective_user.id
        elif hasattr(update, 'from_user'):  # Для callback_query
            user_id = update.from_user.id
        else:
            # Пробуем получить user_id из message
            user_id = update.message.from_user.id

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Получаем username
            username = ""
            if hasattr(update, 'effective_user') and update.effective_user.username:
                username = update.effective_user.username
            
            # Проверяем/добавляем пользователя
            cursor.execute(
                'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
                (user_id, username)
            )
            
            # Обновляем username, если он изменился
            if username:
                cursor.execute(
                    'UPDATE users SET username = ? WHERE user_id = ? AND username != ?',
                    (username, user_id, username)
                )
            
            conn.commit()
            
            # Берём все данные пользователя
            data = cursor.execute(
                'SELECT user_id, username, balance, last_daily, current_game FROM users WHERE user_id = ?',
                (user_id,)
            ).fetchone()
        
        if data:
            return {
                "user_id": data[0],
                "username": data[1],
                "balance": data[2],
                "last_daily": data[3],
                "current_game": data[4]
            }
        return None
    except Exception as e:
        print(f"❗️ Error in DB query: {str(e)}")
        return None


async def save_balance(user_id: int, new_balance: int | None):
    """
    Обновляет баланс пользователя.
    Если передан None вместо new_balance — сбрасывает поле current_game.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()

            if new_balance is None:
                cursor.execute(
                    'UPDATE users SET current_game = NULL WHERE user_id = ?',
                    (user_id,)
                )
            else:
                cursor.execute(
                    'UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?',
                    (new_balance, user_id),
                )
            conn.commit()
    except Exception as e:
        print(f"❗️ Error saving balance for user {user_id}: {str(e)}")


async def set_current_game(user_id: int, game_name: str):
    """Устанавливает текущую игру пользователя"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET current_game = ? WHERE user_id = ?',
                (game_name, user_id)
            )
            conn.commit()
    except Exception as e:
        print(f"❗️ Error setting game for user {user_id}: {str(e)}")


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками."""
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="show_balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{update.effective_user.first_name}*!\nВыбери действие:"

    try:
        # Если это команда /start
        await update.message.reply_text(
            text, 
            parse_mode=constants.ParseMode.MARKDOWN, 
            reply_markup=reply_markup
        )
    except AttributeError:
        # Если это callback (кнопка "Назад")
        query = update.callback_query
        await query.edit_message_text(
            text, 
            parse_mode=constants.ParseMode.MARKDOWN, 
            reply_markup=reply_markup
        )


async def show_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает баланс пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_data = await get_user(update)
    if user_data is None:
        await query.edit_message_text("❌ Ошибка получения данных.")
        return

    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]]

    await query.edit_message_text(
        text=f"Твой текущий баланс:\n*{user_data['balance']:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def casino_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню казино"""
    query = update.callback_query
    await query.answer()
    
    game_buttons = [
        [InlineKeyboardButton("Орел / Решка 🤏", callback_data="coin_flip")],
        [InlineKeyboardButton("Кости 🎲", callback_data="dice_roll")],
        [InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")],
    ]

    await query.edit_message_text(
        text="*Выберите игру:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(game_buttons),
    )


async def game_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает ставку для выбранной игры"""
    query = update.callback_query
    await query.answer()
    
    game_names = {
        "coin_flip": "Орел / Решка 🤏",
        "dice_roll": "Кости 🎲",
    }
    
    game_name = game_names.get(query.data, "Неизвестная игра")
    
    user_data = await get_user(update)
    if user_data is None:
        return
    
    # Сохраняем выбранную игру в БД
    await set_current_game(user_data['user_id'], query.data)
    
    keyboard = [[InlineKeyboardButton("↩️ Отмена", callback_data="cancel_bet")]]
    
    msg = (
        f"Введите сумму ставки для игры \"*{game_name}*\":\n\n"
        f"Текущий баланс: *{user_data['balance']:,}* 🪙"
    )
    
    await query.edit_message_text(
        msg, 
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- ОБРАБОТЧИК КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик всех кнопок"""
    query = update.callback_query
    await query.answer()

    if query.data == "mainmenu":
        await main_menu(update, context)
    elif query.data == "show_balance":
        await show_balance_handler(update, context)
    elif query.data == "daily":
        await daily_handler(update, context)
    elif query.data == "shop":
        await show_shop(update, context)
    elif query.data == "casino":
        await casino_keyboard_handler(update, context)
    elif query.data in ["coin_flip", "dice_roll"]:
        await game_bet_handler(update, context)
    elif query.data == "cancel_bet":
        user_data = await get_user(update)
        if user_data:
            await save_balance(user_id=user_data["user_id"], new_balance=None)
            await query.edit_message_text("❌ Ставка отменена.")
    elif query.data.startswith("buy_"):
        await process_purchase(update, context)


# --- ЛИДЕРЫ И ЕЖЕДНЕВНЫЙ БОНУС ---

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает топ-10 игроков"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    msg = "🏆 Топ самых богатых игроков:\n"
    for i, (username, bal) in enumerate(leaders, 1):
        name = username if username else "Аноним"
        msg += f"{i}. {name}: {bal:,} 🪙\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ежедневного бонуса"""
    query = update.callback_query
    await query.answer()
    
    today = datetime.date.today().isoformat()
    
    user_data = await get_user(update)
    if user_data is None:
        await query.edit_message_text("❌ Ошибка получения данных.")
        return

    last_date_str = user_data["last_daily"]

    if last_date_str is None or str(last_date_str) != str(today):
        bonus = DAILY_START
        new_balance = user_data["balance"] + bonus

        # Обновляем баланс и дату последнего бонуса
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?',
                    (new_balance, today, user_data["user_id"])
                )
                conn.commit()
        except Exception as e:
            print(f"❗️ Error updating daily bonus: {str(e)}")
            await query.edit_message_text("❌ Ошибка при начислении бонуса.")
            return

        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]]
        
        await query.edit_message_text(
            f"✅ Успех! Вы получили свой дневной бонус: *{bonus:,}* 🪙.\n"
            f"Новый баланс: *{new_balance:,}* 🪙",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]]
        
        await query.edit_message_text(
            "❌ Вы уже забрали бонус сегодня.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# --- МАГАЗИН ---

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает магазин"""
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    buttons = []
    for row in cur.execute("SELECT item_id, name, price FROM shop"):
        item_id, name, price = row
        button_name = f"{name} 💰 {price:,}"
        buttons.append([InlineKeyboardButton(button_name, callback_data=f"buy_{item_id}")])

    # Кнопка возврата
    buttons.append(
        [InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]
    )

    # Текст со списком товаров
    text = "*Добро пожаловать в магазин!*\n"
    for name, price, desc in cur.execute("SELECT name, price, description FROM shop"):
        text += f"\n• {name}\nЦена: {price:,} 🪙\n{desc}"

    conn.close()

    await query.edit_message_text(
        text=text,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает покупку товара"""
    query = update.callback_query
    await query.answer()

    _, item_id = query.data.split("_")
    item_id = int(item_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM shop WHERE item_id = ?", (item_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await query.edit_message_text("Ошибка: товар не найден!")
        return

    item_name, item_price = result

    user_data = await get_user(update)
    if user_data is None:
        return

    current_balance = user_data["balance"]

    if current_balance < item_price:
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="shop")]]
        await query.edit_message_text(
            f"❌ Недостаточно средств для покупки '{item_name}'. "
            f"Ваш баланс: {current_balance:,}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Покупка успешна
    new_balance = current_balance - item_price
    await save_balance(user_id=user_data["user_id"], new_balance=new_balance)

    keyboard = [[InlineKeyboardButton("↩️ В главное меню", callback_data="mainmenu")]]
    
    await query.edit_message_text(
        f"✅ Вы купили '{item_name}' за {item_price:,} монет!\n"
        f"Ваш новый баланс: *{new_balance:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- ОБРАБОТКА СТАВОК ---

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ставку пользователя
    """
    user_data = await get_user(update)
    if user_data is None:
        return

    selected_game = user_data.get("current_game")
    if not selected_game:
        return

    bet_text = update.message.text.replace(",", "").replace(" ", "")

    # Пытаемся преобразовать введённое значение в целое число
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
        coin = random.choice(["орёл", "решка"])
        # Для простоты - 50% шанс победы
        won = random.choice([True, False])
        
        result_msg = f"🤏 Выпал *{coin}*."
        if won:
            win_amount = int(bet * 2)  # Выигрыш x2
            result_msg += " Вы угадали! Победа!"
        else:
            result_msg += " Вы не угадали. Проигрыш."

    elif selected_game == "dice_roll":
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        total = dice1 + dice2

        if total % 2 == 0:
            win_amount = bet * 2
            result_msg = f"🎲 Выпало {dice1} + {dice2} = *{total}* (Чет). Победа!"
        else:
            result_msg = f"🎲 Выпало {dice1} + {dice2} = *{total}* (Нечет). Проигрыш."

    # Считаем новый баланс
    new_balance = user_data["balance"] - bet + win_amount

    # Сохраняем изменения
    await save_balance(user_id=user_data["user_id"], new_balance=new_balance)

    # Создаем кнопки для продолжения игры
    play_again_buttons = [
        [InlineKeyboardButton("🎲 Играть снова", callback_data="casino")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="mainmenu")]
    ]

    if win_amount > 0:
        profit = win_amount - bet
        summary = (
            f"{result_msg}\n\n"
            f"Выигрыш: +{profit:,} 🪙\n"
            f"Новый баланс: *{new_balance:,}* 🪙"
        )
    else:
        summary = (
            f"{result_msg}\n\n"
            f"Потеряно: -{bet:,} 🪙\n"
            f"Новый баланс: *{new_balance:,}* 🪙"
        )
        
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(play_again_buttons)
    )


if __name__ == "__main__":
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))

    # Обработчик кнопок (должен быть один)
    app.add_handler(CallbackQueryHandler(button_handler))

    # Ввод суммы ставок (только числа)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\d+$"), process_bet))

    print("Бот запущен...")
    app.run_polling(drop_pending_updates=True)
