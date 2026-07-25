import json
import os
import datetime
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Токен
TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError("API_TOKEN не найден!")

# Настройки
DATA_FILE = "data.json"
DAILY_START = 10000

# Загрузка данных
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"users": {}, "shop": [
            {"id": 1, "name": "Счастливая монета", "price": 50000, "desc": "Увеличивает шанс выигрыша"},
            {"id": 2, "name": "Удвоитель опыта", "price": 75000, "desc": "Временное удвоение выигрышей"},
            {"id": 3, "name": "VIP-статус", "price": 200000, "desc": "Эксклюзивные игры"},
        ]}
    except:
        return {"users": {}, "shop": [
            {"id": 1, "name": "Счастливая монета", "price": 50000, "desc": "Увеличивает шанс выигрыша"},
            {"id": 2, "name": "Удвоитель опыта", "price": 75000, "desc": "Временное удвоение выигрышей"},
            {"id": 3, "name": "VIP-статус", "price": 200000, "desc": "Эксклюзивные игры"},
        ]}

# Сохранение данных
def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ Данные сохранены!")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

# Получить пользователя
def get_user(data, user_id):
    user_id = str(user_id)
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": 10000,
            "last_daily": None,
            "current_game": None
        }
        save_data(data)
    return data["users"][user_id]

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user = update.effective_user
    text = f"🎰 *Казино-Бот*\n\nПривет, *{user.first_name}*!\nВыбери действие:"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = load_data()
    user = get_user(data, user_id)
    
    if query.data == "balance":
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="back")]]
        await query.edit_message_text(
            f"💰 *Ваш баланс*\n\n`{user['balance']:,}` 🪙",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "casino":
        keyboard = [
            [InlineKeyboardButton("🪙 Орел/Решка", callback_data="coin")],
            [InlineKeyboardButton("🎲 Кости", callback_data="dice")],
            [InlineKeyboardButton("↩️ Назад", callback_data="back")],
        ]
        await query.edit_message_text(
            "🎰 *Казино*\n\nВыберите игру:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data in ["coin", "dice"]:
        game_name = "Орел/Решка" if query.data == "coin" else "Кости"
        user["current_game"] = query.data
        save_data(data)
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
        await query.edit_message_text(
            f"🎮 *{game_name}*\n\n💰 Баланс: `{user['balance']:,}` 🪙\n\n✏️ *Введите ставку числом:*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "cancel":
        user["current_game"] = None
        save_data(data)
        
        keyboard = [
            [InlineKeyboardButton("🎲 В казино", callback_data="casino")],
            [InlineKeyboardButton("↩️ Меню", callback_data="back")]
        ]
        await query.edit_message_text(
            "❌ Ставка отменена",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "daily":
        today = datetime.date.today().isoformat()
        
        if user["last_daily"] != today:
            user["balance"] += DAILY_START
            user["last_daily"] = today
            save_data(data)
            
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            await query.edit_message_text(
                f"✅ *Бонус получен!*\n\n🎁 Бонус: `+{DAILY_START:,}` 🪙\n💰 Баланс: `{user['balance']:,}` 🪙",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            await query.edit_message_text(
                "❌ *Бонус уже получен!*\nПриходите завтра!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif query.data == "shop":
        buttons = []
        for item in data["shop"]:
            buttons.append([InlineKeyboardButton(
                f"{item['name']} - {item['price']:,} 🪙",
                callback_data=f"buy_{item['id']}"
            )])
        buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back")])
        
        text = "🛍 *Магазин*\n\n*Товары:*\n"
        for item in data["shop"]:
            text += f"\n📦 *{item['name']}*\n💵 Цена: `{item['price']:,}` 🪙\n📝 {item['desc']}\n"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif query.data.startswith("buy_"):
        item_id = int(query.data.split("_")[1])
        
        item = None
        for shop_item in data["shop"]:
            if shop_item["id"] == item_id:
                item = shop_item
                break
        
        if not item:
            await query.edit_message_text("❌ Товар не найден")
            return
        
        if user["balance"] < item["price"]:
            keyboard = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
            await query.edit_message_text(
                f"❌ *Недостаточно средств!*\n💰 Баланс: `{user['balance']:,}` 🪙\n💵 Цена: `{item['price']:,}` 🪙",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        user["balance"] -= item["price"]
        save_data(data)
        
        keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
        await query.edit_message_text(
            f"✅ *Покупка успешна!*\n📦 Товар: *{item['name']}*\n💵 Потрачено: `{item['price']:,}` 🪙\n💰 Баланс: `{user['balance']:,}` 🪙",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "top":
        # Сортируем пользователей по балансу
        sorted_users = sorted(
            data["users"].items(),
            key=lambda x: x[1]["balance"],
            reverse=True
        )[:10]
        
        msg = "🏆 *Топ-10 игроков:*\n\n"
        for i, (uid, u_data) in enumerate(sorted_users, 1):
            # Пробуем получить username из контекста
            username = f"ID:{uid[:8]}"
            msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '👤'} {i}. {username}: `{u_data['balance']:,}` 🪙\n"
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="back")]]
        await query.edit_message_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
            [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
            [InlineKeyboardButton("🗓 Бонус", callback_data="daily")],
            [InlineKeyboardButton("🏆 Топ", callback_data="top")],
        ]
        await query.edit_message_text(
            "🎰 *Главное меню*\n\nВыбери действие:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Обработка сообщений (ставки)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()
    user = get_user(data, user_id)
    
    if not user["current_game"]:
        return
    
    try:
        bet = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите целое число!")
        return
    
    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше нуля!")
        return
    
    if bet > user["balance"]:
        await update.message.reply_text(
            f"❌ *Недостаточно средств!*\n💰 Баланс: `{user['balance']:,}` 🪙",
            parse_mode='Markdown'
        )
        return
    
    # Игры
    if user["current_game"] == "coin":
        coin = random.choice(["орёл", "решка"])
        won = random.choice([True, False])
        if won:
            win = bet * 2
            msg = f"🪙 Монетка: *{coin}*\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🪙 Монетка: *{coin}*\n❌ Проигрыш -{bet:,} 🪙"
    
    elif user["current_game"] == "dice":
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2
            msg = f"🎲 {d1}+{d2}=*{total}* (Чёт)\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🎲 {d1}+{d2}=*{total}* (Нечет)\n❌ Проигрыш -{bet:,} 🪙"
    
    user["balance"] = user["balance"] - bet + win
    user["current_game"] = None
    save_data(data)
    
    keyboard = [
        [InlineKeyboardButton("🎲 Играть еще", callback_data="casino")],
        [InlineKeyboardButton("↩️ Меню", callback_data="back")]
    ]
    
    await update.message.reply_text(
        f"{msg}\n💰 Баланс: `{user['balance']:,}` 🪙",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команда /top
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1]["balance"],
        reverse=True
    )[:10]
    
    msg = "🏆 *Топ-10 игроков:*\n\n"
    for i, (uid, u_data) in enumerate(sorted_users, 1):
        username = f"ID:{uid[:8]}"
        msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '👤'} {i}. {username}: `{u_data['balance']:,}` 🪙\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# Запуск
def main():
    print("🚀 Запуск бота...")
    
    # Создаем файл данных если его нет
    if not os.path.exists(DATA_FILE):
        initial_data = {
            "users": {},
            "shop": [
                {"id": 1, "name": "Счастливая монета", "price": 50000, "desc": "Увеличивает шанс выигрыша"},
                {"id": 2, "name": "Удвоитель опыта", "price": 75000, "desc": "Временное удвоение выигрышей"},
                {"id": 3, "name": "VIP-статус", "price": 200000, "desc": "Эксклюзивные игры"},
            ]
        }
        save_data(initial_data)
        print("✅ Создан новый файл данных")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
