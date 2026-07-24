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


# ⚙️ Загрузка токена из системной переменной API_TOKEN (Bothost создаёт её автоматически).
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Основная таблица пользователей
    # Добавлена новая колонка current_game для сохранения текущего действия
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 10000,
            last_daily DATE, -- Дата последнего получения бонуса
            current_game TEXT   -- Текущая игра пользователя
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
        
    conn.commit()
    conn.close()


async def get_user(update):
    """
    Получаем данные пользователя из базы.
    Регистрирует нового игрока, если его нет.
    Возвращает ВСЕ поля пользователя.
    """
    # Теперь всегда передаётся полный объект update!
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Проверяем/добавляем пользователя
    cursor.execute(
        '''
        INSERT OR IGNORE INTO users (user_id, username) 
        VALUES (?, ?);
        ''',
        (user.id, user.username),
    )
    conn.commit()
    
    # Берём баланс, дату бонуса И текущую игру
    data = cursor.execute(
        '''
        SELECT balance, last_daily, current_game 
        FROM users WHERE user_id = ?
        ''',
        (user.id,)
    ).fetchone() or (None, None, None)
    
    conn.close()
    return {"balance": data[0], "last_daily": data[1], "current_game": data[2]}


async def save_balance(user_id: int, amount: int):
    """Обновляет баланс пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        '''
        UPDATE users SET balance = ? WHERE user_id = ?
        ''',
        (amount, user_id),
    )
    conn.commit()
    conn.close()


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками."""
    user_data = await get_user(update=update)

    keyboard = [
        [InlineKeyboardButton(f"💰 Баланс: {user_data['balance']:,} 🪙", callback_data="balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{update.effective_user.first_name}*!\nВыбери действие:"

    # УБРАЛ try/except — теперь всё работает корректно!
    await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)


# ✅ Вот здесь была ошибка! Теперь правильно обрабатываем казино
async def casino_keyboard(query):
    """Показывает клавиатуру с играми внутри казино."""
    game_buttons = [
        [InlineKeyboardButton("Орел / Решка 🤏", callback_data="coin_flip")],
        [InlineKeyboardButton("Кости 🎲", callback_data="dice_roll")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")],  # Кнопка назад
    ]

    await query.edit_message_text(
        text="*Выберите игру:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(game_buttons),
    )


# --- ОБРАБОТЧИК КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие

    match query.data:
        case "mainmenu":
            await main_menu(update, context)

        case "balance":
            user_data = await get_user(update=update) # Передаём полное обновление
            await query.edit_message_text(
                text=f"Твой текущий баланс: *{user_data['balance']:,}* 🪙",
                parse_mode="Markdown",
            )

        # ❗️ Фикс: вместо вызова несуществующей show_casino добавляем нашу новую функцию
        case "casino":
            await casino_keyboard(query)

        # ❗️ Здесь тоже нужно было использовать полное обновление
        case "daily":
            # Раньше передавали просто query, теперь правильно
            await daily(update, context) # <--- Оставляем как есть, но внутри daily поправили

        case "shop":
            await show_shop(query, context)

        # Обработка покупок товаров
        case buy_item if buy_item.startswith("buy_"):
            await process_purchase(update, context)

        # Сохраняем игру прямо в БД!
        case "coin_flip" | "dice_roll":
            game_name = {
                "coin_flip": "Орел / Решка 🤏",
                "dice_roll": "Кости 🎲",
            }[query.data]

            # Сохраняем текущую игру в профиль пользователя
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET current_game = ? WHERE user_id = ?", (query.data, update.effective_user.id)
            )
            conn.commit()
            conn.close()

            # Получаем данные синхронно, а потом формируем строку
            user_data = await get_user(update=update) # Передаём полное обновление
            msg = (
                f"Введите сумму ставки для игры \"*{game_name}*\":\n\n"
                f"Текущий баланс: *{user_data['balance']:,}* 🪙"  
            )
            await query.edit_message_text(msg, parse_mode="Markdown")  # Без клавиатуры

        # Разделили логику возврата
        # cancel — отмена текущей ставки
        # back_to_main — выход из магазина или казино в главное меню
        case "cancel":
            # Удалим сохранённую игру из профиля пользователя
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET current_game = NULL WHERE user_id = ?", (update.effective_user.id,)
            )
            conn.commit()
            conn.close()

            # Оставаемся в текущем сообщении, ждём новую ставку
            await query.answer("Ставка отменена.")

        case "back_to_main":
            # Полностью возвращаемся в главное меню
            await main_menu(update, context)


# --- ЛИДЕРЫ И ЕЖЕДНЕВНЫЙ БОНУС ---

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    msg = "🏆 Топ самых богатых игроков:\n"
    for i, (username, bal) in enumerate(leaders, 1):
        name = username or "Аноним"
        msg += f"{i}. {name}: {bal:,} 🪙\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE): # <--- Изменил сигнатуру функции
    today = datetime.date.today()
    
    # ❗️ Вот здесь была ошибка!
    # user_data = await get_user(update=query) <-- Так делать нельзя
    # Нужно передать ВСЁ обновление целиком
    user_data = await get_user(update=update) # <--- Исправление тут!

    last_date_str = user_data["last_daily"]

    if last_date_str is None:
        days_passed = 1
    else:
        last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
        days_passed = (today - last_date).days

    if days_passed < 1:
        await update.callback_query.edit_message_text("❌ Вы уже забрали бонус сегодня.") # <--- Используем callback_query
        return

    bonus = DAILY_START + max(DAILY_INCREMENT * (days_passed - 1), 0)
    new_balance = user_data["balance"] + bonus

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?",
        (new_balance, today.isoformat(), user.id),
    )
    conn.commit()
    conn.close()

    await update.callback_query.edit_message_text( # <--- Используем callback_query
        f"✅ Успех! Вы забрали бонус за {days_passed} день/дня: *{bonus:,}* 🪙.\nНовый баланс: *{new_balance:,}* 🪙",
        parse_mode="Markdown",
    )


# --- ПОКАЗАТЬ МАГАЗИН ---

async def show_shop(query, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Собираем кнопки товаров. ЭМОДЗИ ДОБАВЛЕНЫ ТОЛЬКО В НАЗВАНИЯ КНОПОК!
    buttons = []
    for row in cur.execute("SELECT item_id, name, price FROM shop"):
        item_id, name, _price = row
        # Добавляем эмодзи только к названию на кнопке, а не в текст сообщения
        button_name = f"{name} \U0001f4b8 {_price:,}"  # Эмодзи монеты экранировано
        buttons.append([InlineKeyboardButton(button_name, callback_data=f"buy_{item_id}")])

    # Добавляем кнопку возврата
    # Изменено на отдельную команду для магазина
    buttons.append(
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")]
    )

    # Формируем текст со списком товаров БЕЗ эмодзи в начале строк
    # Это решает проблему парсинга Markdown V2
    text = "*Добро пожаловать в магазин!*\n"
    for name, price, desc in cur.execute("SELECT name, price, description FROM shop"):
        text += f"\n• {name}\nЦена: {price:,} 🪙\n{desc}"

    conn.close()

    await query.edit_message_text(
        text=text,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ✍️ Новый хендлер для обработки покупок
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Извлекаем ID товара из callback_data
    _, item_id = query.data.split("_")
    item_id = int(item_id)

    # Получаем информацию о товаре
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM shop WHERE item_id = ?", (item_id,))
    result = cursor.fetchone()
    if not result:
        await query.edit_message_text("Ошибка: товар не найден!")
        return

    item_name, item_price = result

    # Проверяем баланс пользователя
    user_data = await get_user(update=update)
    current_balance = user_data["balance"]

    if current_balance < item_price:
        await query.edit_message_text(
            f"❌ Недостаточно средств для покупки '{item_name}'. Ваш баланс: {current_balance:,}"
        )
        return

    # Покупка успешна
    new_balance = current_balance - item_price
    await save_balance(update.effective_user.id, new_balance)

    # Сообщение об успехе
    await query.edit_message_text(
        f"✅ Вы купили '{item_name}' за {item_price:,} монет!\nВаш новый баланс: *{new_balance:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
    )

    # Возвращаемся в главное меню
    await main_menu(update, context)


# --- ИГРОПРОВОДНИК —

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Эта функция срабатывает при вводе любой цифры от пользователя.
    Она проверит, есть ли у него активная игра, и обработает ставку.
    """
    # Получаем полную информацию о пользователе
    user_data = await get_user(update=update)

    # Если у пользователя нет активной игры, просто игнорируем сообщение
    selected_game = user_data.get("current_game")
    if not selected_game:
        return

    bet_text = update.message.text.replace(",", "").replace(" ", "")

    # Пытаемся преобразовать введённое значение в целое число
    try:
        bet = int(bet_text)
    except ValueError:
        # Пользователь отправил текст вместо цифры
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
        multiplier = 1.95

        result_msg = f"🤏 Выпал *{coin}*."
        if won:
            win_amount = int(bet * multiplier)
            result_msg += " Ваша ставка сыграла!"
        else:
            result_msg += " Попробуйте еще раз."

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
    new_balance = user_data["balance"] + win_amount - bet

    # Сохраняем изменения баланса И УДАЛЯЕМ АКТИВНУЮ ИГРУ
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?",
        (new_balance, update.effective_user.id),
    )
    conn.commit()
    conn.close()

    summary = (
        f"{result_msg}\n\n{'+' if win_amount > 0 else '-'}{abs(win_amount - bet):,} 🪙\nВаш новый баланс: *{new_balance:,}* 🪙"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")


if __name__ == "__main__":
    init_db()  # Создаём базу данных при запуске

    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))  # Стартовое сообщение
    app.add_handler(CommandHandler("top", top))     # Команда топ-лидеров

    # Все кнопки
    app.add_handler(CallbackQueryHandler(button_handler))

    # Ввод суммы ставок
    # Важно: этот обработчик должен идти до обычных командных хэндлеров
    # Используем стандартные фильтры Telegram для проверки цифр
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\d+$"), callback=process_bet), group=0)

    print("Бот запущен...")
    app.run_polling(drop_pending_updates=True)
