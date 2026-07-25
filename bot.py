import json
import os
import sqlite3
import datetime
import random

# Пробуем импортировать psycopg2, если не установлен - работаем только с SQLite
try:
    import psycopg2
    import psycopg2.extras
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("⚠️ psycopg2 не установлен, будем использовать SQLite")

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


# ⚙️ Загрузка токенов из переменных окружения
TOKEN = os.getenv("API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError(
        "🛑 Ошибка! Переменная окружения API_TOKEN не найдена."
        "\nПроверьте настройки вашего сервера."
    )

# Определяем тип базы данных
if DATABASE_URL and POSTGRESQL_AVAILABLE:
    DB_TYPE = "postgresql"
    print("✅ Используем PostgreSQL базу данных")
else:
    DB_TYPE = "sqlite"
    if not POSTGRESQL_AVAILABLE and DATABASE_URL:
        print("⚠️ DATABASE_URL есть, но psycopg2 не установлен. Используем SQLite")
    print("✅ Используем SQLite базу данных")


# --- НАСТРОЙКИ ---
DB_NAME = "casino.db"
BACKUP_FILE = "backup_data.json"
DAILY_START = 10_000
DAILY_INCREMENT = 10_000


# --- ФУНКЦИИ БЭКАПА ДАННЫХ ---

def backup_all_data():
    """Сохраняет все данные в JSON файл"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, username, balance, last_daily, current_game FROM users')
        users_data = []
        for row in cursor.fetchall():
            users_data.append({
                "user_id": row[0],
                "username": row[1],
                "balance": row[2],
                "last_daily": str(row[3]) if row[3] else None,
                "current_game": row[4]
            })
        
        cursor.close()
        conn.close()
        
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Данные сохранены в {BACKUP_FILE}")
    except Exception as e:
        print(f"❌ Ошибка сохранения бэкапа: {e}")


def restore_from_backup():
    """Восстанавливает данные из JSON файла"""
    try:
        if not os.path.exists(BACKUP_FILE):
            print("📄 Файл бэкапа не найден")
            return False
        
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for user in users_data:
            if DB_TYPE == "postgresql":
                cursor.execute(
                    '''INSERT INTO users (user_id, username, balance, last_daily, current_game) 
                       VALUES (%s, %s, %s, %s, %s) 
                       ON CONFLICT (user_id) DO NOTHING''',
                    (user["user_id"], user["username"], user["balance"], 
                     user["last_daily"], user["current_game"])
                )
            else:
                cursor.execute(
                    '''INSERT OR IGNORE INTO users (user_id, username, balance, last_daily, current_game) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (user["user_id"], user["username"], user["balance"], 
                     user["last_daily"], user["current_game"])
                )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Данные восстановлены из {BACKUP_FILE}")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления из бэкапа: {e}")
        return False


# --- РАБОТА С БАЗОЙ ДАННЫХ ---

def get_db_connection():
    """Получает соединение с базой данных"""
    try:
        if DB_TYPE == "postgresql":
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        else:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        # Возвращаем SQLite как запасной вариант
        return sqlite3.connect(DB_NAME)


def init_db():
    """Инициализация базы данных"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            # PostgreSQL синтаксис
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT DEFAULT '',
                    balance INTEGER DEFAULT 10000,
                    last_daily DATE,
                    current_game TEXT
                );
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop (
                    item_id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT DEFAULT ''
                );
            ''')
            
            # Проверяем наличие товаров
            cursor.execute('SELECT COUNT(*) FROM shop')
            count = cursor.fetchone()[0]
            
            if count == 0:
                items = [
                    ("Счастливая монета", 50_000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75_000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200_000, "Открывает эксклюзивные игры"),
                ]
                cursor.executemany(
                    'INSERT INTO shop (name, price, description) VALUES (%s, %s, %s)', 
                    items
                )
        else:
            # SQLite синтаксис
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    balance INTEGER DEFAULT 10000,
                    last_daily DATE,
                    current_game TEXT
                );
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT DEFAULT ''
                );
            ''')
            
            # Проверяем наличие товаров
            cursor.execute('SELECT COUNT(*) FROM shop')
            count = cursor.fetchone()[0]
            
            if count == 0:
                items = [
                    ("Счастливая монета", 50_000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75_000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200_000, "Открывает эксклюзивные игры"),
                ]
                cursor.executemany(
                    'INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', 
                    items
                )
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[INFO] База данных инициализирована ({DB_TYPE})")
        
        # Пробуем восстановить данные из бэкапа
        restore_from_backup()
        
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации БД: {e}")


async def get_user(user_id_or_update):
    """Получает данные пользователя из базы"""
    try:
        # Определяем user_id
        if isinstance(user_id_or_update, int):
            user_id = user_id_or_update
            username = ""
        elif hasattr(user_id_or_update, 'effective_user') and user_id_or_update.effective_user:
            user_id = user_id_or_update.effective_user.id
            username = user_id_or_update.effective_user.username or ""
        elif hasattr(user_id_or_update, 'from_user') and user_id_or_update.from_user:
            user_id = user_id_or_update.from_user.id
            username = user_id_or_update.from_user.username or ""
        elif hasattr(user_id_or_update, 'message') and user_id_or_update.message:
            user_id = user_id_or_update.message.from_user.id
            username = user_id_or_update.message.from_user.username or ""
        else:
            print("❌ Не удалось определить user_id")
            return None

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            # PostgreSQL
            cursor.execute(
                '''INSERT INTO users (user_id, username) 
                   VALUES (%s, %s) 
                   ON CONFLICT (user_id) DO UPDATE 
                   SET username = CASE WHEN users.username = '' THEN EXCLUDED.username ELSE users.username END''',
                (user_id, username)
            )
            
            cursor.execute(
                'SELECT user_id, username, balance, last_daily, current_game FROM users WHERE user_id = %s',
                (user_id,)
            )
        else:
            # SQLite
            cursor.execute(
                'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
                (user_id, username)
            )
            
            if username:
                cursor.execute(
                    'UPDATE users SET username = ? WHERE user_id = ? AND username = ?',
                    (username, user_id, '')
                )
            
            cursor.execute(
                'SELECT user_id, username, balance, last_daily, current_game FROM users WHERE user_id = ?',
                (user_id,)
            )
        
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        
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
        print(f"❌ Ошибка получения пользователя: {e}")
        return None


async def save_balance(user_id: int, new_balance: int = None):
    """Обновляет баланс пользователя"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if DB_TYPE == "postgresql":
            if new_balance is None:
                cursor.execute(
                    'UPDATE users SET current_game = NULL WHERE user_id = %s',
                    (user_id,)
                )
            else:
                cursor.execute(
                    'UPDATE users SET balance = %s, current_game = NULL WHERE user_id = %s',
                    (new_balance, user_id)
                )
        else:
            if new_balance is None:
                cursor.execute(
                    'UPDATE users SET current_game = NULL WHERE user_id = ?',
                    (user_id,)
                )
            else:
                cursor.execute(
                    'UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?',
                    (new_balance, user_id)
                )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Сохраняем бэкап после изменения баланса
        backup_all_data()
        
        print(f"✅ Баланс обновлен для пользователя {user_id}: {new_balance}")
    except Exception as e:
        print(f"❌ Ошибка сохранения баланса для {user_id}: {e}")


async def set_current_game(user_id: int, game_name: str):
    """Устанавливает текущую игру пользователя"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            cursor.execute(
                'UPDATE users SET current_game = %s WHERE user_id = %s',
                (game_name, user_id)
            )
        else:
            cursor.execute(
                'UPDATE users SET current_game = ? WHERE user_id = ?',
                (game_name, user_id)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"🎮 Игра установлена: {game_name} для пользователя {user_id}")
    except Exception as e:
        print(f"❌ Ошибка установки игры для {user_id}: {e}")


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками"""
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="show_balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        user_name = update.effective_user.first_name
    except AttributeError:
        try:
            user_name = update.callback_query.from_user.first_name
        except:
            user_name = "Игрок"
    
    text = f"🎰 *Казино-Бот* 🎰\n\nПривет, *{user_name}*!\nТвой баланс будет сохранен!\n\nВыбери действие:"

    try:
        await update.message.reply_text(
            text, 
            parse_mode=constants.ParseMode.MARKDOWN, 
            reply_markup=reply_markup
        )
    except AttributeError:
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
        text=f"💰 *Твой баланс*\n\n`{user_data['balance']:,}` 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def casino_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню казино"""
    query = update.callback_query
    await query.answer()
    
    game_buttons = [
        [InlineKeyboardButton("🪙 Орел / Решка", callback_data="coin_flip")],
        [InlineKeyboardButton("🎲 Кости", callback_data="dice_roll")],
        [InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")],
    ]

    await query.edit_message_text(
        text="🎰 *Казино*\n\n*Выберите игру:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(game_buttons),
    )


async def game_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает ставку для выбранной игры"""
    query = update.callback_query
    await query.answer()
    
    game_names = {
        "coin_flip": "Орел / Решка 🪙",
        "dice_roll": "Кости 🎲",
    }
    
    game_name = game_names.get(query.data, "Неизвестная игра")
    
    user_data = await get_user(update)
    if user_data is None:
        return
    
    await set_current_game(user_data['user_id'], query.data)
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_bet")]]
    
    msg = (
        f"🎮 *{game_name}*\n\n"
        f"💰 Ваш баланс: `{user_data['balance']:,}` 🪙\n\n"
        f"✏️ *Введите сумму ставки числом:*"
    )
    
    await query.edit_message_text(
        msg, 
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик всех кнопок"""
    query = update.callback_query
    await query.answer()

    print(f"🔘 Нажата кнопка: {query.data}")

    handlers = {
        "mainmenu": main_menu,
        "show_balance": show_balance_handler,
        "daily": daily_handler,
        "shop": show_shop,
        "casino": casino_keyboard_handler,
        "coin_flip": game_bet_handler,
        "dice_roll": game_bet_handler,
        "cancel_bet": cancel_bet_handler,
    }
    
    if query.data in handlers:
        await handlers[query.data](update, context)
    elif query.data.startswith("buy_"):
        await process_purchase(update, context)


async def cancel_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет текущую ставку"""
    query = update.callback_query
    await query.answer()
    
    user_data = await get_user(update)
    if user_data:
        await save_balance(user_id=user_data["user_id"], new_balance=None)
    
    keyboard = [
        [InlineKeyboardButton("🎲 В казино", callback_data="casino")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="mainmenu")]
    ]
    
    await query.edit_message_text(
        "❌ Ставка отменена. Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает топ-10 игроков"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
        leaders = cursor.fetchall()
        cursor.close()
        conn.close()

        msg = "🏆 *Топ-10 богатых игроков:*\n\n"
        for i, (username, bal) in enumerate(leaders, 1):
            name = username if username else "Аноним"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            msg += f"{medal} {i}. {name}: `{bal:,}` 🪙\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Ошибка получения топа: {e}")
        await update.message.reply_text("❌ Ошибка при получении топа игроков.")


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ежедневного бонуса"""
    query = update.callback_query
    await query.answer()
    
    today = datetime.date.today().isoformat()
    
    user_data = await get_user(update)
    if user_data is None:
        await query.edit_message_text("❌ Ошибка получения данных.")
        return

    last_date = user_data["last_daily"]
    
    # Нормализуем дату для сравнения
    if last_date:
        if hasattr(last_date, 'isoformat'):
            last_date = last_date.isoformat()
        else:
            last_date = str(last_date)

    if last_date is None or last_date != today:
        bonus = DAILY_START
        
        # Проверяем, не пропустил ли пользователь дни
        if last_date:
            try:
                last_date_obj = datetime.date.fromisoformat(last_date)
                today_obj = datetime.date.today()
                days_diff = (today_obj - last_date_obj).days
                if days_diff > 1:
                    bonus += DAILY_INCREMENT * (days_diff - 1)
            except:
                pass
        
        new_balance = user_data["balance"] + bonus

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if DB_TYPE == "postgresql":
                cursor.execute(
                    'UPDATE users SET balance = %s, last_daily = %s WHERE user_id = %s',
                    (new_balance, today, user_data["user_id"])
                )
            else:
                cursor.execute(
                    'UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?',
                    (new_balance, today, user_data["user_id"])
                )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Сохраняем
