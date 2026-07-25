import json, os, datetime, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise ValueError("API_TOKEN не найден!")

ADMIN_IDS = ["1439955343"]
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
    "common": {"name": "Обычный", "price": 5000, "rewards": [1000, 2000, 3000, 5000, 10000]},
    "rare": {"name": "Редкий", "price": 15000, "rewards": [5000, 10000, 20000, 35000, 50000]},
    "epic": {"name": "Эпический", "price": 50000, "rewards": [15000, 30000, 50000, 100000, 200000]},
    "legendary": {"name": "Легендарный", "price": 150000, "rewards": [50000, 100000, 200000, 500000, 1000000]},
}

def load_db():
    global DB
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    DB = json.loads(content)
    except:
        DB = {}

def save_db():
    global DB
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(DB, f, ensure_ascii=False, indent=2)
    except:
        pass

def is_admin(uid):
    return str(uid) in ADMIN_IDS

def get_user(uid, name=None):
    global DB
    uid = str(uid)
    if uid not in DB:
        DB[uid] = {
            "name": name or "Игрок",
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
    uid = str(u.id)
    get_user(uid, u.first_name)
    kb = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
        [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")],
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("⚙️ Админ", callback_data="admin")])
    await update.message.reply_text(
        f"🎰 Lucky Casino\n\nПривет, {u.first_name}!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def buttons(update, context):
    q = update.callback_query
    try:
        await q.answer()
    except:
        pass
    uid = str(q.from_user.id)
    user = get_user(uid, q.from_user.first_name)
    admin = is_admin(uid)
    d = q.data

    if d == "profile":
        collect_mining(user)
        user = get_user(uid)
        card = VIDEO_CARDS.get(user["video_card"])
        txt = f"👤 Профиль\n\n💰 Баланс: {user['balance']:,} 🪙\n📅 Регистрация: {user['reg_date']}\n🎮 Игр: {user['games']}\n🎁 Кейсов: {user['cases_opened']}\n\n⛏ Майнинг:\n"
        txt += f"Видеокарта: {card['emoji']} {card['name']}\n" if card else "Видеокарта: ❌ Нет\n"
        txt += f"Намайнено: {user['mined_total']:,} 🪙\nБизнес: {'✅' if user['business'] else '❌'}\nVIP: {'✅' if user['vip'] else '❌'}\n\nЗаработано: {user['earned']:,} 🪙\nПроиграно: {user['lost']:,} 🪙"
        kb = [[InlineKeyboardButton("⛏ Собрать", callback_data="collect")], [InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "collect":
        inc = collect_mining(user)
        await q.answer(f"Собрано: {inc:,} 🪙" if inc > 0 else "Нечего собирать")
    elif d == "casino":
        kb = [[InlineKeyboardButton("🪙 Монетка (x2)", callback_data="game_coin")], [InlineKeyboardButton("🎲 Кости (x2)", callback_data="game_dice")], [InlineKeyboardButton("🎰 Слоты (x5)", callback_data="game_slots")], [InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await q.edit_message_text(f"🎰 Казино\n💰 Баланс: {user['balance']:,} 🪙\n\nВыберите игру:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "mining":
        card = VIDEO_CARDS.get(user["video_card"])
        pending = mining_income(user)
        if card:
            txt = f"⛏ Майнинг\n\nВидеокарта: {card['emoji']} {card['name']}\nДоход: {card['income']:,} 🪙/час\nНамайнено: {user['mined_total']:,} 🪙\nОжидает: {pending:,} 🪙"
        else:
            txt = "⛏ Майнинг\n\n❌ Нет видеокарты!\n\nКарты:\n"
            for lv, c in VIDEO_CARDS.items():
                txt += f"{c['emoji']} {c['name']}: {c['income']:,} 🪙/час\n"
        kb = [[InlineKeyboardButton("💰 Собрать", callback_data="collect")]] if pending > 0 else []
        kb.append([InlineKeyboardButton("🛍 Магазин", callback_data="shop_videocards")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="menu")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "cases":
        kb = [[InlineKeyboardButton(f"📦 Обычный - {CASES['common']['price']:,}🪙", callback_data="open_common")], [InlineKeyboardButton(f"🎁 Редкий - {CASES['rare']['price']:,}🪙", callback_data="open_rare")], [InlineKeyboardButton(f"💎 Эпический - {CASES['epic']['price']:,}🪙", callback_data="open_epic")], [InlineKeyboardButton(f"👑 Легендарный - {CASES['legendary']['price']:,}🪙", callback_data="open_legendary")], [InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await q.edit_message_text("🎁 Кейсы\n\nВыберите:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("open_"):
        ct = d.replace("open_", "")
        case = CASES.get(ct)
        if not case:
            return
        if user["balance"] < case["price"]:
            await q.answer(f"Нужно {case['price']:,} 🪙")
            return
        user["balance"] -= case["price"]
        reward = random.choice(case["rewards"])
        if random.random() < 0.05:
            reward = case["rewards"][-1]
        user["balance"] += reward
        user["cases_opened"] += 1
        user["earned"] += reward
        save_db()
        txt = f"🎁 {case['name']}\n\n💵 Цена: {case['price']:,} 🪙\n🎉 Выигрыш: {reward:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙"
        if reward == case["rewards"][-1]:
            txt += "\n🔥 ДЖЕКПОТ!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Ещё", callback_data="cases")], [InlineKeyboardButton("↩️ Меню", callback_data="menu")]]))
    elif d == "shop":
        kb = [[InlineKeyboardButton("🖥 Видеокарты", callback_data="shop_videocards")], [InlineKeyboardButton("🏪 Бизнес", callback_data="shop_business")], [InlineKeyboardButton("💎 VIP", callback_data="shop_vip")], [InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await q.edit_message_text("🛍 Магазин\n\nКатегория:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "shop_videocards":
        txt = "🖥 Видеокарты\n\n"
        for lv, c in VIDEO_CARDS.items():
            owned = user["video_card"] >= lv
            txt += f"{c['emoji']} {c['name']}\n💰 {c['income']:,}/час\n💵 {c['price']:,} 🪙 {'✅' if owned else '❌'}\n\n"
        kb = []
        for lv, c in VIDEO_CARDS.items():
            if user["video_card"] < lv:
                kb.append([InlineKeyboardButton(f"{c['emoji']} {c['name']} - {c['price']:,}🪙", callback_data=f"buyc_{lv}")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="shop")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "shop_business":
        txt = f"🏪 Бизнес\n\n💵 100,000 🪙\n💰 +5,000 к бонусу\n{'✅ Куплен' if user['business'] else '❌'}"
        kb = []
        if not user["business"]:
            kb.append([InlineKeyboardButton("Купить - 100,000🪙", callback_data="buyb")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="shop")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "shop_vip":
        txt = f"💎 VIP\n\n💵 200,000 🪙\n💰 x2 выигрыши\n{'✅ Активен' if user['vip'] else '❌'}"
        kb = []
        if not user["vip"]:
            kb.append([InlineKeyboardButton("Купить - 200,000🪙", callback_data="buyv")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="shop")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("buyc_"):
        lv = int(d.replace("buyc_", ""))
        c = VIDEO_CARDS[lv]
        if user["video_card"] >= lv:
            return
        if user["balance"] < c["price"]:
            await q.answer(f"Нужно {c['price']:,} 🪙")
            return
        user["balance"] -= c["price"]
        user["video_card"] = lv
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
        await q.answer(f"Куплена {c['name']}!")
    elif d == "buyb":
        if user["business"]:
            return
        if user["balance"] < 100000:
            await q.answer("Нужно 100,000 🪙")
            return
        user["balance"] -= 100000
        user["business"] = True
        save_db()
        await q.answer("Бизнес куплен!")
    elif d == "buyv":
        if user["vip"]:
            return
        if user["balance"] < 200000:
            await q.answer("Нужно 200,000 🪙")
            return
        user["balance"] -= 200000
        user["vip"] = True
        save_db()
        await q.answer("VIP активен!")
    elif d in ["game_coin", "game_dice", "game_slots"]:
        games = {"game_coin": "Монетка", "game_dice": "Кости", "game_slots": "Слоты"}
        user["current_game"] = d
        save_db()
        await q.edit_message_text(f"🎮 {games[d]}\n💰 Баланс: {user['balance']:,} 🪙\n\nВведите ставку:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]))
    elif d == "cancel":
        user["current_game"] = None
        save_db()
        await q.edit_message_text("❌ Отменено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Казино", callback_data="casino")], [InlineKeyboardButton("↩️ Меню", callback_data="menu")]]))
    elif d == "daily":
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
            await q.edit_message_text(f"✅ Бонус: +{bonus:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]))
        else:
            await q.edit_message_text("❌ Уже получен!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]))
    elif d == "top":
        su = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        txt = "🏆 Топ-10\n\n"
        for i, item in enumerate(su, 1):
            u = item[1]
            txt += f"{i}. {u['name'][:15]}: {u['balance']:,} 🪙\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="menu")]]))
    elif d == "admin":
        if not admin:
            return
        txt = f"⚙️ Админ\n\n👥 {len(DB)} чел.\n💰 {sum(u['balance'] for u in DB.values()):,} 🪙"
        kb = [[InlineKeyboardButton("👥 Список", callback_data="admin_users")], [InlineKeyboardButton("💰 Выдать", callback_data="admin_give")], [InlineKeyboardButton("🔄 Сброс", callback_data="admin_reset")], [InlineKeyboardButton("📢 Рассылка", callback_data="admin_send")], [InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "admin_users":
        if not admin:
            return
        txt = "👥 Игроки:\n\n"
        for i, (uid, u) in enumerate(list(DB.items())[:20], 1):
            txt += f"{i}. {u['name'][:15]}: {u['balance']:,} 🪙\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="admin")]]))
    elif d == "admin_give":
        if not admin:
            return
        kb = []
        for uid, u in list(DB.items())[:15]:
            kb.append([InlineKeyboardButton(f"{u['name'][:20]} - {u['balance']:,}🪙", callback_data=f"give_{uid}")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="admin")])
        await q.edit_message_text("💰 Выдать\n\nКому:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("give_"):
        if not admin:
            return
        target = d.replace("give_", "")
        context.user_data["target"] = target
        context.user_data["action"] = "give"
        await q.edit_message_text(f"💰 Сумма для {DB[target]['name']}:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="admin")]]))
    elif d == "admin_reset":
        if not admin:
            return
        for u in DB.values():
            u["last_daily"] = None
        save_db()
        await q.answer("Сброшено!")
    elif d == "admin_send":
        if not admin:
            return
        context.user_data["action"] = "send"
        await q.edit_message_text("📢 Сообщение для всех:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="admin")]]))
    elif d == "menu":
        kb = [[InlineKeyboardButton("👤 Профиль", callback_data="profile")], [InlineKeyboardButton("🎰 Казино", callback_data="casino")], [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")], [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")], [InlineKeyboardButton("🛍 Магазин", callback_data="shop")], [InlineKeyboardButton("🎁 Бонус", callback_data="daily")], [InlineKeyboardButton("🏆 Топ", callback_data="top")]]
        if admin:
            kb.append([InlineKeyboardButton("⚙️ Админ", callback_data="admin")])
        await q.edit_message_text("🎰 Меню", reply_markup=InlineKeyboardMarkup(kb))

async def messages(update, context):
    uid = str(update.message.from_user.id)
    user = get_user(uid, update.message.from_user.first_name)
    admin = is_admin(uid)
    
    if admin and context.user_data.get("action"):
        act = context.user_data["action"]
        if act == "give":
            target = context.user_data.get("target")
            if target and target in DB:
                try:
                    amount = int(update.message.text.strip())
                    if amount > 0:
                        DB[target]["balance"] += amount
                        save_db()
                        await update.message.reply_text(f"✅ +{amount:,} 🪙 для {DB[target]['name']}")
                except:
                    await update.message.reply_text("❌ Число!")
            context.user_data["action"] = None
            return
        elif act == "send":
            txt = update.message.text
            ok = 0
            for u in DB:
                try:
                    await context.bot.send_message(chat_id=int(u), text=f"📢 {txt}")
                    ok += 1
                except:
                    pass
            await update.message.reply_text(f"✅ Отправлено: {ok}")
            context.user_data["action"] = None
            return
    
    if not user.get("current_game"):
        return
    
    try:
        bet = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Число!")
        return
    
    if bet < 1 or bet > user["balance"]:
        await update.message.reply_text(f"❌ Неверно!\n💰 {user['balance']:,} 🪙")
        return
    
    vip = 2 if user["vip"] else 1
    game = user["current_game"]
    win = 0
    
    if game == "game_coin":
        coin = random.choice(["Орёл", "Решка"])
        if random.random() < 0.5:
            win = bet * 2 * vip
            msg = f"🪙 {coin}\n✅ +{win-bet:,} 🪙"
        else:
            msg = f"🪙 {coin}\n❌ -{bet:,} 🪙"
    elif game == "game_dice":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        t = d1 + d2
        if t % 2 == 0:
            win = bet * 2 * vip
            msg = f"🎲 {d1}+{d2}={t}\n✅ +{win-bet:,} 🪙"
        else:
            msg = f"🎲 {d1}+{d2}={t}\n❌ -{bet:,} 🪙"
    elif game == "game_slots":
        s = random.choices(["🍒","🍋","🍊","7️⃣","💎","⭐"], k=3)
        if s[0] == s[1] == s[2]:
            win = bet * 5 * vip
            msg = f"🎰 {' '.join(s)}\n🎉 +{win-bet:,} 🪙"
        elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
            win = bet * 2 * vip
            msg = f"🎰 {' '.join(s)}\n✅ +{win-bet:,} 🪙"
        else:
            msg = f"🎰 {' '.join(s)}\n❌ -{bet:,} 🪙"
    
    user["balance"] += win - bet
    user["games"] += 1
    if win > 0:
        user["earned"] += win - bet
    else:
        user["lost"] += bet
    user["current_game"] = None
    save_db()
    
    await update.message.reply_text(f"{msg}\n💰 {user['balance']:,} 🪙", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Играть", callback_data="casino")], [InlineKeyboardButton("↩️ Меню", callback_data="menu")]]))

def main():
    load_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))
    save_db()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
