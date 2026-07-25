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
        return {
            "users": {},
            "shop": [
                {"id": 1, "name": "🏪 Бизнес", "price": 100000, "desc": "Приносит 5000🪙 каждый час"},
                {"id": 2, "name": "🌾 Ферма", "price": 50000, "desc": "Приносит 2000🪙 каждый час"},
                {"id": 3, "name": "💎 VIP-статус", "price": 200000, "desc": "Удвоение всех выигрышей"},
            ]
        }
    except:
        return {
            "users": {},
            "shop": [
                {"id": 1, "name": "🏪 Бизнес", "price": 100000, "desc": "Приносит 5000🪙 каждый час"},
                {"id": 2, "name": "🌾 Ферма", "price": 50000, "desc": "Приносит 2000🪙 каждый час"},
                {"id": 3, "name": "💎 VIP-статус", "price": 200000, "desc": "Удвоение всех выигрышей"},
            ]
        }

# Сохранение данных
def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ Данные сохранены!")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

# Получить пользователя
def get_user(data, user_id, username=None):
    user_id = str(user_id)
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "username": username or f"User{user_id[:6]}",
            "balance": 10000,
            "last_daily": None,
            "current_game": None,
            "business": False,
            "farm": False,
            "vip": False,
            "register_date": datetime.date.today().isoformat()
        }
        save_data(data)
    elif username and data["users"][user_id].get("username") != username:
        data["users"][user_id]["username"] = username
        save_data(data)
    return data["users"][user_id]

# Получить позицию в топе
def get_top_position(data, user_id):
    user_id = str(user_id)
    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1]["balance"],
        reverse=True
    )
    for i, (uid, _) in enumerate(sorted_users, 1):
        if uid == user_id:
            return i
    return len(sorted_users) + 1 if sorted_users else 1

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
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
    username = query.from_user.username or query.from_user.first_name
    data = load_data()
    user = get_user(data, user_id, username)
    
    # Профиль
    if query.data == "profile":
        top_pos = get_top_position(data, user_id)
        total_users = len(data["users"])
        reg_date = user.get("register_date", "Неизвестно")
        
        # Определяем статусы
        business_status = "✅ Есть" if user.get("business") else "❌ Нет"
        farm_status = "✅ Есть" if user.get("farm") else "❌ Нет"
        vip_status = "👑 VIP" if user.get("vip") else "⭐ Обычный"
        
        profile_text = (
            f"👤 *Профиль игрока*\n\n"
            f"📛 *Имя:* `{user['username']}`\n"
            f"🆔 *ID:* `{user_id}`\n\n"
            f"💰 *Баланс:* `{user['balance']:,}` 🪙\n"
            f"📅 *Дата регистрации:* `{reg_date}`\n"
            f"🏆 *Место в топе:* `{top_pos}` из `{total_users}`\n\n"
            f"🏪 *Бизнес:* {business_status}\n"
            f"🌾 *Ферма:* {farm_status}\n"
            f"💎 *Статус:* {vip_status}"
        )
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="back")]]
        await query.edit_message_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Казино
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
    
    # Выбор игры
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
    
    # Отмена ставки
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
    
    # Ежедневный бонус
    elif query.data == "daily":
        today = datetime.date.today().isoformat()
        
        if user["last_daily"] != today:
            bonus = DAILY_START
            # VIP получает двойной бонус
            if user.get("vip"):
                bonus *= 2
            
            user["balance"] += bonus
            user["last_daily"] = today
            save_data(data)
            
            vip_text = " (VIP x2)" if user.get("vip") else ""
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            await query.edit_message_text(
                f"✅ *Бонус получен!{vip_text}*\n\n🎁 Бонус: `+{bonus:,}` 🪙\n💰 Баланс: `{user['balance']:,}` 🪙",
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
    
    # Магазин
    elif query.data == "shop":
        buttons = []
        for item in data["shop"]:
            # Проверяем, есть ли уже этот предмет у пользователя
            if item["id"] == 1 and user.get("business"):
                buttons.append([InlineKeyboardButton(
                    f"🏪 Бизнес - КУПЛЕНО ✅",
                    callback_data="owned"
                )])
            elif item["id"] == 2 and user.get("farm"):
                buttons.append([InlineKeyboardButton(
                    f"🌾 Ферма - КУПЛЕНО ✅",
                    callback_data="owned"
                )])
            elif item["id"] == 3 and user.get("vip"):
                buttons.append([InlineKeyboardButton(
                    f"💎 VIP - АКТИВЕН ✅",
                    callback_data="owned"
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    f"{item['name']} - {item['price']:,} 🪙",
                    callback_data=f"buy_{item['id']}"
                )])
        buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back")])
        
        text = "🛍 *Магазин*\n\n*Товары:*\n"
        for item in data["shop"]:
            owned = False
            if item["id"] == 1 and user.get("business"):
                owned = True
            elif item["id"] == 2 and user.get("farm"):
                owned = True
            elif item["id"] == 3 and user.get("vip"):
                owned = True
            
            status = "✅ Куплено" if owned else f"💵 Цена: `{item['price']:,}` 🪙"
            text += f"\n📦 *{item['name']}*\n{status}\n📝 {item['desc']}\n"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    # Покупка
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
        
        # Проверяем, не куплен ли уже
        if item_id == 1 and user.get("business"):
            await query.answer("У вас уже есть бизнес!")
            return
        elif item_id == 2 and user.get("farm"):
            await query.answer("У вас уже есть ферма!")
            return
        elif item_id == 3 and user.get("vip"):
            await query.answer("У вас уже есть VIP-статус!")
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
        
        # Устанавливаем флаг покупки
        if item_id == 1:
            user["business"] = True
        elif item_id == 2:
            user["farm"] = True
        elif item_id == 3:
            user["vip"] = True
        
        save_data(data)
        
        keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
        await query.edit_message_text(
            f"✅ *Покупка успешна!*\n📦 Товар: *{item['name']}*\n💵 Потрачено: `{item['price']:,}` 🪙\n💰 Баланс: `{user['balance']:,}` 🪙",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Уже куплено
    elif query.data == "owned":
        await query.answer("Этот предмет уже куплен!")
    
    # Топ
    elif query.data == "top":
        sorted_users = sorted(
            data["users"].items(),
            key=lambda x: x[1]["balance"],
            reverse=True
        )[:10]
        
        msg = "🏆 *Топ-10 игроков:*\n\n"
        for i, (uid, u_data) in enumerate(sorted_users, 1):
            name = u_data.get("username", f"ID:{uid[:8]}")
            vip_icon = "👑 " if u_data.get("vip") else ""
            msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '👤'} {i}. {vip_icon}{name}: `{u_data['balance']:,}` 🪙\n"
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="back")]]
        await query.edit_message_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Назад в меню
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
            [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
            [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
            [InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
        ]
        await query.edit_message_text(
            "🎰 *Главное меню*\n\nВыбери действие:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Обработка сообщений (ставки)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or update.message.from_user.first_name
    data = load_data()
    user = get_user(data, user_id, username)
    
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
    
    # Множитель для VIP
    vip_multiplier = 2 if user.get("vip") else 1
    
    # Игры
    if user["current_game"] == "coin":
        coin = random.choice(["орёл", "решка"])
        won = random.choice([True, False])
        if won:
            win = bet * 2 * vip_multiplier
            msg = f"🪙 Монетка: *{coin}*\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🪙 Монетка: *{coin}*\n❌ Проигрыш -{bet:,} 🪙"
    
    elif user["current_game"] == "dice":
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2 * vip_multiplier
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
    
    vip_text = " (VIP x2)" if user.get("vip") and win > 0 else ""
    await update.message.reply_text(
        f"{msg}{vip_text}\n💰 Баланс: `{user['balance']:,}` 🪙",
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
        name = u_data.get("username", f"ID:{uid[:8]}")
        vip_icon = "👑 " if u_data.get("vip") else ""
        msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '👤'} {i}. {vip_icon}{name}: `{u_data['balance']:,}` 🪙\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# Команда /profile
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name
    data = load_data()
    user = get_user(data, user_id, username)
    
    top_pos = get_top_position(data, user_id)
    total_users = len(data["users"])
    reg_date = user.get("register_date", "Неизвестно")
    
    business_status = "✅ Есть" if user.get("business") else "❌ Нет"
    farm_status = "✅ Есть" if user.get("farm") else "❌ Нет"
    vip_status = "👑 VIP" if user.get("vip") else "⭐ Обычный"
    
    profile_text = (
        f"👤 *Профиль игрока*\n\n"
        f"📛 *Имя:* `{user['username']}`\n"
        f"🆔 *ID:* `{user_id}`\n\n"
        f"💰 *Баланс:* `{user['balance']:,}` 🪙\n"
        f"📅 *Дата регистрации:* `{reg_date}`\n"
        f"🏆 *Место в топе:* `{top_pos}` из `{total_users}`\n\n"
        f"🏪 *Бизнес:* {business_status}\n"
        f"🌾 *Ферма:* {farm_status}\n"
        f"💎 *Статус:* {vip_status}"
    )
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')

# Запуск
def main():
    print("🚀 Запуск бота...")
    
    if not os.path.exists(DATA_FILE):
        initial_data = {
            "users": {},
            "shop": [
                {"id": 1, "name": "🏪 Бизнес", "price": 100000, "desc": "Приносит 5000🪙 каждый час"},
                {"id": 2, "name": "🌾 Ферма", "price": 50000, "desc": "Приносит 2000🪙 каждый час"},
                {"id": 3, "name": "💎 VIP-статус", "price": 200000, "desc": "Удвоение всех выигрышей"},
            ]
        }
        save_data(initial_data)
        print("✅ Создан новый файл данных")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
