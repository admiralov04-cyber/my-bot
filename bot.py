import json, os, datetime, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.getenv("API_TOKEN")
ADMIN_IDS = ["1439955343"]
DATA_FILE = "user_data.json"
DAILY_START = 10000
DB = {}
CARD_BASE_PRICE = 5000
CARD_BASE_INCOME = 100
TREASURY = 0
TREASURY_LIMIT = 1000000

CASES = {
    "common": {"name": "Обычный", "price": 5000, "rewards": [1000, 2000, 3000, 5000, 10000]},
    "rare": {"name": "Редкий", "price": 15000, "rewards": [5000, 10000, 20000, 35000, 50000]},
    "epic": {"name": "Эпический", "price": 50000, "rewards": [15000, 30000, 50000, 100000, 200000]},
    "legendary": {"name": "Легендарный", "price": 150000, "rewards": [50000, 100000, 200000, 500000, 1000000]},
}

def load_db():
    global DB, TREASURY
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.loads(f.read() or "{}")
                DB = data.get("users", {})
                TREASURY = data.get("treasury", 0)
    except:
        DB = {}
        TREASURY = 0

def save_db():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"users": DB, "treasury": TREASURY}, f)
    except:
        pass

def is_admin(uid):
    return str(uid) in ADMIN_IDS

def get_user(uid, name=None):
    global DB
    uid = str(uid)
    if uid not in DB:
        DB[uid] = {
            "name": name or "Игрок", "balance": 10000, "last_daily": None,
            "current_game": None, "business": False, "vip": False,
            "cards": 1, "cards_income": CARD_BASE_INCOME, "cards_price": CARD_BASE_PRICE,
            "tax_balance": 0, "tax_limit": 5000000, "mining_start": None, "mined_total": 0,
            "reg_date": datetime.datetime.now().strftime("%d.%m.%Y в %H:%M:%S"),
            "earned": 0, "lost": 0, "games": 0, "cases_opened": 0,
            "energy": 10, "rating": 0, "exp": 0,
            "last_robbery": None, "robbery_success": 0, "robbery_fail": 0,
        }
        save_db()
    return DB[uid]

def fm(n):
    if n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.1f} трлн"
    elif n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f} млрд"
    elif n >= 1_000_000:
        return f"{n/1_000_000:.1f} млн"
    elif n >= 1_000:
        return f"{n/1_000:.1f} тыс"
    return str(n)

def mi(user):
    c = user.get("cards", 1)
    inc = user.get("cards_income", CARD_BASE_INCOME)
    return {"cards": c, "inc": inc, "total": c * inc, "price": user.get("cards_price", CARD_BASE_PRICE), "tax": user.get("tax_balance", 0), "tlim": user.get("tax_limit", 5000000)}

def bc(user):
    info = mi(user)
    p = info["price"]
    if user["balance"] < p:
        return False, p
    user["balance"] -= p
    user["cards"] += 1
    user["cards_price"] = int(p * 1.5)
    if user["cards"] % 10 == 0:
        user["cards_income"] = int(user["cards_income"] * 1.2)
    user["tax_balance"] += int(p * 0.05)
    save_db()
    return True, p

def pt(user):
    tax = user.get("tax_balance", 0)
    if tax <= 0:
        return False, 0
    paid = min(user["balance"], tax)
    user["balance"] -= paid
    user["tax_balance"] -= paid
    global TREASURY
    TREASURY += paid
    if TREASURY > TREASURY_LIMIT:
        TREASURY = TREASURY_LIMIT
    save_db()
    return True, paid

def cm(user):
    if not user.get("mining_start"):
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
        return 0
    info = mi(user)
    try:
        start = datetime.datetime.fromisoformat(user["mining_start"])
        hours = (datetime.datetime.now() - start).total_seconds() / 3600
        income = max(0, int(hours * info["total"]))
    except:
        income = 0
    if income > 0:
        user["balance"] += income
        user["mined_total"] += income
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
    return income

def try_robbery(user):
    global TREASURY
    today = str(datetime.date.today())
    if user.get("last_robbery") == today:
        return "❌ Вы уже грабили казну сегодня! Приходите завтра."
    if TREASURY <= 0:
        return "🏦 Казна пуста! Подождите пополнения."
    cards = user.get("cards", 1)
    vip = user.get("vip", False)
    base_chance = 30
    card_bonus = min(cards * 2, 30)
    vip_bonus = 15 if vip else 0
    success_chance = min(base_chance + card_bonus + vip_bonus, 80)
    user["last_robbery"] = today
    if random.randint(1, 100) <= success_chance:
        max_steal = min(TREASURY, user["balance"] * 2)
        if max_steal < 1000:
            user["last_robbery"] = None
            return "🏦 В казне недостаточно средств!"
        stolen = random.randint(1000, max_steal)
        TREASURY -= stolen
        user["balance"] += stolen
        user["robbery_success"] = user.get("robbery_success", 0) + 1
        user["earned"] += stolen
        user["exp"] = user.get("exp", 0) + random.randint(50, 200)
        save_db()
        return f"🦹 Ограбление казны!\n\n🎯 Шанс: {success_chance}%\n✅ Успех!\n💰 Украдено: {stolen:,} 🪙\n💳 Баланс: {user['balance']:,} 🪙\n🏦 В казне: {TREASURY:,} 🪙"
    else:
        penalty = max(int(user["balance"] * 0.1), 100)
        user["balance"] -= penalty
        TREASURY += penalty
        user["robbery_fail"] = user.get("robbery_fail", 0) + 1
        save_db()
        return f"🦹 Ограбление казны!\n\n🎯 Шанс: {success_chance}%\n❌ Провал!\n👮 Штраф: {penalty:,} 🪙\n💳 Баланс: {user['balance']:,} 🪙\n🏦 В казне: {TREASURY:,} 🪙"

async def start(update, context):
    u = update.effective_user
    uid = str(u.id)
    get_user(uid, u.first_name)
    kb = [
        [InlineKeyboardButton("👤 Профиль", callback_data="p")],
        [InlineKeyboardButton("🎰 Казино", callback_data="c")],
        [InlineKeyboardButton("⛏ Майнинг", callback_data="m")],
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cs")],
        [InlineKeyboardButton("🛍 Магазин", callback_data="s")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="d")],
        [InlineKeyboardButton("🏆 Топ", callback_data="t")],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("⚙️ Админ", callback_data="a")])
    await update.message.reply_text(
        f"🎰 Lucky Casino\n\nПривет, {u.first_name}!\n🏦 В казне: {TREASURY:,} 🪙\n\nНапишите \"ограбить казну\"!",
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

    if d == "p":
        cm(user)
        user = get_user(uid)
        info = mi(user)
        st = "👑 VIP" if user['vip'] else "⭐ Обычный"
        txt = f"👤 {user['name']}, ваш профиль:\n\n"
        txt += f"🪪 ID: {uid}\n🏆 Статус: {st}\n💰 Денег: {fm(user['balance'])} 🪙\n"
        txt += f"💎 Намайнено: {fm(user['mined_total'])} 🪙\n"
        txt += f"💸 Налог: {user['tax_balance']:,}/{user['tax_limit']:,} 🪙\n"
        txt += f"🏋 Энергия: {user.get('energy', 10)}\n👑 Рейтинг: {user.get('rating', 0)}\n"
        txt += f"🌟 Опыт: {fm(user.get('exp', 0))}\n🎲 Игр: {user['games']}\n"
        txt += f"🎁 Кейсов: {user['cases_opened']}\n"
        txt += f"🦹 Ограблений: {user.get('robbery_success', 0)}/{user.get('robbery_fail', 0) + user.get('robbery_success', 0)}\n"
        txt += f"🏪 Бизнес: {'✅' if user['business'] else '❌'}\n"
        txt += f"🖥 Видеокарт: {info['cards']} шт.\n💷 Доход: {info['total']:,} 🪙/час\n"
        txt += f"\n💚 Заработано: {fm(user['earned'])} 🪙\n💔 Проиграно: {fm(user['lost'])} 🪙\n"
        txt += f"\n📅 Регистрация:\n{user['reg_date']}"
        kb = [[InlineKeyboardButton("⛏ Собрать", callback_data="cl")], [InlineKeyboardButton("💰 Налог", callback_data="pt")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "cl":
        inc = cm(user)
        await q.answer(f"Собрано: {inc:,} 🪙" if inc > 0 else "Нечего собирать")
    elif d == "pt":
        ok, paid = pt(user)
        await q.answer(f"Оплачено: {paid:,} 🪙" if ok else "Нет налогов")
    elif d == "c":
        kb = [[InlineKeyboardButton("🪙 Монетка", callback_data="gc")], [InlineKeyboardButton("🎲 Кости", callback_data="gd")], [InlineKeyboardButton("🎰 Слоты", callback_data="gs")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text(f"🎰 Казино\n💰 {user['balance']:,} 🪙\n\nВыберите игру:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "m":
        cm(user)
        user = get_user(uid)
        info = mi(user)
        pending = 0
        if user.get("mining_start"):
            try:
                start = datetime.datetime.fromisoformat(user["mining_start"])
                pending = max(0, int(((datetime.datetime.now() - start).total_seconds() / 3600) * info["total"]))
            except:
                pass
        txt = f"⛏ Майнинг ферма\n\n💷 Доход: {info['total']:,} 🪙/час\n📝 Видеокарты: {info['cards']} шт./♾️ шт.\n💵 С карты: {info['inc']:,} 🪙/час\n🆙 Следующая: {info['price']:,} 🪙\n\n💸 Налоги: {info['tax']:,}/{info['tlim']:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙"
        if pending > 0:
            txt += f"\n⏳ Ожидает: {pending:,} 🪙"
        kb = [[InlineKeyboardButton("🖥 Купить карту", callback_data="bc")]]
        if pending > 0:
            kb.append([InlineKeyboardButton("💰 Собрать", callback_data="cl")])
        if info["tax"] > 0:
            kb.append([InlineKeyboardButton("💸 Налог", callback_data="pt")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="mn")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "bc":
        ok, price = bc(user)
        await q.answer(f"Куплена! Карт: {mi(user)['cards']} шт." if ok else f"Нужно {price:,} 🪙")
    elif d == "cs":
        kb = [[InlineKeyboardButton(f"📦 Обычный - {CASES['common']['price']:,}🪙", callback_data="oc")], [InlineKeyboardButton(f"🎁 Редкий - {CASES['rare']['price']:,}🪙", callback_data="or")], [InlineKeyboardButton(f"💎 Эпический - {CASES['epic']['price']:,}🪙", callback_data="oe")], [InlineKeyboardButton(f"👑 Легендарный - {CASES['legendary']['price']:,}🪙", callback_data="ol")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text(f"🎁 Кейсы\n🏦 В казне: {TREASURY:,} 🪙\n\nВыберите:", reply_markup=InlineKeyboardMarkup(kb))
    elif d in ["oc", "or", "oe", "ol"]:
        ct = {"oc": "common", "or": "rare", "oe": "epic", "ol": "legendary"}[d]
        case = CASES[ct]
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
        user["exp"] = user.get("exp", 0) + random.randint(10, 100)
        global TREASURY
        TREASURY += int(case["price"] * 0.1)
        if TREASURY > TREASURY_LIMIT:
            TREASURY = TREASURY_LIMIT
        save_db()
        txt = f"🎁 {case['name']}\n\n💵 Цена: {case['price']:,} 🪙\n🎉 Выигрыш: {reward:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙"
        if reward == case["rewards"][-1]:
            txt += "\n🔥 ДЖЕКПОТ!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Ещё", callback_data="cs")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
    elif d == "s":
        kb = [[InlineKeyboardButton("🏪 Бизнес", callback_data="sb")], [InlineKeyboardButton("💎 VIP", callback_data="sv")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text("🛍 Магазин\n\nКатегория:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "sb":
        kb = []
        if not user["business"]:
            kb.append([InlineKeyboardButton("Купить - 100,000🪙", callback_data="bb")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="s")])
        await q.edit_message_text(f"🏪 Бизнес\n\n💵 100,000 🪙\n💰 +5,000 к бонусу\n{'✅ Куплен' if user['business'] else '❌'}", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "sv":
        kb = []
        if not user["vip"]:
            kb.append([InlineKeyboardButton("Купить - 200,000🪙", callback_data="bv")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="s")])
        await q.edit_message_text(f"💎 VIP\n\n💵 200,000 🪙\n💰 x2 выигрыши\n+15% к шансу ограбления\n{'✅ Активен' if user['vip'] else '❌'}", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "bb":
        if not user["business"] and user["balance"] >= 100000:
            user["balance"] -= 100000
            user["business"] = True
            save_db()
            await q.answer("Бизнес куплен!")
        else:
            await q.answer("Нужно 100,000 🪙")
    elif d == "bv":
        if not user["vip"] and user["balance"] >= 200000:
            user["balance"] -= 200000
            user["vip"] = True
            save_db()
            await q.answer("VIP активен!")
        else:
            await q.answer("Нужно 200,000 🪙")
    elif d in ["gc", "gd", "gs"]:
        gs = {"gc": "Монетка", "gd": "Кости", "gs": "Слоты"}
        user["current_game"] = d
        save_db()
        await q.edit_message_text(f"🎮 {gs[d]}\n💰 {user['balance']:,} 🪙\n\nВведите ставку:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cn")]]))
    elif d == "cn":
        user["current_game"] = None
        save_db()
        await q.edit_message_text("❌ Отменено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Казино", callback_data="c")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
    elif d == "d":
        today = str(datetime.date.today())
        if user.get("last_daily") != today:
            bonus = DAILY_START + (5000 if user["business"] else 0)
            if user["vip"]:
                bonus *= 2
            user["balance"] += bonus
            user["last_daily"] = today
            user["earned"] += bonus
            user["exp"] = user.get("exp", 0) + 100
            save_db()
            await q.edit_message_text(f"✅ Бонус: +{bonus:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
        else:
            await q.edit_message_text("❌ Уже получен!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
    elif d == "t":
        su = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        txt = "🏆 Топ-10\n\n"
        for i, item in enumerate(su, 1):
            u = item[1]
            txt += f"{i}. {u['name'][:15]}: {u['balance']:,} 🪙\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="mn")]]))
    elif d == "a":
        if not admin:
            return
        txt = f"⚙️ Админ\n\n👥 {len(DB)} чел.\n💰 Общий: {sum(u['balance'] for u in DB.values()):,} 🪙\n🏦 Казна: {TREASURY:,} 🪙"
        kb = [[InlineKeyboardButton("👥 Список", callback_data="au")], [InlineKeyboardButton("💰 Выдать", callback_data="ag")], [InlineKeyboardButton("🏦 Пополнить казну", callback_data="at")], [InlineKeyboardButton("🔄 Сброс", callback_data="ar")], [InlineKeyboardButton("📢 Рассылка", callback_data="as")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "at" and admin:
        context.user_data["action"] = "treasury"
        await q.edit_message_text("🏦 Сумма для казны:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="a")]]))
    elif d == "au" and admin:
        txt = "👥 Игроки:\n\n"
        for i, (uid, u) in enumerate(list(DB.items())[:20], 1):
            txt += f"{i}. {u['name'][:15]}: {u['balance']:,} 🪙\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="a")]]))
    elif d == "ag" and admin:
        kb = [[InlineKeyboardButton(f"{u['name'][:20]} - {u['balance']:,}🪙", callback_data=f"g_{uid}")] for uid, u in list(DB.items())[:15]]
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="a")])
        await q.edit_message_text("💰 Выдать\n\nКому:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("g_") and admin:
        target = d.replace("g_", "")
        context.user_data["target"] = target
        context.user_data["action"] = "give"
        await q.edit_message_text(f"💰 Сумма для {DB[target]['name']}:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="a")]]))
    elif d == "ar" and admin:
        for u in DB.values():
            u["last_daily"] = None
        save_db()
        await q.answer("Сброшено!")
    elif d == "as" and admin:
        context.user_data["action"] = "send"
        await q.edit_message_text("📢 Сообщение для всех:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="a")]]))
    elif d == "mn":
        kb = [
            [InlineKeyboardButton("👤 Профиль", callback_data="p")],
            [InlineKeyboardButton("🎰 Казино", callback_data="c")],
            [InlineKeyboardButton("⛏ Майнинг", callback_data="m")],
            [InlineKeyboardButton("🎁 Кейсы", callback_data="cs")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="s")],
            [InlineKeyboardButton("🎁 Бонус", callback_data="d")],
            [InlineKeyboardButton("🏆 Топ", callback_data="t")],
        ]
        if admin:
            kb.append([InlineKeyboardButton("⚙️ Админ", callback_data="a")])
        await q.edit_message_text(f"🎰 Меню\n🏦 В казне: {TREASURY:,} 🪙\n\nНапишите \"ограбить казну\"!", reply_markup=InlineKeyboardMarkup(kb))

async def messages(update, context):
    uid = str(update.message.from_user.id)
    user = get_user(uid, update.message.from_user.first_name)
    admin = is_admin(uid)
    global TREASURY
    text = update.message.text.strip().lower()
    
    if text in ["ограбить казну", "ограбление казны", "ограбить"]:
        result = try_robbery(user)
        await update.message.reply_text(result)
        return
    
    if admin and context.user_data.get("action"):
        act = context.user_data["action"]
        if act == "give":
            target = context.user_data.get("target")
            if target and target in DB:
                try:
                    amount = int(text)
                    if amount > 0:
                        DB[target]["balance"] += amount
                        save_db()
                        await update.message.reply_text(f"✅ +{amount:,} 🪙 для {DB[target]['name']}")
                except:
                    await update.message.reply_text("❌ Число!")
            context.user_data["action"] = None
            return
        elif act == "send":
            ok = 0
            for u in DB:
                try:
                    await context.bot.send_message(chat_id=int(u), text=f"📢 {update.message.text}")
                    ok += 1
                except:
                    pass
            await update.message.reply_text(f"✅ Отправлено: {ok}")
            context.user_data["action"] = None
            return
        elif act == "treasury":
            try:
                amount = int(text)
                if amount > 0:
                    TREASURY += amount
                    if TREASURY > TREASURY_LIMIT:
                        TREASURY = TREASURY_LIMIT
                    save_d
