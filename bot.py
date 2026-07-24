import sqlite3
import datetime
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

DB_NAME = 'casino.db'
DAILY_START = 10000
DAILY_INCREMENT = 10000

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Основная таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 10000,
            last_daily DATE -- Дата последнего получения бонуса
        )
    ''')
    
    # Таблица магазина предметов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER,
            description TEXT
        )
    ''')
    
    # Инвентарь пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(item_id) REFERENCES shop(item_id)
        )
    ''')
    
    # Заполним магазин базовыми предметами, если он пуст
    cursor.execute("SELECT COUNT(*) FROM shop")
    if cursor.fetchone()[0] == 0:
        items = [
            ('Счастливая монета', 50000, 'Увеличивает шанс выигрыша в казино на 5%'),
            ('Удвоитель опыта', 75000, 'Временно удваивает все выигрыши'),
            ('VIP-статус', 200000, 'Открывает эксклюзивные игры')
        ]
        cursor.executemany('INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items)
        
    conn.commit()
    conn.close()

async def get_user(update: Update):
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                   (user.id, user.username))
    conn.commit()
    
    cursor.execute('SELECT balance, last_daily FROM users WHERE user_id = ?', (user.id,))
    data = cursor.fetchone()
    conn.close()
    return {'balance': data[0], 'last_daily': data[1]}

async def save_balance(user_id: int, amount: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# --- КОМАНДЫ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = await get_user(update)
    await update.message.reply_text(
        f"👋 Привет, {update.effective_user.first_name}! \n"
        f"Твой баланс: {user_data['balance']:,} 🪙\n\n"
        "Доступные команды:\n"
        "/balance - Проверить счет\n"
        "/daily - Забрать ежедневный бонус\n"
        "/top - Лидеры сервера\n"
        "/shop - Магазин предметов\n"
        "\n🎲 Казино:\n"
        "/coin <ставка> - Орел или Решка (x2)\n"
        "/dice <ставка> - Кости 1-6 (x2)"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = await get_user(update)
    await update.message.reply_text(f"💰 Ваш текущий баланс: {user_data['balance']:,} 🪙")

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
    await update.message.reply_text(msg)

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = datetime.date.today()
    
    user_data = await get_user(update)
    last_date_str = user_data['last_daily']
    
    if last_date_str:
        last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d').date()
        days_passed = (today - last_date).days
    else:
        days_passed = 1

    if days_passed < 1:
        await update.message.reply_text("❌ Вы уже забирали бонус сегодня.")
        return

    bonus = DAILY_START * days_passed
    new_balance = user_data['balance'] + bonus
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?', 
                   (new_balance, today.isoformat(), user.id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Успех! Вы забрали бонус за {days_passed} день/дня: {bonus:,} 🪙.\nНовый баланс: {new_balance:,} 🪙")

# --- КАЗИНО ---

async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используйте: /coin <сумма>")
        return
        
    try:
        bet = int(context.args[0].replace(',', '').replace(' ', ''))
    except ValueError:
        await update.message.reply_text("Ставка должна быть числом.")
        return

    user_data = await get_user(update)
    if bet > user_data['balance'] or bet <= 0:
        await update.message.reply_text("Недостаточно средств или неверная сумма.")
        return

    choice = random.choice(['орел', 'решка'])
    result = random.choice(['орел', 'решка'])
    
    win = choice == result
    outcome = "выиграли!" if win else "проиграли."
    multiplier = 2 if win else 0
    
    new_bal = user_data['balance'] + (bet * multiplier) - bet
    await save_balance(update.effective_user.id, new_bal)
    
    await update.message.reply_text(
        f"Вы поставили {bet:,} 🪙 на '{choice}'.\n"
        f"Выпало: '{result}'.\n"
        f"Вы {outcome}\n"
        f"Баланс: {new_bal:,} 🪙"
    )

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используйте: /dice <сумма>")
        return
        
    try:
        bet = int(context.args[0].replace(',', '').replace(' ', ''))
    except ValueError:
        await update.message.reply_text("Ставка должна быть числом.")
        return

    user_data = await get_user(update)
    if bet > user_data['balance'] or bet <= 0:
        await update.message.reply_text("Недостаточно средств или неверная сумма.")
        return

    user_num = random.randint(1, 6)
    bot_num = random.randint(1, 6)
    
    win = user_num > bot_num
    draw = user_num == bot_num
    
    if draw:
        await update.message.reply_text(
            f"Ничья! У вас {user_num}, у бота {bot_num}. Ставка возвращена.\n"
            f"Баланс: {user_data['balance']:,} 🪙"
        )
        return

    multiplier = 2 if win else 0
    new_bal = user_data['balance'] + (bet * multiplier) - bet
    await save_balance(update.effective_user.id, new_bal)
    
    status = "Победа!" if win else "Поражение."
    await update.message.reply_text(
        f"Вы бросили кубик: {user_num}. Бот бросил: {bot_num}.\n"
        f"{status}\n"
        f"Баланс: {new_bal:,} 🪙"
    )

# --- МАГАЗИН ---

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT item_id, name, price, description FROM shop')
    items = cursor.fetchall()
    conn.close()

    keyboard = []
    for item in items:
        btn = InlineKeyboardButton(
            text=f"{item[1]} ({item[2]:,} 🪙)",
            callback_data=f"buy_{item[0]}"
        )
        keyboard.append([btn])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🛍 Добро пожаловать в магазин:", reply_markup=reply_markup)

# Для обработки нажатий на кнопки потребуется отдельный handler (обработчик CallbackQuery)
# Его добавление требует расширения логики файла примерно на 30-40 строк кода.

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token("8563921943:AAFk0nmJRGUlFjGHJmrhl1hu4X49Zo0w8BU").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("top", top))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("coin", coin))
    application.add_handler(CommandHandler("dice", dice))
    application.add_handler(CommandHandler("shop", shop))
    
    print("Игровой бот запущен!")
    application.run_polling()
