import sqlite3  # Для работы с базой данных SQLite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
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
import logging  # Логирование ошибок


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
            ('Счастливая монета', 50_000, 'Увеличивает шанс выигрыша'),
            ('Удвоитель опыта', 75_000, 'Временное удвоение всех выигрышей'),
            ('VIP-статус', 200_000, 'Открывает эксклюзивные игры'),
        ]
        cursor.executemany('INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items)
        
    conn.commit()
    conn.close()


async def get_user(update: Update):
    """
    Получаем данные пользователя из базы.
    Регистрирует нового игрока, если его нет.
    Возвращает ВСЕ поля пользователя.
    """
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
    return {'balance': data[0], 'last_daily': data[1], 'current_game': data[2]}


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
    user_data = await get_user(update)

    keyboard = [
        [InlineKeyboardButton(f'💰 Баланс: {user_data["balance"]:,} 🪙', callback_data='balance')],
        [InlineKeyboardButton('🎲 Казино', callback_data='casino')],
        [InlineKeyboardButton('🛍 Магазин', callback_data='shop')],
        [InlineKeyboardButton('🗓 Ежедневный бонус', callback_data='daily')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{update.effective_user.first_name}*!\nВыбери действие:"
    try:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        logger.error(e)


# --- ОБРАБОТЧИК КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие

    match query.data:
        case 'mainmenu':
            await main_menu_from_callback(query)

        case 'balance':
            user_data = await get_user(update)
            await query.edit_message_text(
                text=f"Твой текущий баланс: *{user_data['balance']:,}* 🪙",
                parse_mode="Markdown"  
            )

        case 'daily':
            await daily(query, context)
            
        case 'shop':
            await show_shop(query, context)

        # Обработка покупок товаров
        case buy_item if buy_item.startswith('buy_'):
            await process_purchase(update, context)

        # Теперь сохраняем игру прямо в БД!
        case 'coin_flip' | 'dice_roll':
            game_name = {
                'coin_flip': 'Орел / Решка 🤏',
                'dice_roll': 'Кости 🎲'
            }[query.data]

            # Сохраняем текущую игру в профиль пользователя
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET current_game = ? WHERE user_id = ?", (query.data, update.effective_user.id))
            conn.commit()
            conn.close()

            # Получаем данные синхронно, а потом формируем строку
            user_data = await get_user(update)
            msg = (
                f"Введите сумму ставки для игры \"*{game_name}*\":\n\n"
                f"Текущий баланс: *{user_data['balance']:,}* 🪙"  # Теперь здесь число!
            )
            await query.edit_message_text(msg, parse_mode="Markdown") # Без клавиатуры

        # Исправленная логика возврата из магазина
        # Теперь кнопка «Назад» работает как «cancel»
        case 'cancel':
            # Отмена выбора игры/возврат в главное меню
            # Стираем текущее состояние игры у пользователя
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET current_game = NULL WHERE user_id = ?", (update.effective_user.id,))
            conn.commit()
            conn.close()

            await main_menu_from_callback(query)


async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет выбор игры и возвращает в главное меню."""
    query = update.callback_query
    await query.answer()

    # Удалим сохранённую игру из профиля пользователя
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET current_game = NULL WHERE user_id = ?", (update.effective_user.id,))
    conn.commit()
    conn.close()

    await main_menu_from_callback(query)


async def main_menu_from_callback(query):
    """Показать главное меню из коллбека (без message object)."""
    user_data = await get_user(update=query)
    keyboard = [
        [InlineKeyboardButton(f'💰 Баланс: {user_data["balance"]:,} 🪙', callback_data='balance')],
        [InlineKeyboardButton('🎲 Казино', callback_data='casino')],
        [InlineKeyboardButton('🛍 Магазин', callback_data='shop')],
        [InlineKeyboardButton('🗓 Ежедневный бонус', callback_data='daily')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{query.from_user.first_name}*!\nВыбери действие:"
    await query.edit_message_text(
        text=text, parse_mode="Markdown", reply_markup=reply_markup  
    )


# --- ЛИДЕРЫ И ЕЖЕДНЕВНЫЙ БОНУС ---

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10')
    leaders = cursor.fetchall()
    conn.close()

    msg = "🏆 Топ самых богатых игроков:\n"
    for i, (username, bal) in enumerate(leaders, 1):
        name = username or "Аноним"
        msg += f"{i}. {name}: {bal:,} 🪙\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def daily(query, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    user = query.from_user

    user_data = await get_user(update=query)
    last_date_str = user_data['last_daily']

    # Обработка первого запуска (когда поля ещё нет)
    if last_date_str is None:
        days_passed = 1
    else:
        last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d').date()
        days_passed = (today - last_date).days

    if days_passed < 1:
        await query.edit_message_text("❌ Вы уже забрали бонус сегодня.")
        return

    bonus = DAILY_START + max(DAILY_INCREMENT * (days_passed - 1), 0)
    new_balance = user_data['balance'] + bonus

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.conn.cursor()
    cursor.execute(
        'UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?',
        (new_balance, today.isoformat(), user.id))
    conn.commit()
    conn.close()

    await query.edit_message_text(
        f"✅ Успех! Вы забрали бонус за {days_passed} день/дня: *{bonus:,}* 🪙.\nНовый баланс: *{new_balance:,}* 🪙",
        parse_mode="Markdown"
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
    buttons.append(
        [InlineKeyboardButton('↩️ Назад', callback_data='cancel')] # Используем cancel для возврата
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
    _, item_id = query.data.split('_')
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
    user_data = await get_user(update)
    current_balance = user_data['balance']

    if current_balance < item_price:
        await query.edit_message_text(f"❌ Недостаточно средств для покупки '{item_name}'. Ваш баланс: {current_balance:,}")
        return

    # Покупка успешна
    new_balance = current_balance - item_price
    await save_balance(update.effective_user.id, new_balance)

    # Сообщение об успехе
    await query.edit_message_text(
        f"✅ Вы купили '{item_name}' за {item_price:,} монет!\nВаш новый баланс: *{new_balance:,}* 🪙",
        parse_mode=constants.ParseMode.MARKDOWN
    )

    # Возвращаемся в главное меню
    await main_menu_from_callback(query)


# --- ИГРОПРОВОДНИК —

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Эта функция срабатывает при вводе любой цифры от пользователя.
    Она проверит, есть ли у него активная игра, и обработает ставку.
    """
    # Получаем полную информацию о пользователе
    user_data = await get_user(update)

    # Если у пользователя нет активной игры, просто игнорируем сообщение
    selected_game = user_data.get('current_game')
    if not selected_game:
        return

    bet_text = update.message.text.replace(',', '').replace(' ', '')

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

    if bet > user_data['balance']:
        await update.message.reply_text("❌ Недостаточно средств на балансе.", parse_mode="Markdown")
        return

    result_msg = ""
    win_amount = 0

    # Логика игр
    if selected_game == 'coin_flip':
        choice = random.choice(['орёл', 'решка'])
        coin = random.choice(['орёл', 'решка'])
        won = choice == coin
        multiplier = 1.95

        result_msg = f"🤏 Выпал *{coin}*."
        if won:
            win_amount = int(bet * multiplier)
            result_msg += " Ваша ставка сыграла!"
        else:
            result_msg += " Попробуйте еще раз."

    elif selected_game == 'dice_roll':
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        total = dice1 + dice2

        if total % 2 == 0:
            win_amount = bet * 2
            result_msg = f"🎲 Выпало {dice1} + {dice2} = *{total}* (Чет). Победа!"
        else:
            result_msg = f"🎲 Выпало {dice1} + {dice2} = *{total}* (Нечет). Проигрыш."

    # Считаем новый баланс
    new_balance = user_data['balance'] + win_amount - bet

    # Сохраняем изменения баланса И УДАЛЯЕМ АКТИВНУЮ ИГРУ
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?",
        (new_balance, update.effective_user.id)
    )
    conn.commit()
    conn.close()

    summary = (
        f"{result_msg}\n\n{'+' if win_amount > 0 else '-'}{abs(win_amount - bet):,} 🪙\nВаш новый баланс: *{new_balance:,}* 🪙"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")


# ✍️ Кастомный фильтр для ввода суммы
# Теперь фильтруем любые цифровые сообщения без привязки к контексту
def game_input_filter(_: Update, ctx: ContextTypes.DEFAULT_TYPE | None = None) -> bool:
    """
    Этот фильтр позволяет обрабатывать любое цифровое сообщение от пользователя.
    Мы будем проверять наличие активной игры непосредственно в функции-обработчике.
    """
    return _.message is not None and _.message.text.isdigit()


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
    # Он будет ловить ЛЮБЫЕ цифровые сообщения, но обработка произойдёт только при наличии активной игры
    app.add_handler(MessageHandler(game_input_filter, process_bet), group=0)

    print("Бот запущен...")
    app.run_polling(drop_pending_updates=True)
