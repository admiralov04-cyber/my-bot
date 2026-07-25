import json, os, datetime, random
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
    get_user(u.id, u.first_name)
    kb = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
        [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")],
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ]
    await update.message.reply_text(
        f"🎰 Lucky Casino\n\nПривет, {u.first_name}!\nВыберите действие:",
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
        txt = "👤 Профиль\n\n"
        txt += f"💰 Баланс: {user['balance']:,} 🪙\n"
        txt += f"📅 Регистрация: {user['reg_date']}\n"
        txt += f"🎮 Игр: {user['games']}\n"
        txt += f"🎁 Кейсов: {user['cases_opened']}\n\n"
        txt += "⛏ Майнинг:\n"
        if card:
            txt += f"Видеокарта: {card['emoji']} {card['name']}\n"
        else:
            txt += "Видеокарта: ❌ Нет\n"
        txt += f"Намайнено: {user['mined_total']:,} 🪙\n"
        txt += f"Бизнес: {'✅' if user['business'] else '❌'}\n"
        txt += f"VIP: {'✅' if user['vip'] else '❌'}\n\n"
        txt += f"Заработано: {user['earned']:,} 🪙\n"
        txt += f"Проиграно: {user['lost']:,} 🪙"
        kb = [
            [InlineKeyboardButton("⛏ Собрать майнинг", callback_data="collect")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "collect":
        inc = collect_mining(user)
        if inc > 0:
            await q.answer(f"Собрано: {inc:,} 🪙")
        else:
            await q.answer("Нечего собирать")
        await buttons(update, context)
    
    elif q.data == "casino":
        kb = [
            [InlineKeyboardButton("🪙 Монетка (x2)", callback_data="game_coin")],
            [InlineKeyboardButton("🎲 Кости (x2)", callback_data="game_dice")],
            [InlineKeyboardButton("🎰 Слоты (x5)", callback_data="game_slots")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")],
        ]
        await q.edit_message_text(
            f"🎰 Казино\n💰 Баланс: {user['balance']:,} 🪙\n\nВыберите игру:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "mining":
        card = VIDEO_CARDS.get(user["video_card"])
        pending = mining_income(user)
        if card:
            txt = "⛏ Майнинг ферма\n\n"
            txt += f"Видеокарта: {card['emoji']} {card['name']}\n"
            txt += f"Доход: {card['income']:,} 🪙/час\n"
            txt += f"Намайнено: {user['mined_total']:,} 🪙\n"
            txt += f"Ожидает: {pending:,} 🪙"
        else:
            txt = "⛏ Майнинг ферма\n\n"
            txt += "❌ Нет видеокарты!\nКупите в магазине.\n\nДоступные карты:\n"
            for lv, c in VIDEO_CARDS.items():
                txt += f"{c['emoji']} {c['name']}: {c['income']:,} 🪙/час\n"
        kb = []
        if pending > 0:
            kb.append([InlineKeyboardButton("💰 Собрать", callback_data="collect")])
        kb.append([InlineKeyboardButton("🛍 В магазин", callback_data="shop_videocards")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="menu")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "cases":
        kb = [
            [InlineKeyboardButton(f"📦 Обычный - {CASES['common']['price']:,}🪙", callback_data="open_common")],
            [InlineKeyboardButton(f"🎁 Редкий - {CASES['rare']['price']:,}🪙", callback_data="open_rare")],
            [InlineKeyboardButton(f"💎 Эпический - {CASES['epic']['price']:,}🪙", callback_data="open_epic")],
            [InlineKeyboardButton(f"👑 Легендарный - {CASES['legendary']['price']:,}🪙", callback_data="open_legendary")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")],
        ]
        await q.edit_message_text("🎁 Кейсы\n\nВыберите кейс:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data.startswith("open_"):
        ct = q.data.replace("open_", "")
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
        txt = f"🎁 Кейс: {case['name']}\n\n"
        txt += f"💵 Стоимость: {case['price']:,} 🪙\n"
        txt += f"🎉 Выигрыш: {reward:,} 🪙\n"
        txt += f"💰 Баланс: {user['balance']:,} 🪙"
        if reward == case["rewards"][-1]:
            txt += "\n\n🔥 ДЖЕКПОТ!"
        kb = [
            [InlineKeyboardButton("🎁 Открыть ещё", callback_data="cases")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "shop":
        kb = [
            [InlineKeyboardButton("🖥 Видеокарты", callback_data="shop_videocards")],
            [InlineKeyboardButton("🏪 Бизнес", callback_data="shop_business")],
            [InlineKeyboardButton("💎 VIP", callback_data="shop_vip")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")],
        ]
        await q.edit_message_text("🛍 Магазин\n\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "shop_videocards":
        txt = "🖥 Видеокарты\n\n"
        for lv, c in VIDEO_CARDS.items():
            owned = user["video_card"] >= lv
            txt += f"{c['emoji']} {c['name']}\n"
            txt += f"💰 Доход: {c['income']:,} 🪙/час\n"
            txt += f"💵 Цена: {c['price']:,} 🪙\n"
            txt += f"Статус: {'✅ Куплена' if owned else '❌'}\n\n"
        kb = []
        for lv, c in VIDEO_CARDS.items():
            if user["video_card"] < lv:
                kb.append([InlineKeyboardButton(f"{c['emoji']} {c['name']} - {c['price']:,}🪙", callback_data=f"buyc_{lv}")])
        kb.append([InlineKeyboardButton("↩️ В магазин", callback_data="shop")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "shop_business":
        txt = "🏪 Бизнес\n\n"
        txt += "💵 Цена: 100,000 🪙\n"
        txt += "💰 Доход: +5,000 к бонусу\n"
        txt += f"Статус: {'✅ Куплен' if user['business'] else '❌'}"
        kb = []
        if not user["business"]:
            kb.append([InlineKeyboardButton("🏪 Купить - 100,000🪙", callback_data="buyb")])
        kb.append([InlineKeyboardButton("↩️ В магазин", callback_data="shop")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "shop_vip":
        txt = "💎 VIP-статус\n\n"
        txt += "💵 Цена: 200,000 🪙\n"
        txt += "💰 Бонусы:\n"
        txt += "• x2 к выигрышам\n"
        txt += "• x2 к бонусу\n"
        txt += f"Статус: {'✅ Активен' if user['vip'] else '❌'}"
        kb = []
        if not user["vip"]:
            kb.append([InlineKeyboardButton("💎 Купить - 200,000🪙", callback_data="buyv")])
        kb.append([InlineKeyboardButton("↩️ В магазин", callback_data="shop")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data.startswith("buyc_"):
        lv = int(q.data.replace("buyc_", ""))
        c = VIDEO_CARDS[lv]
        if user["video_card"] >= lv:
            await q.answer("Уже есть карта лучше!")
            return
        if user["balance"] < c["price"]:
            await q.answer(f"Нужно {c['price']:,} 🪙")
            return
        user["balance"] -= c["price"]
        user["video_card"] = lv
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
        await q.answer(f"Куплена {c['name']}!")
        kb = [[InlineKeyboardButton("↩️ К видеокартам", callback_data="shop_videocards")]]
        await q.edit_message_text(
            f"✅ Куплена {c['name']}!\n💰 Доход: {c['income']:,} 🪙/час\n💳 Баланс: {user['balance']:,} 🪙",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "buyb":
        if user["business"]:
            return
        if user["balance"] < 100000:
            await q.answer("Нужно 100,000 🪙")
            return
        user["balance"] -= 100000
        user["business"] = True
        save_db()
        await q.answer("Бизнес куплен!")
        kb = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
        await q.edit_message_text("✅ Бизнес куплен!\n+5,000 к бонусу", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "buyv":
        if user["vip"]:
            return
        if user["balance"] < 200000:
            await q.answer("Нужно 200,000 🪙")
            return
        user["balance"] -= 200000
        user["vip"] = True
        save_db()
        await q.answer("VIP активирован!")
        kb = [[InlineKeyboardButton("↩️ В магазин", callback_data="shop")]]
        await q.edit_message_text("✅ VIP активирован!\nx2 выигрыши и бонусы", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data in ["game_coin", "game_dice", "game_slots"]:
        games = {"game_coin": "Монетка", "game_dice": "Кости", "game_slots": "Слоты"}
        user["current_game"] = q.data
        save_db()
        kb = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
        await q.edit_message_text(
            f"🎮 {games[q.data]}\n💰 Баланс: {user['balance']:,} 🪙\n\nВведите ставку:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "cancel":
        user["current_game"] = None
        save_db()
        kb = [
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]
        await q.edit_message_text("❌ Отменено", reply_markup=InlineKeyboardMarkup(kb))
    
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
            kb = [[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
            await q.edit_message_text(
                f"✅ Бонус: +{bonus:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            kb = [[InlineKeyboardButton("↩️ Меню", callback_data="menu")]]
            await q.edit_message_text("❌ Уже получен!\nЗавтра снова", reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "top":
        su = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        txt = "🏆 Топ-10\n\n"
        for i, item in enumerate(su, 1):
            u_data = item[1]
            vip = "👑" if u_data.get("vip") else ""
            txt += f"{i}. {vip}{u_data['name'][:15]}: {u_data['balance']:,} 🪙\n"
        kb = [[InlineKeyboardButton("↩️ Назад", callback_data="menu")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif q.data == "menu":
        kb = [
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")],
            [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
            [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
            [InlineKeyboardButton("🏆 Топ", callback_data="top")],
        ]
        await q.edit_message_text("🎰 Главное меню\n\nВыберите действие:", reply_markup=InlineKeyboardMarkup(kb))

async def messages(update, context):
    uid = str(update.message.from_user.id)
    user = get_user(uid, update.message.from_user.first_name)
    if not user.get("current_game"):
        return
    try:
        bet = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите число!")
        return
    if bet < 1 or bet > user["balance"]:
        await update.message.reply_text(f"❌ Неверная ставка!\n💰 Баланс: {user['balance']:,} 🪙")
        return
    
    vip = 2 if user["vip"] else 1
    game = user["current_game"]
    win = 0
    
    if game == "game_coin":
        coin = random.choice(["Орёл", "Решка"])
        if random.random() < 0.5:
            win = bet * 2 * vip
            msg = f"🪙 {coin}\n✅ Победа! +{win-bet:,} 🪙"
        else:
            msg = f"🪙 {coin}\n❌ Проигрыш -{bet:,} 🪙"
    elif game == "game_dice":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2 * vip
            msg = f"🎲 {d1}+{d2}={total} (Чёт)\n✅ Победа! +{win-bet:,} 🪙"
        else:
            msg = f"🎲 {d1}+{d2}={total} (Нечет)\n❌ Проигрыш -{bet:,} 🪙"
    elif game == "game_slots":
        s = random.choices(["🍒","🍋","🍊","7️⃣","💎","⭐"], k=3)
        if s[0] == s[1] == s[2]:
            win = bet * 5 * vip
            msg = f"🎰 {' '.join(s)}\n🎉 ДЖЕКПОТ! +{win-bet:,} 🪙"
        elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
            win = bet * 2 * vip
            msg = f"🎰 {' '.join(s)}\n✅ Победа! +{win-bet:,} 🪙"
        else:
            msg = f"🎰 {' '.join(s)}\n❌ Проигрыш -{bet:,} 🪙"
    
    user["balance"] += win - bet
    user["games"] += 1
    if win > 0:
        user["earned"] += win - bet
    else:
        user["lost"] += bet
    user["current_game"] = None
    save_db()
    
    kb = [
        [InlineKeyboardButton("🎰 Играть ещё", callback_data="casino")],
        [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
    ]
    await update.message.reply_text(
        f"{msg}\n💰 Баланс: {user['balance']:,} 🪙",
        reply_markup=InlineKeyboardMarkup(kb)
    )

def main():
    print("Загрузка...")
    load_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))
    print("Бот запущен!")
    save_db()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
