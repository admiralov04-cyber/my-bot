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

# Глобальная база данных
DB = {}

# Конфигурация видеокарт
VIDEO_CARDS = {
    1: {"name": "GTX 1060", "price": 30000, "income": 2500, "emoji": "🟢"},
    2: {"name": "RTX 2060", "price": 50000, "income": 4500, "emoji": "🔵"},
    3: {"name": "RTX 3060", "price": 70000, "income": 7000, "emoji": "🟣"},
    4: {"name": "RTX 4070", "price": 100000, "income": 11000, "emoji": "🟡"},
    5: {"name": "RTX 4090", "price": 150000, "income": 25000, "emoji": "🔴"},
}

# Конфигурация кейсов
CASES = {
    "common": {"name": "Обычный кейс", "price": 5000, "rewards": [1000, 2000, 3000, 5000, 10000]},
    "rare": {"name": "Редкий кейс", "price": 15000, "rewards": [5000, 10000, 20000, 35000, 50000]},
    "epic": {"name": "Эпический кейс", "price": 50000, "rewards": [15000, 30000, 50000, 100000, 200000]},
    "legendary": {"name": "Легендарный кейс", "price": 150000, "rewards": [50000, 100000, 200000, 500000, 1000000]},
}

# Загрузка данных
def load_database():
    global DB
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    DB = json.loads(content)
                    print(f"✅ Загружено: {len(DB)} пользователей")
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
            "vip": False,
            "video_card": 0,
            "mining_start": None,
            "mined_total": 0,
            "reg_date": datetime.date.today().isoformat(),
            "earned": 0,
            "lost": 0,
            "games": 0,
            "cases_opened": 0,
        }
        save_database()
        print(f"👤 Новый: {uid}")
    
    if username and DB[uid]["name"] != username:
        DB[uid]["name"] = username
        save_database()
    
    return DB[uid]

# Расчет дохода от майнинга
def calculate_mining_income(user):
    if user["video_card"] == 0 or not user.get("mining_start"):
        return 0
    
    card = VIDEO_CARDS.get(user["video_card"])
    if not card:
        return 0
    
    try:
        start_time = datetime.datetime.fromisoformat(user["mining_start"])
        now = datetime.datetime.now()
        hours_passed = (now - start_time).total_seconds() / 3600
        
        if hours_passed < 0:
            return 0
        
        income = int(hours_passed * card["income"])
        return income
    except:
        return 0

# Сбор дохода от майнинга
def collect_mining(user):
    income = calculate_mining_income(user)
    if income > 0:
        user["balance"] += income
        user["mined_total"] = user.get("mined_total", 0) + income
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_database()
        return income
    return 0

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
    
    get_user(user_id, username)
    
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
        [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")],
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ]
    
    await update.message.reply_text(
        f"🎰 *Lucky Casino*\n\nПривет, *{user.first_name}*!\nВыбери действие:",
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
        mining_income = collect_mining(user)
        user = get_user(uid, name)
        
        pos, total = get_top_position(uid)
        card_level = user.get("video_card", 0)
        card_info = VIDEO_CARDS.get(card_level, None)
        
        text = (
            f"👤 *Профиль*\n\n"
            f"💰 Баланс: `{user['balance']:,}` 🪙\n"
            f"📅 С нами с: `{user['reg_date']}`\n"
            f"🏆 Топ: `{pos}` из `{total}`\n"
            f"🎮 Игр: `{user['games']}`\n"
            f"🎁 Кейсов: `{user.get('cases_opened', 0)}`\n\n"
            f"⛏ *Майнинг:*\n"
        )
        
        if card_info:
            text += f"🖥 Карта: {card_info['emoji']} *{card_info['name']}*\n"
        else:
            text += "🖥 Карта: ❌ Нет\n"
        
        text += (
            f"💎 Намайнено: `{user.get('mined_total', 0):,}` 🪙\n"
            f"🏪 Бизнес: {'✅' if user['business'] else '❌'}\n"
            f"💎 Статус: {'👑 VIP' if user['vip'] else '⭐ Обычный'}\n\n"
            f"💚 Заработано: `{user['earned']:,}` 🪙\n"
            f"💔 Проиграно: `{user['lost']:,}` 🪙"
        )
        
        if mining_income > 0:
            text += f"\n\n✅ Собрано: `+{mining_income:,}` 🪙"
        
        keyboard = [
            [InlineKeyboardButton("⛏ Собрать майнинг", callback_data="collect_mining")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === СБОР МАЙНИНГА ===
    elif query.data == "collect_mining":
        income = collect_mining(user)
        if income > 0:
            await query.answer(f"✅ Собрано: {income:,} 🪙")
        else:
            await query.answer("❌ Нет дохода")
        
        await buttons(update, context)
        return
    
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
    
    # === МАЙНИНГ ===
    elif query.data == "mining":
        card_level = user.get("video_card", 0)
        card_info = VIDEO_CARDS.get(card_level)
        pending = calculate_mining_income(user)
        
        if card_info:
            text = (
                f"⛏ *Майнинг ферма*\n\n"
                f"🖥 Карта: {card_info['emoji']} *{card_info['name']}*\n"
                f"💰 Доход: `{card_info['income']:,}` 🪙/час\n"
                f"💎 Намайнено: `{user.get('mined_total', 0):,}` 🪙\n"
                f"⏳ Ожидает: `{pending:,}` 🪙\n\n"
                f"⚡ *Улучшить в магазине!*"
            )
        else:
            text = (
                f"⛏ *Майнинг ферма*\n\n"
                f"❌ Нет видеокарты!\n"
                f"🛍 Купите в магазине.\n\n"
                f"💰 *Доходы карт:*\n"
            )
            for level, card in VIDEO_CARDS.items():
                text += f"{card['emoji']} {card['name']}: `{card['income']:,}` 🪙/час\n"
        
        keyboard = []
        if pending > 0:
            keyboard.append([InlineKeyboardButton("💰 Собрать", callback_data="collect_mining")])
        keyboard.append([InlineKeyboardButton("🛍 В магазин", callback_data="shop")])
        keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="menu")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === КЕЙСЫ ===
    elif query.data == "cases":
        text = "🎁 *Кейсы*\n\nВыберите кейс:\n\n"
        
        for case_id, case in CASES.items():
            text += f"📦 *{case['name']}*: `{case['price']:,}` 🪙\n"
        
        keyboard = [
            [InlineKeyboardButton(f"📦 Обычный - {CASES['common']['price']:,}🪙", callback_data="open_common")],
            [InlineKeyboardButton(f"🎁 Редкий - {CASES['rare']['price']:,}🪙", callback_data="open_rare")],
            [InlineKeyboardButton(f"💎 Эпический - {CASES['epic']['price']:,}🪙", callback_data="open_epic")],
            [InlineKeyboardButton(f"👑 Легендарный - {CASES['legendary']['price']:,}🪙", callback_data="open_legendary")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")],
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === ОТКРЫТИЕ КЕЙСА ===
    elif query.data.startswith("open_"):
        case_type = query.data.replace("open_", "")
        case = CASES.get(case_type)
        
        if not case:
            await query.answer("Кейс не найден")
            return
        
        if user["balance"] < case["price"]:
            await query.answer(f"Нужно {case['price']:,} 🪙")
            return
        
        user["balance"] -= case["price"]
        reward = random.choice(case["rewards"])
        
        if random.random() < 0.05:
            reward = case["rewards"][-1]
        
        user["balance"] += reward
        user["cases_opened"] = user.get("cases_opened", 0) + 1
        user["earned"] = user.get("earned", 0) + reward
        save_database()
        
        text = (
            f"🎁 *Открытие кейса*\n\n"
            f"📦 *{case['name']}*\n"
            f"💵 Цена: `{case['price']:,}` 🪙\n"
            f"🎉 Выигрыш: `{reward:,}` 🪙\n"
            f"💰 Баланс: `{user['balance']:,}` 🪙"
        )
        
        if reward == case["rewards"][-1]:
            text += "\n\n🔥 *JACKPOT!*"
        
        keyboard = [
            [InlineKeyboardButton("🎁 Еще кейс", callback_data="cases")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === МАГАЗИН ===
    elif query.data == "shop":
        text = "🛍 *Магазин*\n\n*Видеокарты:*\n\n"
        
        for level, card in VIDEO_CARDS.items():
            owned = user.get("video_card", 0) >= level
            text += f"{card['emoji']} *{card['name']}*\n"
            text += f"💰 Доход: `{card['income']:,}` 🪙/час\n"
            text += f"💵 Цена: `{card['price']:,}` 🪙\n"
            text += f"Статус: {'✅ Куплена' if owned else '❌'}\n\n"
        
        text += (
            f"🏪 *Бизнес:*\n"
            f"💵 Цена: `100,000` 🪙\n"
            f"Статус: {'✅ Куплен' if user.get('business') else '❌'}\n\n"
            f"💎 *VIP:*\n"
            f"💵 Цена: `200,000` 🪙\n"
            f"Статус: {'✅ Активен' if user.get('vip') else '❌'}\n"
        )
        
        keyboard = []
        for level, card in VIDEO_CARDS.items():
            if user.get("video_card", 0) < level:
                keyboard.append([InlineKeyboardButton(
                    f"{card['emoji']} {card['name']} - {card['price']:,}🪙",
                    callback_data=f"buy_card_{level}"
                )])
        
        if not user.get("business"):
            keyboard.append([InlineKeyboardButton("🏪 Бизнес - 100,000🪙", callback_data="buy_business")])
        
        if not user.get("vip"):
            keyboard.append([InlineKeyboardButton("💎 VIP - 200,000🪙", callback_data="buy_vip")])
        
        keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="menu")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === ПОКУПКА КАРТЫ ===
    elif query.data.startswith("buy_card_"):
        level = int(query.data.replace("buy_card_", ""))
        card = VIDEO_CARDS.get(level)
        
        if not card:
            await query.answer("Карта не найдена")
            return
        
        if user.get("video_card", 0) >= level:
            await query.answer("У вас уже есть карта лучше!")
            return
        
        if user["balance"] < card["price"]:
            await query.answer(f"Нужно {card['price']:,} 🪙")
            return
        
        user["balance"] -= card["price"]
        user["video_card"] = level
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_database()
        
        await query.answer(f"Куплена {card['name']}!")
        
        keyboard = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
        await query.edit_message_text(
            f"✅ *Покупка!*\n\n"
            f"🖥 *{card['name']}*\n"
            f"💰 Доход: `{card['income']:,}` 🪙/час\n"
            f"💵 Цена: `{card['price']:,}` 🪙\n"
            f"💳 Баланс: `{user['balance']:,}` 🪙\n\n"
            f"⛏ Майнинг запущен!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # === ПОКУПКА БИЗНЕСА ===
    elif query.data == "buy_business":
        if user.get("business"):
            await query.answer("Уже куплен!")
            return
        
        if user["balance"] < 100000:
            await query.answer("Нужно 100,000 🪙")
            return
        
        user["balance"] -= 100000
        user["business"] = True
        save_database()
        
        await query.answer("Бизнес куплен!")
        
        keyboard = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
        await query.edit_message_text(
            "✅ *Бизнес куплен!*\n💰 +5,000 к бонусу",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # === ПОКУПКА VIP ===
    elif query.data == "buy_vip":
        if user.get("vip"):
            await query.answer("VIP уже активен!")
            return
        
        if user["balance"] < 200000:
            await query.answer("Нужно 200,000 🪙")
            return
        
        user["balance"] -= 200000
        user["vip"] = True
        save_database()
        
        await query.answer("VIP активирован!")
        
        keyboard = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
        await query.edit_message_text(
            "✅ *VIP активирован!*\n💰 x2 выигрыши и бонусы",
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
            if user.get("vip"):
                bonus *= 2
                parts.append("💎 VIP x2")
            
            user["balance"] += bonus
            user["last_daily"] = today
            user["earned"] += bonus
            save_database()
            
            text = f"✅ *Бонус!*\n\n" + "\n".join(parts) + f"\n\n💰 Итого: `+{bonus:,}` 🪙\n💳 Баланс: `{user['balance']:,}` 🪙"
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
            await query.edit_message_text("❌ Уже получен!\n⏰ Завтра снова", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === ТОП ===
    elif query.data == "top":
        sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        
        text = "🏆 *Топ-10*\n\n"
        for i, (u_id, u_data) in enumerate(sorted_users, 1):
            name = u_data["name"][:15]
            vip = "👑" if u_data.get("vip") else ""
            card = "⛏" if u_data.get("video_card", 0) > 0 else ""
            text += f"{['🥇','🥈','🥉'][i-1] if i<4 else '👤'} {i}. {vip}{card}{name}: `{u_data['balance']:,}` 🪙\n"
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # === МЕНЮ ===
    elif query.data == "menu":
        keyboard = [
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")],
            [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
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
    uid = str(upd
