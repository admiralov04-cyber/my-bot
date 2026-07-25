import json
import os
import datetime
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError("API_TOKEN не найден!")

DATA_FILE = "user_data.json"
DAILY_START = 10000
DB = {}

VIDEO_CARDS = {
    1: {"name": "GTX 1060", "price": 30000, "income": 2500, "emoji": "🟢"},
    2: {"name": "RTX 2060", "price": 50000, "income": 4500, "emoji": "🔵"},
    3: {"name": "RTX 3060", "price": 70000, "income": 7000, "emoji": "🟣"},
    4: {"name": "RTX 4070", "price": 100000, "income": 11000, "emoji": "🟡"},
    5: {"name": "RTX 4090", "price": 150000, "income": 25000, "emoji": "🔴"},
}

CASES = {
    "common": {"name": "Обычный кейс", "price": 5000, "rewards": [1000, 2000, 3000, 5000, 10000]},
    "rare": {"name": "Редкий кейс", "price": 15000, "rewards": [5000, 10000, 20000, 35000, 50000]},
    "epic": {"name": "Эпический кейс", "price": 50000, "rewards": [15000, 30000, 50000, 100000, 200000]},
    "legendary": {"name": "Легендарный кейс", "price": 150000, "rewards": [50000, 100000, 200000, 500000, 1000000]},
}

def load_database():
    global DB
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    DB = json.loads(content)
                    print(f"Loaded: {len(DB)} users")
                    return True
    except Exception as e:
        print(f"Load error: {e}")
    DB = {}
    return False

def save_database():
    global DB
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(DB, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False

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
    if username and DB[uid]["name"] != username:
        DB[uid]["name"] = username
        save_database()
    return DB[uid]

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
        return int(hours_passed * card["income"])
    except:
        return 0

def collect_mining(user):
    income = calculate_mining_income(user)
    if income > 0:
        user["balance"] += income
        user["mined_total"] = user.get("mined_total", 0) + income
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_database()
        return income
    return 0

def get_top_position(user_id):
    uid = str(user_id)
    if not DB:
        return 1, 1
    sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)
    for i, (u_id, _) in enumerate(sorted_users, 1):
        if u_id == uid:
            return i, len(sorted_users)
    return len(sorted_users) + 1, len(sorted_users) + 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    get_user(uid, user.username or user.first_name)
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
        f"🎰 *Lucky Casino*\n\nHi, *{user.first_name}*!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    name = query.from_user.username or query.from_user.first_name
    user = get_user(uid, name)
    
    if query.data == "profile":
        mining_income = collect_mining(user)
        user = get_user(uid, name)
        pos, total = get_top_position(uid)
        card_level = user.get("video_card", 0)
        card_info = VIDEO_CARDS.get(card_level)
        
        text = f"👤 *Profile*\n\n💰 Balance: `{user['balance']:,}`\n📅 Since: `{user['reg_date']}`\n🏆 Rank: `{pos}/{total}`\n🎮 Games: `{user['games']}`\n🎁 Cases: `{user.get('cases_opened', 0)}`\n\n⛏ *Mining:*\n"
        
        if card_info:
            text += f"🖥 Card: {card_info['emoji']} *{card_info['name']}*\n"
        else:
            text += "🖥 Card: ❌ None\n"
        
        text += f"💎 Mined: `{user.get('mined_total', 0):,}`\n🏪 Business: {'✅' if user['business'] else '❌'}\n💎 Status: {'👑 VIP' if user['vip'] else '⭐ Normal'}\n\n💚 Earned: `{user['earned']:,}`\n💔 Lost: `{user['lost']:,}`"
        
        if mining_income > 0:
            text += f"\n\n✅ Collected: `+{mining_income:,}`"
        
        keyboard = [
            [InlineKeyboardButton("⛏ Collect Mining", callback_data="collect_mining")],
            [InlineKeyboardButton("↩️ Back", callback_data="menu")]
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "collect_mining":
        income = collect_mining(user)
        if income > 0:
            await query.answer(f"Collected: {income:,}")
        else:
            await query.answer("No income")
        await button_handler(update, context)
    
    elif query.data == "casino":
        keyboard = [
            [InlineKeyboardButton("🪙 Coin (x2)", callback_data="game_coin")],
            [InlineKeyboardButton("🎲 Dice (x2)", callback_data="game_dice")],
            [InlineKeyboardButton("🎰 Slots (x5)", callback_data="game_slots")],
            [InlineKeyboardButton("↩️ Back", callback_data="menu")],
        ]
        await query.edit_message_text(
            f"🎰 *Casino*\n💰 Balance: `{user['balance']:,}`\n\nChoose game:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "mining":
        card_level = user.get("video_card", 0)
        card_info = VIDEO_CARDS.get(card_level)
        pending = calculate_mining_income(user)
        
        if card_info:
            text = f"⛏ *Mining Farm*\n\n🖥 Card: {card_info['emoji']} *{card_info['name']}*\n💰 Income: `{card_info['income']:,}`/hour\n💎 Mined: `{user.get('mined_total', 0):,}`\n⏳ Pending: `{pending:,}`"
        else:
            text = "⛏ *Mining Farm*\n\n❌ No card!\n🛍 Buy in shop.\n\n💰 *Card Incomes:*\n"
            for level, card in VIDEO_CARDS.items():
                text += f"{card['emoji']} {card['name']}: `{card['income']:,}`/hour\n"
        
        keyboard = []
        if pending > 0:
            keyboard.append([InlineKeyboardButton("💰 Collect", callback_data="collect_mining")])
        keyboard.append([InlineKeyboardButton("🛍 Shop", callback_data="shop")])
        keyboard.append([InlineKeyboardButton("↩️ Back", callback_data="menu")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "cases":
        keyboard = [
            [InlineKeyboardButton(f"📦 Common - {CASES['common']['price']:,}", callback_data="open_common")],
            [InlineKeyboardButton(f"🎁 Rare - {CASES['rare']['price']:,}", callback_data="open_rare")],
            [InlineKeyboardButton(f"💎 Epic - {CASES['epic']['price']:,}", callback_data="open_epic")],
            [InlineKeyboardButton(f"👑 Legendary - {CASES['legendary']['price']:,}", callback_data="open_legendary")],
            [InlineKeyboardButton("↩️ Back", callback_data="menu")],
        ]
        await query.edit_message_text(
            "🎁 *Cases*\n\nChoose case to open:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("open_"):
        case_type = query.data.replace("open_", "")
        case = CASES.get(case_type)
        
        if not case:
            await query.answer("Case not found")
            return
        
        if user["balance"] < case["price"]:
            await query.answer(f"Need {case['price']:,}")
            return
        
        user["balance"] -= case["price"]
        reward = random.choice(case["rewards"])
        if random.random() < 0.05:
            reward = case["rewards"][-1]
        
        user["balance"] += reward
        user["cases_opened"] = user.get("cases_opened", 0) + 1
        user["earned"] = user.get("earned", 0) + reward
        save_database()
        
        text = f"🎁 *Case Opened*\n\n📦 *{case['name']}*\n💵 Cost: `{case['price']:,}`\n🎉 Win: `{reward:,}`\n💰 Balance: `{user['balance']:,}`"
        if reward == case["rewards"][-1]:
            text += "\n\n🔥 *JACKPOT!*"
        
        keyboard = [
            [InlineKeyboardButton("🎁 Open More", callback_data="cases")],
            [InlineKeyboardButton("↩️ Menu", callback_data="menu")]
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "shop":
        text = "🛍 *Shop*\n\n*Video Cards:*\n\n"
        for level, card in VIDEO_CARDS.items():
            owned = user.get("video_card", 0) >= level
            text += f"{card['emoji']} *{card['name']}*\n💰 Income: `{card['income']:,}`/h\n💵 Price: `{card['price']:,}`\nStatus: {'✅ Owned' if owned else '❌'}\n\n"
        
        text += f"🏪 *Business:*\n💵 Price: `100,000`\nStatus: {'✅' if user.get('business') else '❌'}\n\n💎 *VIP:*\n💵 Price: `200,000`\nStatus: {'✅' if user.get('vip') else '❌'}\n"
        
        keyboard = []
        for level, card in VIDEO_CARDS.items():
            if user.get("video_card", 0) < level:
                keyboard.append([InlineKeyboardButton(f"{card['emoji']} {card['name']} - {card['price']:,}", callback_data=f"buy_card_{level}")])
        
        if not user.get("business"):
            keyboard.append([InlineKeyboardButton("🏪 Business - 100,000", callback_data="buy_business")])
        if not user.get("vip"):
            keyboard.append([InlineKeyboardButton("💎 VIP - 200,000", callback_data="buy_vip")])
        keyboard.append([InlineKeyboardButton("↩️ Back", callback_data="menu")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("buy_card_"):
        level = int(query.data.replace("buy_card_", ""))
        card = VIDEO_CARDS.get(level)
        if not card:
            await query.answer("Card not found")
            return
        if user.get("video_card", 0) >= level:
            await query.answer("Better card owned!")
            return
        if user["balance"] < card["price"]:
            await query.answer(f"Need {card['price']:,}")
            return
        
        user["balance"] -= card["price"]
        user["video_card"] = level
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_database()
        
        await query.answer(f"Bought {card['name']}!")
        keyboard = [[InlineKeyboardButton("↩️ Shop", callback_data="shop")]]
        await query.edit_message_text(
            f"✅ *Purchased!*\n\n🖥 *{card['name']}*\n💰 Income: `{card['income']:,}`/h\n💵 Cost: `{card['price']:,}`\n💳 Balance: `{user['balance']:,}`\n\n⛏ Mining started!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "buy_business":
        if user.get("business"):
            await query.answer("Already owned!")
            return
        if user["balance"] < 100000:
            await query.answer("Need 100,000")
            return
        
        user["balance"] -= 100000
        user["business"] = True
        save_database()
        
        await query.answer("Business bought!")
        keyboard = [[InlineKeyboardButton("↩️ Shop", callback_data="shop")]]
        await query.edit_message_text("✅ *Business bought!*\n💰 +5,000 to bonus", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "buy_vip":
        if user.get("vip"):
            await query.answer("VIP active!")
            return
        if user["balance"] < 200000:
            await query.answer("Need 200,000")
            return
        
        user["balance"] -= 200000
        user["vip"] = True
        save_database()
        
        await query.answer("VIP activated!")
        keyboard = [[InlineKeyboardButton("↩️ Shop", callback_data="shop")]]
        await query.edit_message_text("✅ *VIP activated!*\n💰 x2 wins & bonus", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data in ["game_coin", "game_dice", "game_slots"]:
        games = {"game_coin": "🪙 Coin", "game_dice": "🎲 Dice", "game_slots": "🎰 Slots"}
        user["current_game"] = query.data
        save_database()
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"*{games[query.data]}*\n\n💰 Balance: `{user['balance']:,}`\n\nEnter bet:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "cancel":
        user["current_game"] = None
        save_database()
        keyboard = [
            [InlineKeyboardButton("🎰 Casino", callback_data="casino")],
            [InlineKeyboardButton("↩️ Menu", callback_data="menu")]
        ]
        await query.edit_message_text("❌ Cancelled", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "daily":
        today = datetime.date.today().isoformat()
        if user.get("last_daily") != today:
            bonus = DAILY_START
            parts = [f"🎁 Base: +{DAILY_START:,}"]
            if user.get("business"):
                bonus += 5000
                parts.append("🏪 Business: +5,000")
            if user.get("vip"):
                bonus *= 2
                parts.append("💎 VIP x2")
            
            user["balance"] += bonus
            user["last_daily"] = today
            user["earned"] += bonus
            save_database()
            
            text = f"✅ *Bonus!*\n\n" + "\n".join(parts) + f"\n\n💰 Total: `+{bonus:,}`\n💳 Balance: `{user['balance']:,}`"
            keyboard = [[InlineKeyboardButton("↩️ Menu", callback_data="menu")]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("↩️ Menu", callback_data="menu")]]
            await query.edit_message_text("❌ Already claimed!\n⏰ Tomorrow again", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "top":
        sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        text = "🏆 *Top-10*\n\n"
        for i, (u_id, u_data) in enumerate(sorted_users, 1):
            name = u_data["name"][:15]
            vip = "👑" if u_data.get("vip") else ""
            card = "⛏" if u_data.get("video_card", 0) > 0 else ""
            text += f"{['🥇','🥈','🥉'][i-1] if i<4 else '👤'} {i}. {vip}{card}{name}: `{u_data['balance']:,}`\n"
        
        keyboard = [[InlineKeyboardButton("↩️ Back", callback_data="menu")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "menu":
        keyboard = [
            [InlineKeyboardButton("👤 Profile", callback_data="profile")],
            [InlineKeyboardButton("🎰 Casino", callback_data="casino")],
            [InlineKeyboardButton("⛏ Mining", callback_data="mining")],
            [InlineKeyboardButton("🎁 Cases", callback_data="cases")],
            [InlineKeyboardButton("🛍 Shop", callback_data="shop")],
            [InlineKeyboardButton("🎁 Bonus", callback_data="daily")],
            [InlineKeyboardButton("🏆 Top", callback_data="top")],
        ]
        await query.edit_message_text(
            "🎰 *Menu*\nChoose action:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    name = update.message.from_user.username or update.message.from_user.first_name
    user = get_user(uid, name)
    
    if not user.get("current_game"):
        return
    
    try:
        bet = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Enter number!")
        return
    
    if bet < 1:
        await update.message.reply_text("❌ Min 1!")
        return
    
    if bet > user["balance"]:
        await update.message.reply_text(f"❌ Low balance!\n💰 Balance: `{user['balance']:,}`", parse_mode='Markdown')
        return
    
    vip = 2 if user.get("vip") else 1
    game = user["current_game"]
    win = 0
    
    if game == "game_coin":
        coin = random.choice(["Heads", "Tails"])
        if random.random() < 0.5:
            win = bet * 2 * vip
            msg = f"🪙 {coin}\n✅ Win! +{win-bet:,}"
        else:
            msg = f"🪙 {coin}\n❌ Loss -{bet:,}"
    
    elif game == "game_dice":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2 * vip
            msg = f"🎲 {d1}+{d2}={total} (Even)\n✅ Win! +{win-bet:,}"
        else:
            msg = f"🎲 {d1}+{d2}={total} (Odd)\n❌ Loss -{bet:,}"
    
    elif game == "game_slots":
        s = random.choices(["🍒","🍋","🍊","7️⃣","💎","⭐"], k=3)
        if s[0] == s[1] == s[2]:
            win = bet * 5 * vip
            msg = f"🎰 {' '.join(s)}\n🎉 JACKPOT! +{win-bet:,}"
        elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
            win = bet * 2 * vip
            msg = f"🎰 {' '.join(s)}\n✅ Win! +{win-bet:,}"
        else:
            msg = f"🎰 {' '.join(s)}\n❌ Loss -{bet:,}"
    
    user["balance"] += win - bet
    user["games"] += 1
    if win > 0:
        user["earned"] += win - bet
    else:
        user["lost"] += bet
    user["current_game"] = None
    save_database()
    
    keyboard = [
        [InlineKeyboardButton("🎰 Play", callback_data="casino")],
        [InlineKeyboardButton("↩️ Menu", callback_data="menu")]
    ]
    
    await update.message.reply_text(
        f"{msg}\n💰 Balance: `{user['balance']:,}`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    text = "🏆 *Top-10*\n\n"
    for i, (_, u) in enumerate(sorted_users
