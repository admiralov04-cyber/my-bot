import json
import os
import sqlite3
import datetime
import random

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)

TOKEN = os.getenv("API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("API_TOKEN не найден")

DB_TYPE = "postgresql" if (DATABASE_URL and POSTGRESQL_AVAILABLE) else "sqlite"
DB_NAME = "casino.db"
BACKUP_FILE = "backup_data.json"
DAILY_START = 10000
DAILY_INCREMENT = 10000


def get_db_connection():
    try:
        if DB_TYPE == "postgresql":
            return psycopg2.connect(DATABASE_URL)
        return sqlite3.connect(DB_NAME)
    except:
        return sqlite3.connect(DB_NAME)


def backup_all_data():
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
        print("Data backed up")
    except Exception as e:
        print(f"Backup error: {e}")


def restore_from_backup():
    try:
        if not os.path.exists(BACKUP_FILE):
            return False
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
        conn = get_db_connection()
        cursor = conn.cursor()
        for user in users_data:
            try:
                if DB_TYPE == "postgresql":
                    cursor.execute(
                        'INSERT INTO users (user_id, username, balance, last_daily, current_game) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING',
                        (user["user_id"], user["username"], user["balance"], user["last_daily"], user["current_game"])
                    )
                else:
                    cursor.execute(
                        'INSERT OR IGNORE INTO users (user_id, username, balance, last_daily, current_game) VALUES (?, ?, ?, ?, ?)',
                        (user["user_id"], user["username"], user["balance"], user["last_daily"], user["current_game"])
                    )
            except:
                continue
        conn.commit()
        cursor.close()
        conn.close()
        print("Data restored")
        return True
    except Exception as e:
        print(f"Restore error: {e}")
        return False


def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT DEFAULT '',
                    balance INTEGER DEFAULT 10000,
                    last_daily DATE,
                    current_game TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop (
                    item_id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT DEFAULT ''
                )
            ''')
            cursor.execute('SELECT COUNT(*) FROM shop')
            if cursor.fetchone()[0] == 0:
                items = [
                    ("Счастливая монета", 50000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200000, "Открывает эксклюзивные игры"),
                ]
                for item in items:
                    cursor.execute('INSERT INTO shop (name, price, description) VALUES (%s, %s, %s)', item)
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    balance INTEGER DEFAULT 10000,
                    last_daily DATE,
                    current_game TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT DEFAULT ''
                )
            ''')
            cursor.execute('SELECT COUNT(*) FROM shop')
            if cursor.fetchone()[0] == 0:
                items = [
                    ("Счастливая монета", 50000, "Увеличивает шанс выигрыша"),
                    ("Удвоитель опыта", 75000, "Временное удвоение всех выигрышей"),
                    ("VIP-статус", 200000, "Открывает эксклюзивные игры"),
                ]
                cursor.executemany('INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items)
        
        conn.commit()
        cursor.close()
        conn.close()
        restore_from_backup()
        print("DB initialized")
    except Exception as e:
        print(f"DB init error: {e}")


async def get_user(update_data):
    try:
        if isinstance(update_data, int):
            user_id = update_data
            username = ""
        elif hasattr(update_data, 'effective_user') and update_data.effective_user:
            user_id = update_data.effective_user.id
            username = update_data.effective_user.username or ""
        elif hasattr(update_data, 'from_user') and update_data.from_user:
            user_id = update_data.from_user.id
            username = update_data.from_user.username or ""
        elif hasattr(update_data, 'message') and update_data.message:
            user_id = update_data.message.from_user.id
            username = update_data.message.from_user.username or ""
        else:
            return None

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            cursor.execute(
                'INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING',
                (user_id, username)
            )
            cursor.execute('SELECT user_id, username, balance, last_daily, current_game FROM users WHERE user_id = %s', (user_id,))
        else:
            cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
            cursor.execute('SELECT user_id, username, balance, last_daily, current_game FROM users WHERE user_id = ?', (user_id,))
        
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if data:
            return {"user_id": data[0], "username": data[1], "balance": data[2], "last_daily": data[3], "current_game": data[4]}
        return None
    except Exception as e:
        print(f"Get user error: {e}")
        return None


async def save_balance(user_id, new_balance=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if new_balance is None:
            if DB_TYPE == "postgresql":
                cursor.execute('UPDATE users SET current_game = NULL WHERE user_id = %s', (user_id,))
            else:
                cursor.execute('UPDATE users SET current_game = NULL WHERE user_id = ?', (user_id,))
        else:
            if DB_TYPE == "postgresql":
                cursor.execute('UPDATE users SET balance = %s, current_game = NULL WHERE user_id = %s', (new_balance, user_id))
            else:
                cursor.execute('UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?', (new_balance, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        backup_all_data()
        print(f"Balance updated: {user_id} = {new_balance}")
    except Exception as e:
        print(f"Save balance error: {e}")


async def set_current_game(user_id, game_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            cursor.execute('UPDATE users SET current_game = %s WHERE user_id = %s', (game_name, user_id))
        else:
            cursor.execute('UPDATE users SET current_game = ? WHERE user_id = ?', (game_name, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Set game error: {e}")


async def start(update, context):
    await main_menu(update, context)


async def main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="show_balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        user_name = update.effective_user.first_name
    except:
        try:
            user_name = update.callback_query.from_user.first_name
        except:
            user_name = "Игрок"
    
    text = f"🎰 *Казино-Бот*\n\nПривет, *{user_name}*!\nВыбери действие:"

    try:
        await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)
    except:
        await update.callback_query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)


async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "mainmenu":
        await main_menu(update, context)
    elif query.data == "show_balance":
        await show_balance(update, context)
    elif query.data == "casino":
        await casino_menu(update, context)
    elif query.data == "shop":
        await shop_menu(update, context)
    elif query.data == "daily":
        await daily_bonus(update, context)
    elif query.data in ["coin_flip", "dice_roll"]:
        await game_bet(update, context)
    elif query.data == "cancel_bet":
        await cancel_bet(update, context)
    elif query.data.startswith("buy_"):
        await buy_item(update, context)


async def show_balance(update, context):
    query = update.callback_query
    user_data = await get_user(update)
    if not user_data:
        await query.edit_message_text("❌ Ошибка")
        return
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")]]
    await query.edit_message_text(
        f"💰 *Твой баланс*\n\n`{user_data['balance']:,}` 🪙",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def casino_menu(update, context):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("🪙 Орел / Решка", callback_data="coin_flip")],
        [InlineKeyboardButton("🎲 Кости", callback_data="dice_roll")],
        [InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")],
    ]
    await query.edit_message_text(
        "🎰 *Казино*\n\n*Выберите игру:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def game_bet(update, context):
    query = update.callback_query
    game_names = {"coin_flip": "Орел / Решка 🪙", "dice_roll": "Кости 🎲"}
    game_name = game_names.get(query.data, "Игра")
    
    user_data = await get_user(update)
    if not user_data:
        return
    
    await set_current_game(user_data['user_id'], query.data)
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_bet")]]
    await query.edit_message_text(
        f"🎮 *{game_name}*\n\n💰 Баланс: `{user_data['balance']:,}` 🪙\n\n✏️ *Введите сумму ставки:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_bet(update, context):
    query = update.callback_query
    user_data = await get_user(update)
    if user_data:
        await save_balance(user_data["user_id"])
    
    keyboard = [
        [InlineKeyboardButton("🎲 В казино", callback_data="casino")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="mainmenu")]
    ]
    await query.edit_message_text("❌ Ставка отменена", reply_markup=InlineKeyboardMarkup(keyboard))


async def top(update, context):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
        leaders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        msg = "🏆 *Топ-10 игроков:*\n\n"
        for i, (username, bal) in enumerate(leaders, 1):
            name = username or "Аноним"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            msg += f"{medal} {i}. {name}: `{bal:,}` 🪙\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Top error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def daily_bonus(update, context):
    query = update.callback_query
    today = datetime.date.today().isoformat()
    
    user_data = await get_user(update)
    if not user_data:
        await query.edit_message_text("❌ Ошибка")
        return
    
    last_date = str(user_data["last_daily"]) if user_data["last_daily"] else None
    
    if last_date != today:
        bonus = DAILY_START
        new_balance = user_data["balance"] + bonus
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if DB_TYPE == "postgresql":
                cursor.execute('UPDATE users SET balance = %s, last_daily = %s WHERE user_id = %s', (new_balance, today, user_data["user_id"]))
            else:
                cursor.execute('UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?', (new_balance, today, user_data["user_id"]))
            conn.commit()
            cursor.close()
            conn.close()
            backup_all_data()
        except Exception as e:
            print(f"Daily bonus error: {e}")
            await query.edit_message_text("❌ Ошибка")
            return
        
        keyboard = [[InlineKeyboardButton("↩️ В меню", callback_data="mainmenu")]]
        await query.edit_message_text(
            f"✅ *Бонус получен!*\n\n🎁 Бонус: `{bonus:,}` 🪙\n💰 Баланс: `{new_balance:,}` 🪙",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("↩️ В меню", callback_data="mainmenu")]]
        await query.edit_message_text(
            "❌ *Бонус уже получен!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def shop_menu(update, context):
    query = update.callback_query
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        buttons = []
        cur.execute("SELECT item_id, name, price FROM shop ORDER BY price")
        for row in cur.fetchall():
            item_id, name, price = row
            buttons.append([InlineKeyboardButton(f"{name} - {price:,} 🪙", callback_data=f"buy_{item_id}")])
        
        buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="mainmenu")])
        
        text = "🛍 *Магазин*\n\n*Товары:*\n"
        cur.execute("SELECT name, price, description FROM shop ORDER BY price")
        for name, price, desc in cur.fetchall():
            text += f"\n📦 *{name}*\n💵 Цена: `{price:,}` 🪙\n📝 {desc}\n"
        
        cur.close()
        conn.close()
        
        await query.edit_message_text(
            text=text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Shop error: {e}")
        await query.edit_message_text("❌ Ошибка загрузки магазина")


async def buy_item(update, context):
    query = update.callback_query
    try:
        item_id = int(query.data.split("_")[1])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DB_TYPE == "postgresql":
            cursor.execute("SELECT name, price FROM shop WHERE item_id = %s", (item_id,))
        else:
            cursor.execute("SELECT name, price FROM shop WHERE item_id = ?", (item_id,))
            
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            await query.edit_message_text("❌ Товар не найден")
            return
        
        item_name, item_price = result
        user_data = await get_user(update)
        
        if not user_data:
            return
        
        if user_data["balance"] < item_price:
            keyboard = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
            await query.edit_message_text(
                text=f"❌ *Недостаточно средств!*\n💰 Баланс: `{user_data['balance']:,}` 🪙\n💵 Цена: `{item_price:,}` 🪙",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        new_balance = user_data["balance"] - item_price
        await save_balance(user_data["user_id"], new_balance)
        
        keyboard = [[InlineKeyboardButton("↩️ В меню", callback_data="mainmenu")]]
        await query.edit_message_text(
            text=f"✅ *Покупка успешна!*\n📦 Товар: *{item_name}*\n💵 Потрачено: `{item_price:,}` 🪙\n💰 Баланс: `{new_balance:,}` 🪙",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        print(f"Buy error: {e}")
        await query.edit_message_text("❌ Ошибка покупки")


async def process_bet(update, context):
    user_data = await get_user(update.message.from_user.id)
    if not user_data:
        return
    
    selected_game = user_data.get("current_game")
    if not selected_game:
        return
    
    try:
        bet = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите целое число", parse_mode="Markdown")
        return
    
    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше нуля!")
        return
    
    if bet > user_data["balance"]:
        await update.message.reply_text(
            f"❌ *Недостаточно средств!*\n💰 Баланс: `{user_data['balance']:,}` 🪙",
            parse_mode="Markdown"
        )
        return
    
    result_msg = ""
    win_amount = 0
    
    if selected_game == "coin_flip":
        coin = random.choice(["орёл", "решка"])
        won = random.choice([True, False])
        result_msg = f"🪙 Монетка: *{coin}*"
        if won:
            win_amount = bet * 2
            result_msg += "\n✅ Победа!"
        else:
            result_msg += "\n❌ Проигрыш."
    
    elif selected_game == "dice_roll":
        dice1, dice2 = random.randint(1, 6), random.randint(1, 6)
        total = dice1 + dice2
        if total % 2 == 0:
            win_amount = bet * 2
            result_msg = f"🎲 Кубики: {dice1} + {dice2} = *{total}* (Чёт)\n✅ Победа!"
        else:
            result_msg = f"🎲 Кубики: {dice1} + {dice2} = *{total}* (Нечет)\n❌ Проигрыш."
    
    new_balance = user_data["balance"] - bet + win_amount
    await save_balance(user_data["user_id"], new_balance)
    
    keyboard 
