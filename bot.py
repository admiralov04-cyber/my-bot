import sqlite3
import datetime
import random
import os
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Токен бота
TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError("API_TOKEN не найден!")

# Настройки
DB_NAME = "casino.db"
DAILY_START = 10000

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            balance INTEGER DEFAULT 10000,
            last_daily TEXT,
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
            ("Удвоитель опыта", 75000, "Временное удвоение выигрышей"),
            ("VIP-статус", 200000, "Эксклюзивные игры"),
        ]
        cursor.executemany('INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items)
    
    conn.commit()
    conn.close()
    print("Database ready!")

# Получить пользователя
async def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
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

# Сохранить баланс
async def save_balance(user_id, new_balance=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if new_balance is None:
        cursor.execute('UPDATE users SET current_game = NULL WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('UPDATE users SET balance = ?, current_game = NULL WHERE user_id = ?', 
                      (new_balance, user_id))
    
    conn.commit()
    conn.close()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Бонус", callback_data="daily")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user = update.effective_user
    text = f"🎰 Казино-Бот\n\nПривет, {user.first_name}!\nВыбери действие:"
    
    await update.message.reply_text(text, reply_markup=reply_markup)

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = await get_user(user_id)
    
    if query.data == "balance":
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="back")]]
        await query.edit_message_text(
            f"💰 Ваш баланс: {user_data['balance']:,} 🪙",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "casino":
        keyboard = [
            [InlineKeyboardButton("🪙 Орел/Решка", callback_data="coin")],
            [InlineKeyboardButton("🎲 Кости", callback_data="dice")],
            [InlineKeyboardButton("↩️ Назад", callback_data="back")],
        ]
        await query.edit_message_text(
            "🎰 Выберите игру:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data in ["coin", "dice"]:
        game_name = "Орел/Решка" if query.data == "coin" else "Кости"
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET current_game = ? WHERE user_id = ?', 
                      (query.data, user_id))
        conn.commit()
        conn.close()
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
        await query.edit_message_text(
            f"🎮 {game_name}\n\n💰 Баланс: {user_data['balance']:,} 🪙\n\n✏️ Введите ставку (число):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "cancel":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET current_game = NULL WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        keyboard = [[InlineKeyboardButton("🎲 В казино", callback_data="casino")],
                   [InlineKeyboardButton("↩️ Меню", callback_data="back")]]
        await query.edit_message_text("❌ Ставка отменена", 
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "daily":
        today = datetime.date.today().isoformat()
        last = str(user_data["last_daily"]) if user_data["last_daily"] else None
        
        if last != today:
            new_balance = user_data["balance"] + DAILY_START
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?',
                         (new_balance, today, user_id))
            conn.commit()
            conn.close()
            
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            await query.edit_message_text(
                f"✅ Бонус: +{DAILY_START:,} 🪙\n💰 Баланс: {new_balance:,} 🪙",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            await query.edit_message_text("❌ Бонус уже получен!", 
                                         reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "shop":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, name, price FROM shop ORDER BY price")
        items = cursor.fetchall()
        
        buttons = []
        for item in items:
            buttons.append([InlineKeyboardButton(
                f"{item[1]} - {item[2]:,} 🪙", 
                callback_data=f"buy_{item[0]}"
            )])
        buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back")])
        
        text = "🛍 Магазин\n\nТовары:\n"
        cursor.execute("SELECT name, price, description FROM shop ORDER BY price")
        for item in cursor.fetchall():
            text += f"\n📦 {item[0]}\n💵 {item[1]:,} 🪙\n📝 {item[2]}\n"
        
        conn.close()
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif query.data.startswith("buy_"):
        item_id = int(query.data.split("_")[1])
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, price FROM shop WHERE item_id = ?", (item_id,))
        item = cursor.fetchone()
        conn.close()
        
        if not item:
            await query.edit_message_text("❌ Товар не найден")
            return
        
        if user_data["balance"] < item[1]:
            keyboard = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
            await query.edit_message_text(
                f"❌ Недостаточно средств!\n💰 Баланс: {user_data['balance']:,} 🪙\n💵 Цена: {item[1]:,} 🪙",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        new_balance = user_data["balance"] - item[1]
        await save_balance(user_id, new_balance)
        
        keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
        await query.edit_message_text(
            f"✅ Куплено: {item[0]}\n💰 Баланс: {new_balance:,} 🪙",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
            [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
            [InlineKeyboardButton("🗓 Бонус", callback_data="daily")],
        ]
        await query.edit_message_text(
            "🎰 Главное меню\nВыбери действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Обработка ставок
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data = await get_user(user_id)
    
    if not user_data or not user_data["current_game"]:
        return
    
    try:
        bet = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите целое число!")
        return
    
    if bet <= 0:
        await update.message.reply_text("❌ Ставка больше нуля!")
        return
    
    if bet > user_data["balance"]:
        await update.message.reply_text(f"❌ Недостаточно средств!\n💰 Баланс: {user_data['balance']:,} 🪙")
        return
    
    # Игра
    if user_data["current_game"] == "coin":
        coin = random.choice(["орёл", "решка"])
        won = random.choice([True, False])
        if won:
            win = bet * 2
            msg = f"🪙 {coin}\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🪙 {coin}\n❌ Проигрыш -{bet:,} 🪙"
    
    elif user_data["current_game"] == "dice":
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2
            msg = f"🎲 {d1}+{d2}={total} (Чёт)\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🎲 {d1}+{d2}={total} (Нечет)\n❌ Проигрыш -{bet:,} 🪙"
    
    new_balance = user_data["balance"] - bet + win
    await save_balance(user_id, new_balance)
    
    keyboard = [
        [InlineKeyboardButton("🎲 Играть еще", callback_data="casino")],
        [InlineKeyboardButton("↩️ Меню", callback_data="back")]
    ]
    
    await update.message.reply_text(
        f"{msg}\n💰 Баланс: {new_balance:,} 🪙",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Топ игроков
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()
    
    msg = "🏆 Топ-10:\n\n"
    for i, (name, bal) in enumerate(leaders, 1):
        name = name or "Аноним"
        msg += f"{i}. {name}: {bal:,} 🪙\n"
    
    await update.message.reply_text(msg)

# Запуск
def main():
    print("Starting bot...")
    init_db()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
