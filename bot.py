import json, os, datetime, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError("API_TOKEN not found!")

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
    "common": {"name": "Common", "price": 5000, "rewards": [1000, 2000, 3000, 5000, 10000]},
    "rare": {"name": "Rare", "price": 15000, "rewards": [5000, 10000, 20000, 35000, 50000]},
    "epic": {"name": "Epic", "price": 50000, "rewards": [15000, 30000, 50000, 100000, 200000]},
    "legendary": {"name": "Legendary", "price": 150000, "rewards": [50000, 100000, 200000, 500000, 1000000]},
}

def load_db():
    global DB
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                content = f.read()
                if content.strip():
                    DB = json.loads(content)
    except:
        DB = {}

def save_db():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(DB, f)
    except:
        pass

def get_user(uid, name=None):
    uid = str(uid)
    if uid not in DB:
        DB[uid] = {
            "name": name or "Player",
            "balance": 10000,
            "last_daily": None,
            "current_game": None,
            "business": False,
            "vip": False,
            "video_card": 0,
            "mining_start": None,
            "mined_total": 0,
            "reg_date": str(datetime.date.today()),
            "earned": 0,
            "lost": 0,
            "games": 0,
            "cases_opened": 0,
        }
        save_db()
    return DB[uid]

def mining_income(user):
    if user["video_card"] == 0 or not user.get("mining_start"):
        return 0
    card = VIDEO_CARDS.get(user["video_card"])
    if not card:
        return 0
    try:
        start = datetime.datetime.fromisoformat(user["mining_start"])
        hours = (datetime.datetime.now() - start).total_seconds() / 3600
        return max(0, int(hours * card["income"]))
    except:
        return 0

def collect_mining(user):
    inc = mining_income(user)
    if inc > 0:
        user["balance"] += inc
        user["mined_total"] = user.get("mined_total", 0) + inc
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
    return inc

async def start(update, context):
    u = update.effective_user
    get_user(u.id, u.first_name)
    kb = [
        [InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("🎰 Casino", callback_data="casino")],
        [InlineKeyboardButton("⛏ Mining", callback_data="mining")],
        [InlineKeyboardButton("🎁 Cases", callback_data="cases")],
        [InlineKeyboardButton("🛍 Shop", callback_data="shop")],
        [InlineKeyboardButton("🎁 Bonus", callback_data="daily")],
        [InlineKeyboardButton("🏆 Top", callback_data="top")],
    ]
    await update.message.reply_text(
        f"🎰 Casino Bot\nHi {u.first_name}!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = str(q.from_user.id)
    user = get_user(uid, q.from_user.first_name)
    
    if q.data == "profile":
        collect_mining(user)
        user = get_user(uid)
        card = VIDEO_CARDS.get(user["video_card"])
        txt = f"👤 Profile\n\n"
        txt += f"💰 Balance: {user['balance']:,}\n"
        txt += f"📅 Since: {user['reg_date']}\n"
        txt += f"🎮 Games: {user['games']}\n"
        txt += f"🎁 Cases: {user['cases_opened']}\n\n"
        txt += f"⛏ Mining:\n"
        if card:
            txt += f"Card: {card['emoji']} {card['name']}\n"
        else:
            txt += f"Card: None\n"
        txt += f"Mined: {user['mined_total']:,}\n"
        txt += f"Business: {'Yes' if user['business'] else 'No'}\n"
        txt += f"VIP: {'Yes' if user['vip'] else 'No'}\n"
        txt += f"\nEarned: {user['earned']:,}\nLost: {user['lost']:,}"
        kb = [
            [InlineKeyboardButton("⛏ Collect Mining", callback_data="collect")],
            [InlineKeyboardButton("↩️ Back", callback_data="menu")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "collect":
        inc = collect_mining(user)
        if inc > 0:
            await q.answer(f"Collected: {inc:,}")
        else:
            await q.answer("Nothing to collect")
        await buttons(update, context)
    
    elif q.data == "casino":
        kb = [
            [InlineKeyboardButton("🪙 Coin (x2)", callback_data="game_coin")],
            [InlineKeyboardButton("🎲 Dice (x2)", callback_data="game_dice")],
            [InlineKeyboardButton("🎰 Slots (x5)", callback_data="game_slots")],
            [InlineKeyboardButton("↩️ Back", callback_data="menu")],
        ]
        await q.edit_message_text(
            f"🎰 Casino\nBalance: {user['balance']:,}\nChoose game:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "mining":
        card = VIDEO_CARDS.get(user["video_card"])
        pending = mining_income(user)
        if card:
            txt = f"⛏ Mining Farm\n\n"
            txt += f"Card: {card['emoji']} {card['name']}\n"
            txt += f"Income: {card['income']:,}/hour\n"
            txt += f"Mined: {user['mined_total']:,}\n"
            txt += f"Pending: {pending:,}"
        else:
            txt = "⛏ Mining Farm\n\nNo card!\nBuy in shop.\n\nCards:\n"
            for lv, c in VIDEO_CARDS.items():
                txt += f"{c['emoji']} {c['name']}: {c['income']:,}/h\n"
        kb = []
        if pending > 0:
            kb.append([InlineKeyboardButton("💰 Collect", callback_data="collect")])
        kb.append([InlineKeyboardButton("🛍 Shop", callback_data="shop")])
        kb.append([InlineKeyboardButton("↩️ Back", callback_data="menu")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "cases":
        kb = [
            [InlineKeyboardButton(f"📦 Common - {CASES['common']['price']:,}", callback_data="open_common")],
            [InlineKeyboardButton(f"🎁 Rare - {CASES['rare']['price']:,}", callback_data="open_rare")],
            [InlineKeyboardButton(f"💎 Epic - {CASES['epic']['price']:,}", callback_data="open_epic")],
            [InlineKeyboardButton(f"👑 Legendary - {CASES['legendary']['price']:,}", callback_data="open_legendary")],
            [InlineKeyboardButton("↩️ Back", callback_data="menu")],
        ]
        await q.edit_message_text(
            "🎁 Cases\n\nChoose case to open:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data.startswith("open_"):
        ct = q.data.replace("open_", "")
        case = CASES.get(ct)
        if not case:
            return
        if user["balance"] < case["price"]:
            await q.answer(f"Need {case['price']:,}")
            return
        user["balance"] -= case["price"]
        reward = random.choice(case["rewards"])
        if random.random() < 0.05:
            reward = case["rewards"][-1]
        user["balance"] += reward
        user["cases_opened"] += 1
        user["earned"] += reward
        save_db()
        txt = f"🎁 Case: {case['name']}\n"
        txt += f"Cost: {case['price']:,}\n"
        txt += f"Win: {reward:,}\n"
        txt += f"Balance: {user['balance']:,}"
        if reward == case["rewards"][-1]:
            txt += "\n\n🔥 JACKPOT!"
        kb = [
            [InlineKeyboardButton("🎁 Open More", callback_data="cases")],
            [InlineKeyboardButton("↩️ Menu", callback_data="menu")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "shop":
        txt = "🛍 Shop\n\nVideo Cards:\n\n"
        for lv, c in VIDEO_CARDS.items():
            owned = user["video_card"] >= lv
            txt += f"{c['emoji']} {c['name']}\n"
            txt += f"Income: {c['income']:,}/h\n"
            txt += f"Price: {c['price']:,} {'✅' if owned else ''}\n\n"
        txt += f"🏪 Business: 100,000 {'✅' if user['business'] else ''}\n"
        txt += f"💎 VIP: 200,000 {'✅' if user['vip'] else ''}"
        kb = []
        for lv, c in VIDEO_CARDS.items():
            if user["video_card"] < lv:
                kb.append([InlineKeyboardButton(
                    f"{c['emoji']} {c['name']} - {c['price']:,}",
                    callback_data=f"buyc_{lv}"
                )])
        if not user["business"]:
            kb.append([InlineKeyboardButton("🏪 Business - 100,000", callback_data="buyb")])
        if not user["vip"]:
            kb.append([InlineKeyboardButton("💎 VIP - 200,000", callback_data="buyv")])
        kb.append([InlineKeyboardButton("↩️ Back", callback_data="menu")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data.startswith("buyc_"):
        lv = int(q.data.replace("buyc_", ""))
        c = VIDEO_CARDS[lv]
        if user["video_card"] >= lv:
            await q.answer("Better card owned!")
            return
        if user["balance"] < c["price"]:
            await q.answer(f"Need {c['price']:,}")
            return
        user["balance"] -= c["price"]
        user["video_card"] = lv
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
        await q.answer(f"Bought {c['name']}!")
        kb = [[InlineKeyboardButton("↩️ Shop", callback_data="shop")]]
        await q.edit_message_text(
            f"✅ Bought {c['name']}!\nIncome: {c['income']:,}/h\nBalance: {user['balance']:,}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "buyb":
        if user["business"]:
            return
        if user["balance"] < 100000:
            await q.answer("Need 100,000")
            return
        user["balance"] -= 100000
        user["business"] = True
        save_db()
        await q.answer("Business bought!")
        kb = [[InlineKeyboardButton("↩️ Shop", callback_data="shop")]]
        await q.edit_message_text(
            "✅ Business bought!\n+5,000 to daily bonus",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "buyv":
        if user["vip"]:
            return
        if user["balance"] < 200000:
            await q.answer("Need 200,000")
            return
        user["balance"] -= 200000
        user["vip"] = True
        save_db()
        await q.answer("VIP activated!")
        kb = [[InlineKeyboardButton("↩️ Shop", callback_data="shop")]]
        await q.edit_message_text(
            "✅ VIP activated!\nx2 wins & bonuses",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data in ["game_coin", "game_dice", "game_slots"]:
        user["current_game"] = q.data
        save_db()
        kb = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await q.edit_message_text(
            f"Enter bet:\nBalance: {user['balance']:,}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "cancel":
        user["current_game"] = None
        save_db()
        kb = [
            [InlineKeyboardButton("🎰 Casino", callback_data="casino")],
            [InlineKeyboardButton("↩️ Menu", callback_data="menu")]
        ]
        await q.edit_message_text("Cancelled", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "daily":
        today = str(datetime.date.today())
        if user.get("last_daily") != today:
            bonus = DAILY_START
            if user["business"]:
                bonus += 5000
            if user["vip"]:
                bonus *= 2
            user["balance"] += bonus
            user["last_daily"] = today
            user["earned"] += bonus
            save_db()
            kb = [[InlineKeyboardButton("↩️ Menu", callback_data="menu")]]
            await q.edit_message_text(
                f"✅ Bonus: +{bonus:,}\nBalance: {user['balance']:,}",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            kb = [[InlineKeyboardButton("↩️ Menu", callback_data="menu")]]
            await q.edit_message_text("Already claimed!", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "top":
        su = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        txt = "🏆 Top-10:\n\n"
        for i, item in enumerate(su, 1):
            u_data = item[1]
            txt += f"{i}. {u_data['name'][:15]}: {u_data['balance']:,}\n"
        kb = [[InlineKeyboardButton("↩️ Back", callback_data="menu")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "menu":
        kb = [
            [InlineKeyboardButton("👤 Profile", callback_data="profile")],
            [InlineKeyboardButton("🎰 Casino", callback_data="casino")],
            [InlineKeyboardButton("⛏ Mining", callback_data="mining")],
            [InlineKeyboardButton("🎁 Cases", callback_data="cases")],
            [InlineKeyboardButton("🛍 Shop", callback_data="shop")],
            [InlineKeyboardButton("🎁 Bonus", callback_data="daily")],
            [InlineKeyboardButton("🏆 Top", callback_data="top")],
        ]
        await q.edit_message_text(
            "🎰 Menu\nChoose action:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def messages(update, context):
    uid = str(update.message.from_user.id)
    user = get_user(uid, update.message.from_user.first_name)
    if not user.get("current_game"):
        return
    try:
        bet = int(update.message.text.strip())
    except:
        await update.message.reply_text("Enter number!")
        return
    if bet < 1 or bet > user["balance"]:
        await update.message.reply_text(f"Invalid bet! Balance: {user['balance']:,}")
        return
    
    vip = 2 if user["vip"] else 1
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
    save_db()
    
    kb = [
        [InlineKeyboardButton("🎰 Play Again", callback_data="casino")],
        [InlineKeyboardButton("↩️ Menu", callback_data="menu")]
    ]
    await update.message.reply_text(
        f"{msg}\n💰 Balance: {user['balance']:,}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

def main():
    load_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))
    print("Bot started!")
    save_db()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
