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
DATA_FILE = "user_data.json"
DAILY_START = 10000

# Глобальная база данных (хранится в памяти)
DB = {}

# Загрузка данных при старте
def load_database():
    global DB
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    DB = json.loads(content)
                    print(f"✅ Загружено пользователей: {len(DB)}")
                    return True
    except Exception as e:
        print(f"⚠️ Ошибка загрузки: {e}")
    
    DB = {}
    print("📄 Новая база данных")
    return False

# Сохранение данных
def save_database():
    global DB
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(DB, f, ensure_ascii=False, indent=2)
        print(f"💾 Сохранено: {len(DB)} пользователей")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

# Получить/создать пользователя
def get_user(user_id, username=None):
    global DB
    uid = str(user_id)
    
    if uid not in DB:
        DB[uid] = {
            "name": username or f"Player{uid[:6]}",
            "balance": 10000,
            "last_daily": None,
            "current_game": None,
            "business": False,
            "mining": False,
            "vip": False,
            "reg_date": datetime.date.today().isoformat(),
            "earned": 0,
            "lost": 0,
            "games": 0
        }
        save_database()
        print(f"👤 Новый игрок: {uid}")
    
    # Обновляем имя если изменилось
    if username and DB[uid]["name"] != username:
        DB[uid]["name"] = username
        save_database()
    
    return DB[uid]

# Позиция в топе
def get_top_position(user_id):
    uid = str(user_id)
    if not DB:
        return 1, 1
    
    sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)
    for i, (u_id, _) in enumerate(sorted_users, 1):
        if u_id == uid:
            return i, len(sorted_users)
    return len(sorted_users) + 1, len(sorted_users) + 1

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name
    
    # Создаем пользователя
    get_user(user_id, username)
    
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ]
    
    await update.message.reply_text(
        f"🎰 *Lucky Casino*\n\nПривет, *{user.first_name}*!\nБаланс сохранен 💾",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Обработчик кнопок
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    name = query.from_user.username or query.from_user.first_name
    user = get_user(uid, name)
    
    # === ПРОФИЛЬ ===
    if query.data == "profile":
        pos, total = get_top_position(uid)
        
        text = (
            f"👤 *Профиль*\n\n"
            f"💰 Баланс: `{user['balance']:,}` 🪙\n"
            f"📅 С нами с: `{user['reg_date']}`\n"
            f"🏆 Топ: `{pos}` из `{total}`\n"
            f"🎮 Игр сыграно: `{user['games']}`\n\n"
            f"🏪 Бизнес: {'✅' if user['business'] else '❌'}\n"
            f"⛏ Майнинг: {'✅' if user['mining'] else '❌'}\n"
            f"💎 Статус: {'👑 VIP' if user['vip'] else '⭐ Обычный'}\n\n"
            f"💚 Заработано: `{user['earned']:,}` 🪙\n"
            f"💔 Проиграно: `{user['lost']:,}` 🪙"
        )
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === КАЗИНО ===
    elif query.data == "casino":
        keyboard = [
            [InlineKeyboardButton("🪙 Монетка (x2)", callback_data="game_coin")],
            [InlineKeyboardButton("🎲 Кости (x2)", callback_data="game_dice")],
            [InlineKeyboardButton("🎰 Слоты (x5)", callback_data="game_slots")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")],
        ]
        await query.edit_message_text(
            f"🎰 *Казино*\n💰 Баланс: `{user['balance']:,}` 🪙\n\nВыберите игру:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # === ВЫБОР ИГРЫ ===
    elif query.data in ["game_coin", "game_dice", "game_slots"]:
        games = {
            "game_coin": "🪙 Монетка",
            "game_dice": "🎲 Кости",
            "game_slots": "🎰 Слоты"
        }
        user["current_game"] = query.data
        save_database()
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
        await query.edit_message_text(
            f"*{games[query.data]}*\n\n💰 Баланс: `{user['balance']:,}` 🪙\n\nВведите ставку:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # === ОТМЕНА ===
    elif query.data == "cancel":
        user["current_game"] = None
        save_database()
        
        keyboard = [
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]
        await query.edit_message_text("❌ Отменено", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === БОНУС ===
    elif query.data == "daily":
        today = datetime.date.today().isoformat()
        
        if user.get("last_daily") != today:
            bonus = DAILY_START
            parts = [f"🎁 Базовый: +{DAILY_START:,}"]
            
            if user.get("business"):
                bonus += 5000
                parts.append("🏪 Бизнес: +5,000")
            if user.get("mining"):
                bonus += 2000
                parts.append("⛏ Майнинг: +2,000")
            if user.get("vip"):
                bonus *= 2
                parts.append("💎 VIP x2")
            
            user["balance"] += bonus
            user["last_daily"] = today
            user["earned"] += bonus
            save_database()
            
            text = f"✅ *Бонус получен!*\n\n" + "\n".join(parts) + f"\n\n💰 Итого: `+{bonus:,}` 🪙\n💳 Баланс: `{user['balance']:,}` 🪙"
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
            await query.edit_message_text("❌ Уже получен!\n⏰ Завтра будет снова", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === ТОП ===
    elif query.data == "top":
        sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        
        text = "🏆 *Топ-10*\n\n"
        for i, (u_id, u_data) in enumerate(sorted_users, 1):
            name = u_data["name"][:15]
            vip = "👑" if u_data.get("vip") else ""
            text += f"{['🥇','🥈','🥉'][i-1] if i<4 else '👤'} {i}. {vip}{name}: `{u_data['balance']:,}` 🪙\n"
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === МЕНЮ ===
    elif query.data == "menu":
        keyboard = [
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
            [InlineKeyboardButton("🏆 Топ", callback_data="top")],
        ]
        await query.edit_message_text(
            "🎰 *Меню*\nВыберите действие:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Обработка ставок
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    name = update.message.from_user.username or update.message.from_user.first_name
    user = get_user(uid, name)
    
    if not user.get("current_game"):
        return
    
    try:
        bet = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите число!")
        return
    
    if bet < 1:
        await update.message.reply_text("❌ Минимум 1!")
        return
    
    if bet > user["balance"]:
        await update.message.reply_text(f"❌ Мало средств!\n💰 Баланс: `{user['balance']:,}`", parse_mode='Markdown')
        return
    
    vip = 2 if user.get("vip") else 1
    game = user["current_game"]
    win = 0
    
    # Монетка
    if game == "game_coin":
        coin = random.choice(["Орёл", "Решка"])
        if random.random() < 0.5:
            win = bet * 2 * vip
            msg = f"🪙 {coin}\n✅ Победа! +{win-bet:,}"
        else:
            msg = f"🪙 {coin}\n❌ Проигрыш -{bet:,}"
    
    # Кости
    elif game == "game_dice":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2 * vip
            msg = f"🎲 {d1}+{d2}={total} (Чёт)\n✅ Победа! +{win-bet:,}"
        else:
            msg = f"🎲 {d1}+{d2}={total} (Нечет)\n❌ Проигрыш -{bet:,}"
    
    # Слоты
    elif game == "game_slots":
        s = random.choices(["🍒","🍋","🍊","7️⃣","💎","⭐"], k=3)
        if s[0] == s[1] == s[2]:
            win = bet * 5 * vip
            msg = f"🎰 {' '.join(s)}\n🎉 ДЖЕКПОТ! +{win-bet:,}"
        elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
            win = bet * 2 * vip
            msg = f"🎰 {' '.join(s)}\n✅ Победа! +{win-bet:,}"
        else:
            msg = f"🎰 {' '.join(s)}\n❌ Проигрыш -{bet:,}"
    
    # Обновление
    user["balance"] += win - bet
    user["games"] += 1
    if win > 0:
        user["earned"] += win - bet
    else:
        user["lost"] += bet
    user["current_game"] = None
    save_database()
    
    keyboard = [
        [InlineKeyboardButton("🎰 Играть", callback_data="casino")],
        [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
    ]
    
    await update.message.reply_text(
        f"{msg}\n💰 Баланс: `{user['balance']:,}` 🪙",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команды
async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    text = "🏆 *Топ-10*\n\n"
    for i, (_, u) in enumerate(sorted_users, 1):
        text += f"{i}. {u['name'][:15]}: `{u['balance']:,}` 🪙\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    name = update.effective_user.username or update.effective_user.first_name
    user = get_user(uid, name)
    await update.message.reply_text(f"💰 `{user['balance']:,}` 🪙", parse_mode='Markdown')

# Запуск
def main():
    print("🚀 Starting...")
    
    # Загружаем базу
    load_database()
    
    # Создаем приложение
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Хендлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))
    
    print("✅ Ready!")
    save_database()
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
