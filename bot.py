import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
import datetime
import random
import emoji


# --- БАЗА ДАННЫХ ---
DB_NAME = 'casino.db'
DAILY_START = 10_000
DAILY_INCREMENT = 10_000

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
    
    # Заполним магазин базовыми предметами, если он пуст
    cursor.execute("SELECT COUNT(*) FROM shop")
    if cursor.fetchone()[0] == 0:
        items = [
            ('Счастливая монета', 50_000, 'Увеличивает шанс выигрыша'),
            ('Удвоитель опыта', 75_000, 'Временно удваивает все выигрыши'),
            ('VIP-статус', 200_000, 'Открывает эксклюзивные игры')
        ]
        cursor.executemany('INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items)
        
    conn.commit()
    conn.close()


async def get_user(update: Update):
    """Получаем данные пользователя из базы"""
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
        (user.id, user.username))
    conn.commit()
    
    cursor.execute('SELECT balance, last_daily FROM users WHERE user_id = ?', (user.id,))
    data = cursor.fetchone()
    conn.close()
    return {'balance': data[0], 'last_daily': data[1]}


async def save_balance(user_id: int, amount: int):
    """Сохраняем баланс пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками"""
    user_data = await get_user(update)
    keyboard = [
        [InlineKeyboardButton(f'💰 Баланс: {user_data["balance"]:,} 🪙', callback_data='balance')],
        [InlineKeyboardButton(emoji.emojize(':game_die: Казино'), callback_data='casino')],
        [InlineKeyboardButton(emoji.emojize(':shopping_cart: Магазин'), callback_data='shop')],
        [InlineKeyboardButton(emoji.emojize(':calendar: Ежедневный бонус'), callback_data='daily')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{update.effective_user.first_name}*!\nВыбери действие:"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


# --- ОБРАБОТЧИК КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие
    
    action = query.data.split('_')[0]
    
    match action:
        case 'balance':
            user_data = await get_user(update)
            await query.edit_message_text(
                text=f"Твой текущий баланс: *{user_data['balance']:,}* 🪙",
                parse_mode="Markdown"
            )
            
        case 'daily':
            await daily(query, context)
            
        case 'shop':
            await shop(query, context)
            
        case 'casino':
            casino_keyboard = [
                [InlineKeyboardButton(emoji.emojize(':money_with_wings: Орел / Решка'), callback_data='coin')],
                [InlineKeyboardButton(emoji.emojize(':game_dice: Кости'), callback_data='dice')],
                [InlineKeyboardButton(emoji.emojize(':back_arrow: Назад'), callback_data='mainmenu')]
            ]
            await query.edit_message_text(
                text="*Выберите игру:*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(casino_keyboard)
            )
            
        case 'coin' | 'dice':
            game = {
                'coin': ['орел', 'решка'],
                'dice': ['выпадение кубика']
            }[action]
            
            msg = f"Введите сумму ставки для игры \"*{game}*\":\n\n" \
                  f"(текущий баланс: *(await get_user(update)['balance']:,)* 🪙)"
            await query.edit_message_text(msg, parse_mode="Markdown")
            # Сохраняем выбранную игру в контекст, чтобы потом её обработать
            context.user_data['selected_game'] = action


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
    await update.message.reply_text(msg)


async def daily(query, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    user = query.from_user
    
    user_data = await get_user(query)
    last_date_str = user_data['last_daily']
    
    if last_date_str:
        last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d').date()
        days_passed = (today - last_date).days
    else:
        days_passed = 1

    if days_passed < 1:
        await query.edit_message_text("❌ Вы уже забирали бонус сегодня.")
        return

    bonus = DAILY_START + (DAILY_INCREMENT * max(0, days_passed - 1))  # Увеличивается со второго дня
    new_balance = user_data['balance'] + bonus
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?',
        (new_balance, today.isoformat(), user.id))
    conn.commit()
    conn.close()

    await query.edit_message_text(
        f"✅ Успех! Вы забрали бонус за {days_passed} день/дня: *{bonus:,}* 🪙.\nНовый баланс: *{new_balance:,}* 🪙",
        parse_mode="Markdown"
    )


# --- ИГРОПРОВОДНИК —

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Эта функция срабатывает после того, как игрок нажал кнопку игры 
    (например, "Орел / Решка") и написал свою ставку.
    Она определяет тип игры и запускает её.
    """
    try:
        bet = int(update.message.text.replace(',', '').replace(' ', ''))
    except ValueError:
        await update.
