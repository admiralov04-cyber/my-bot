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
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Создадим таблицу пользователей полностью заново, если она повреждена
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
                
            print("[INFO] Database initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")


async def get_user(update):
    """
    Получаем данные пользователя из базы.
    
    Функция принимает ЛИБО id пользователя (int),
    ЛИБО весь объект update для извлечения этого id.
    Регистрирует нового игрока, если его нет.
    Возвращает ВСЕ поля пользователя или None при ошибке.
    """
    try:
        # Если передали целое число - это id пользователя
        if isinstance(update, int):
            user_id = update
        else:
            # Иначе извлекаем id из объекта Update
            user_id = update.effective_user.id

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Проверяем/добавляем пользователя
            cursor.execute(
                '''
                INSERT OR IGNORE INTO users (user_id, username) 
                VALUES (?, '');
                ''',
                (user_id,)
            )
            conn.commit()
            
            # Берём баланс, дату бонуса И текущую игру
            data = cursor.execute(
                '''
                SELECT balance, last_daily, current_game 
                FROM users WHERE user_id = ?
                ''',
                (user_id,)
            ).fetchone()
        
        return {"balance": data[0], "last_daily": data[1], "current_game": data[2]}
    except Exception as e:
        print(f"❗️ Error in DB query for user {user_id}: {str(e)}")
        return None


async def save_balance(user_id: int, new_balance: int | None):
    """
    Обновляет баланс пользователя.
    Если передан None вместо new_balance — сбрасывает поле current_game.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()

            # Если нам нужно только сбросить игру без изменения баланса
            if new_balance is None:
                cursor.execute(
                    '''
                    UPDATE users SET current_game = NULL WHERE user_id = ?
                    ''',
                    (user_id,)
                )
            else:
                cursor.execute(
                    '''
                    UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?
                    ''',  # Сбросим игру сразу при изменении баланса
                    (new_balance, user_id),
                )
            conn.commit()
    except Exception as e:
        print(f"❗️ Error saving balance for user {user_id}: {str(e)}")


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками."""
    # Исправление ошибки: передаём просто update, а не через знак =
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
        # Если мы вызываем эту функцию из коллбека (кнопки Назад), используем edit_message_text
        await update.callback_query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)


# ✅ Новый хендлер для кнопки "Показать баланс" в главном меню
async def show_balance(query):
    # Здесь тоже убираем лишний знак =
    user_data = await get_user(query.update) # <--- Передача всего объекта Update

    if user_data is None:
        return

    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]]

    await query.edit_message_text(
        text=f"Твой текущий баланс:\n*{user_data['balance']:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ✅ Логика казино вынесена в отдельную функцию
async def casino_keyboard(query):
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

        # Новая логика для показа баланса
        case "show_balance":
            await show_balance(query)

        # Обработка ежедневного бонуса
        case "daily":
            # Вот тут была ошибка! Нужно передавать именно объект Update, а не разбирать его вручную
            await daily(update, context) # <-- Фикс: передаю весь update

        case "shop":
            await show_shop(query, context)

        # Нажатие на кнопку "Казино" в главном меню
        case "casino":
            # Просто открываем клавиатуру с играми
            await casino_keyboard(query)

        # Пользователь выбрал конкретную игру
        case "coin_flip" | "dice_roll":
            # Сохранять игру в БД будем только когда пользователь введёт ставку!
            # Здесь просто просим ввести сумму
            game_name = {
                "coin_flip": "Орел / Решка 🤏",
                "dice_roll": "Кости 🎲",
            }[query.data]

            # Убираем лишнее '=' при получении данных пользователя
            user_data = await get_user(update) # <--- Передача всего объекта Update
            msg = (
                f"Введите сумму ставки для игры \"*{game_name}*\":\n\n"
                f"Текущий баланс: *{user_data['balance']:,}* 🪙"  
            )
            await query.edit_message_text(  
                msg, parse_mode=constants.ParseMode.MARKDOWN)  # Закрывающая кавычка добавлена

        # Разделили логику возврата
        # cancel — отмена текущей ставки
        # back_to_main — выход из магазина или списка игр в главное меню
        case "cancel":
            # Удалим сохранённую игру из профиля пользователя
            await save_balance(query.from_user.id, None)  # <-- Исправлено: передаю None
            # Оставаемся в текущем сообщении, ждём новую ставку
            await query.answer("Ставка отменена.")

        case "back_to_main":
            # Полностью возвращаемся в главное меню
            await main_menu(update, context)

        # Обработка покупок товаров
        case buy_item if buy_item.startswith("buy_"):
            await process_purchase(update, context)


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


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE): # <-- Сигнатура верная
    today = datetime.date.today().isoformat()
    
    # Вот тут было ключевая ошибка! Раньше я писал user_id=user_id
    # Фикс: теперь передаём весь объект Update, чтобы get_user сам разобрал его
    user_data = await get_user(update) # <--- Позиционный вызов

    if user_data is None:
        return

    last_date_str = user_data["last_daily"]

    # Фикс: дата должна храниться именно в формате YYYY-MM-DD
    # Иначе при сравнении могут возникнуть ошибки
    if last_date_str is None or str(last_date_str) != str(today):
        bonus = DAILY_START
        new_balance = user_data["balance"] + bonus

        await save_balance(user_data["id"], new_balance)

        # Отправляем ответ пользователю
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Успех! Вы получили свой дневной бонус: *{bonus:,}* 🪙.\nНовый баланс: *{new_balance:,}* 🪙",
            parse_mode="Markdown"
        ) # <--- Вот здесь был мой косяк! Раньше было написано просто `update.`
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Вы уже забрали бонус сегодня.",
            parse_mode="Markdown"
        )


# --- ПОКАЗАТЬ МАГАЗИН ---

async def show_shop(query, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    buttons = []
    for row in cur.execute("SELECT item_id, name, price FROM shop"):
        item_id, name, _price = row
        # ЭМОДЗИ ДОБАВЛЕНЫ ТОЛЬКО В НАЗВАНИЯ КНОПОК!
        button_name = f"{name} \U0001f4b8 {_price:,}"  # Эмодзи монеты экранировано
        buttons.append([InlineKeyboardButton(button_name, callback_data=f"buy_{item_id}")])

    # Кнопка возврата
    buttons.append(
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")]
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


# ✍️ Новый хендлер для обработки покупок
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Убираем лишний знак '=' при получении данных пользователя
    user_data = await get_user(update) # <--- Передача всего объекта Update
    if user_data is None:
        return

    current_balance = user_data["balance"]

    if current_balance < item_price:
        await query.edit_message_text(
            f"❌ Недостаточно средств для покупки '{item_name}'. Ваш баланс: {current_balance:,}"
        )
        return

    # Покупка успешна
    new_balance = current_balance - item_price
    await save_balance(user_data["id"], new_balance)

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
    user_data = await get_user(update) # <--- Передача всего объекта Update
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
    await save_balance(user_data["id"], new_balance)

    # Новые кнопки для результата игры
    play_again_buttons = [
        [InlineKeyboardButton("⬇ Играть снова", callback_data="casino")], # Вернёмся в список игр
        [InlineKeyboardButton("↩️ Главное меню", callback_data="mainmenu")] # Или сразу в главное меню
    ]

    summary = (
        f"{result_msg}\n\n{'+' if win_amount > 0 else '-'}{abs(win_amount - bet):,} 🪙\nВаш новый баланс: *{new_balance:,}* 🪙"
    )
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(play_again_buttons)
    )


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
