import json
import os
import sqlite3
import datetime
import random

# Пробуем импортировать psycopg2
try:
    import psycopg2
    import psycopg2.extras
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("⚠️ psycopg2 не установлен, используем SQLite")

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


# ⚙️ Загрузка токенов
TOKEN = os.getenv("API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("🛑 Ошибка! Переменная окружения API_TOKEN не найдена.")

# Определяем тип базы данных
if DATABASE_URL and POSTGRESQL_AVAILABLE:
    DB_TYPE = "postgresql"
    print("✅ Используем PostgreSQL")
else:
    DB_TYPE = "sqlite"
    print("✅ Используем SQLite")


# --- НАСТРОЙКИ ---
DB_NAME = "casino.db"
BACKUP_FILE = "backup_data.json"
DAILY_START = 10_000
DAILY_INCREMENT = 10_000


# --- РАБОТА С БАЗОЙ ДАННЫХ ---

def get_db_connection():
    """Получает соединение с базой данных"""
    try:
        if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
            return psycopg2.connect(DATABASE_URL)
        else:
            return sqlite3.connect(DB_NAME)
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return sqlite3.connect(DB_NAME)


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
            try:
                if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
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
            except Exception as e:
                print(f"Ошибка восстановления пользователя {user.get('user_id')}: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Данные восстановлены из {BACKUP_FILE}")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления из бэкапа: {e}")
        return False


def init_db():
    """Инициализация базы данных"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
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
            
            cursor.execute('SELECT COUNT(*) FROM shop')
            count = cursor.fetchone()[0]
            
            if count == 0:
                items = [
                    ("Счастливая монета", 50000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200000, "Открывает эксклюзивные игры"),
                ]
                for item in items:
                    cursor.execute(
                        'INSERT INTO shop (name, price, description) VALUES (%s, %s, %s)',
                        item
                    )
        else:
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
            
            cursor.execute('SELECT COUNT(*) FROM shop')
            count = cursor.fetchone()[0]
            
            if count == 0:
                items = [
                    ("Счастливая монета", 50000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200000, "Открывает эксклюзивные игры"),
                ]
                cursor.executemany(
                    'INSERT INTO shop (name, price, description) VALUES (?, ?, ?)',
                    items
                )
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[INFO] База данных инициализирована ({DB_TYPE})")
        
        # Восстанавливаем данные из бэкапа
        restore_from_backup()
        
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации БД: {e}")


async def get_user(user_id_or_update):
    """Получает данные пользователя"""
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
        
        if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
            cursor.execute(
                '''INSERT INTO users (user_id, username) 
                   VALUES (%s, %s) 
                   ON CONFLICT (user_id) DO NOTHING''',
                (user_id, username)
            )
            
            if username:
                cursor.execute(
                    'UPDATE users SET username = %s WHERE user_id = %s AND username = %s',
                    (username, user_id, '')
                )
            
            cursor.execute(
                'SELECT user_id, username, balance, last_daily, current_game FROM users WHERE user_id = %s',
                (user_id,)
            )
        else:
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

        if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
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
        
        # Сохраняем бэкап
        backup_all_data()
        
        print(f"✅ Баланс обновлен для пользователя {user_id}: {new_balance}")
    except Exception as e:
        print(f"❌ Ошибка сохранения баланса: {e}")


async def set_current_game(user_id: int, game_name: str):
    """Устанавливает текущую игру"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
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
        print(f"❌ Ошибка установки игры: {e}")


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
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
    
    text = f"🎰 *Казино-Бот*\n\nПривет, *{user_name}*!\nВыбери действие:"

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
    """Показывает баланс"""
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
    """Меню казино"""
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
    """Запрос ставки"""
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
        f"✏️ *Введите сумму ставки:*"
    )
    
    await query.edit_message_text(
        msg, 
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
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
        await cancel_bet_handler(update, context)
    elif query.data.startswith("buy_"):
        await process_purchase(update, context)


async def cancel_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ставки"""
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
    """Топ-10 игроков"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
        leaders = cursor.fetchall()
        cursor.close()
        conn.close()

        msg = "🏆 *Топ-10 игроков:*\n\n"
        for i, (username, bal) in enumerate(leaders, 1):
            name = username if username else "Аноним"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            msg += f"{medal} {i}. {name}: `{bal:,}` 🪙\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Ошибка топа: {e}")
        await update.message.reply_text("❌ Ошибка при получении топа.")


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный бонус"""
    query = update.callback_query
    await query.answer()
    
    today = datetime.date.today().isoformat()
    
    user_data = await get_user(update)
    if user_data is None:
        await query.edit_message_text("❌ Ошибка получения данных.")
        return

    last_date = user_data["last_daily"]
    
    if last_date:
        if hasattr(last_date, 'isoformat'):
            last_date = last_date.isoformat()
        else:
            last_date = str(last_date)

    if last_date is None or last_date != today:
        bonus = DAILY_START
        new_balance = user_data["balance"] + bonus

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if DB_TYPE == "postgresql" and POSTGRESQL_AVAILABLE:
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
            
            backup_all_data()
            
        except Exception as e:
            print(f"❌ Ошибка бонуса: {e}")
            await query.edit_message_text("❌ Ошибка при начислении бонуса.")
            return

        keyboard = [[InlineKeyboardButton("↩️ В меню", callback_data="mainmenu")]]
        
        await query.edit_message_text(
            f"✅ *Бонус получен!*\n\n"
            f"🎁 Бонус: `{bonus:,}` 🪙\n"
            f"💰 Баланс: `{new_balance:,}` 🪙",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("↩️ В меню", callback_data="mainmenu")]]
        
        await query.edit_message_text(
         
