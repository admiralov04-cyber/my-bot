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
TREASURY_LIMIT = 100000000
BANK_PERCENT = 5
CHANNEL_URL = "https://t.me/GovTRR"

# VIP настройки
VIP_PRICE = 150
VIP_DAYS = 30
# Ссылка на СБП (замените на свою)
SBP_LINK = "https://finance.ozon.ru/apps/sbp/ozonbankpay/019f9953-f7f2-73f4-9a71-a52a629c1792"
DONATE_REQUESTS = {}

BUSINESSES = {
    1: {"name": "🏪 Ларёк", "price": 100000, "income": 10000},
    2: {"name": "🚗 Автомойка", "price": 200000, "income": 20000},
    3: {"name": "🏪 Магазин 24/7", "price": 450000, "income": 50000},
    4: {"name": "🚙 Автосалон", "price": 5000000, "income": 250000},
    5: {"name": "🏗 Строительная компания", "price": 20000000, "income": 1000000},
    6: {"name": "🏭 Завод", "price": 50000000, "income": 2500000},
}

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
                TREASURY = data.get("treasury", 1000000)
    except:
        DB = {}
        TREASURY = 1000000

def save_db():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"users": DB, "treasury": TREASURY}, f)
    except:
        pass

def is_admin(uid):
    return str(uid) in ADMIN_IDS

def is_vip_active(user):
    if not user.get("vip"):
        return False
    if user.get("vip_until"):
        try:
            until = datetime.datetime.fromisoformat(user["vip_until"])
            if datetime.datetime.now() > until:
                user["vip"] = False
                user["vip_until"] = None
                save_db()
                return False
        except:
            pass
    return user.get("vip", False)

def get_user(uid, name=None):
    global DB
    uid = str(uid)
    if uid not in DB:
        DB[uid] = {
            "name": name or "Игрок", "balance": 10000, "last_daily": None,
            "current_game": None, "businesses": [],
            "cards": 1, "cards_income": CARD_BASE_INCOME, "cards_price": CARD_BASE_PRICE,
            "tax_balance": 0, "mining_start": None, "mined_total": 0,
            "reg_date": datetime.datetime.now().strftime("%d.%m.%Y в %H:%M:%S"),
            "earned": 0, "lost": 0, "games": 0, "cases_opened": 0,
            "energy": 10, "rating": 0, "exp": 0,
            "last_robbery": None, "robbery_success": 0, "robbery_fail": 0,
            "bank_balance": 0, "bank_time": None,
            "vip": False, "vip_until": None, "biz_start": None,
        }
        save_db()
    else:
        is_vip_active(DB[uid])
    return DB[uid]

def give_vip(user, days=VIP_DAYS):
    user["vip"] = True
    user["vip_until"] = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    save_db()
    return f"✅ VIP активирован на {days} дней!\n👑 До: {datetime.datetime.fromisoformat(user['vip_until']).strftime('%d.%m.%Y')}"

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
    return {"cards": c, "inc": inc, "total": c * inc, "price": user.get("cards_price", CARD_BASE_PRICE), "tax": user.get("tax_balance", 0)}

def get_biz_info(user):
    biz_list = user.get("businesses", [])
    total_income = 0
    for biz_id in biz_list:
        biz = BUSINESSES.get(biz_id)
        if biz:
            total_income += biz["income"]
    return {"count": len(biz_list), "max": 2, "total_income": total_income}

def buy_business(user, biz_id):
    biz = BUSINESSES.get(biz_id)
    if not biz:
        return "❌ Бизнес не найден!"
    if biz_id in user.get("businesses", []):
        return "❌ Уже куплен!"
    if len(user.get("businesses", [])) >= 2:
        return "❌ Максимум 2 бизнеса!"
    if user["balance"] < biz["price"]:
        return f"❌ Нужно {biz['price']:,} 🪙"
    user["balance"] -= biz["price"]
    if "businesses" not in user:
        user["businesses"] = []
    user["businesses"].append(biz_id)
    if not user.get("biz_start"):
        user["biz_start"] = datetime.datetime.now().isoformat()
    save_db()
    return f"✅ Куплен: {biz['name']}!\n💰 Доход: {biz['income']:,}/ч"

def collect_biz_income(user):
    if not user.get("businesses") or not user.get("biz_start"):
        return 0
    biz_info = get_biz_info(user)
    if biz_info["total_income"] == 0:
        return 0
    try:
        start = datetime.datetime.fromisoformat(user["biz_start"])
        hours = (datetime.datetime.now() - start).total_seconds() / 3600
        income = max(0, int(hours * biz_info["total_income"]))
    except:
        return 0
    if income > 0:
        vip = is_vip_active(user)
        tax_rate = 0.025 if vip else 0.05  # VIP: -50% налоги
        tax = int(income * tax_rate)
        user["balance"] += income
        user["earned"] = user.get("earned", 0) + income
        user["tax_balance"] = user.get("tax_balance", 0) + tax
        user["biz_start"] = datetime.datetime.now().isoformat()
        save_db()
    return income

def pay_taxes(user):
    tax = user.get("tax_balance", 0)
    if tax <= 0:
        return "✅ Нет неоплаченных налогов!"
    total = user["balance"] + user.get("bank_balance", 0)
    if total < tax:
        return f"❌ Недостаточно средств! Налог: {tax:,} 🪙\n💰 Доступно: {total:,} 🪙"
    from_balance = min(user["balance"], tax)
    user["balance"] -= from_balance
    remaining = tax - from_balance
    if remaining > 0:
        user["bank_balance"] = user.get("bank_balance", 0) - remaining
    global TREASURY
    TREASURY += tax
    user["tax_balance"] = 0
    save_db()
    return f"✅ Налоги оплачены: {tax:,} 🪙\n💰 Баланс: {user['balance']:,}\n🏦 Банк: {user.get('bank_balance', 0):,}"

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
    vip = is_vip_active(user)
    tax_rate = 0.025 if vip else 0.05
    user["tax_balance"] = user.get("tax_balance", 0) + int(p * tax_rate)
    save_db()
    return True, p

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
        return "❌ Вы уже грабили казну сегодня!"
    if TREASURY <= 1000:
        return "🏦 В казне недостаточно средств!"
    cards = user.get("cards", 1)
    vip = is_vip_active(user)
    base_chance = 30
    card_bonus = min(cards * 2, 30)
    vip_bonus = 40 if vip else 0  # VIP: +40% к шансу
    chance = min(base_chance + card_bonus + vip_bonus, 90)
    user["last_robbery"] = today
    if random.randint(1, 100) <= chance:
        stolen = random.randint(1000, min(TREASURY // 2, user["balance"] * 2))
        TREASURY -= stolen
        user["balance"] += stolen
        user["robbery_success"] = user.get("robbery_success", 0) + 1
        user["earned"] = user.get("earned", 0) + stolen
        save_db()
        return f"🦹 Ограбление казны!\n\n🎯 Шанс: {chance}%\n✅ Успех! +{stolen:,} 🪙\n💰 Баланс: {user['balance']:,}\n🏦 В казне: {TREASURY:,}"
    else:
        penalty = max(int(user["balance"] * 0.1), 100)
        user["balance"] -= penalty
        TREASURY += penalty
        user["robbery_fail"] = user.get("robbery_fail", 0) + 1
        save_db()
        return f"🦹 Ограбление казны!\n\n🎯 Шанс: {chance}%\n❌ Провал! -{penalty:,} 🪙\n💰 Баланс: {user['balance']:,}"

def deposit_bank(user, amount):
    if amount <= 0 or amount > user["balance"]:
        return "❌ Неверная сумма!"
    user["balance"] -= amount
    user["bank_balance"] = user.get("bank_balance", 0) + amount
    user["bank_time"] = datetime.datetime.now().isoformat()
    save_db()
    return f"✅ Положено: {amount:,} 🪙\n🏦 В банке: {user['bank_balance']:,}\n💰 Баланс: {user['balance']:,}"

def withdraw_bank(user, amount):
    bank = user.get("bank_balance", 0)
    if amount <= 0:
        return "❌ Неверная сумма!"
    interest = calculate_bank_interest(user)
    total = bank + interest
    if amount > total:
        return f"❌ В банке: {total:,} 🪙"
    user["bank_balance"] = total - amount
    user["bank_time"] = datetime.datetime.now().isoformat()
    user["balance"] += amount
    save_db()
    return f"✅ Снято: {amount:,} 🪙\n💰 Баланс: {user['balance']:,}\n🏦 В банке: {user['bank_balance']:,}"

def calculate_bank_interest(user):
    bank = user.get("bank_balance", 0)
    if bank <= 0 or not user.get("bank_time"):
        return 0
    try:
        start = datetime.datetime.fromisoformat(user["bank_time"])
        hours = (datetime.datetime.now() - start).total_seconds() / 3600
        interest = int(bank * (BANK_PERCENT / 100) * (hours / 24))
        return min(interest, bank * 2)
    except:
        return 0

def add_treasury():
    global TREASURY
    TREASURY += random.randint(50000, 200000)
    if TREASURY > TREASURY_LIMIT:
        TREASURY = TREASURY_LIMIT
    save_db()

def transfer_money(sender, target_id, amount):
    target_id = str(target_id)
    if target_id not in DB:
        return "❌ Игрок не найден!"
    if amount <= 0:
        return "❌ Неверная сумма!"
    if amount > sender["balance"]:
        return "❌ Недостаточно средств!"
    sender["balance"] -= amount
    DB[target_id]["balance"] += amount
    save_db()
    target_name = DB[target_id]["name"]
    return f"✅ Перевод выполнен!\n💸 {amount:,} 🪙 → {target_name}\n💰 Ваш баланс: {sender['balance']:,}"

def show_donate_info(user):
    uid = str(list(DB.keys())[list(DB.values()).index(user)]) if user in DB.values() else ""
    for k, v in DB.items():
        if v == user:
            uid = k
            break
    
    vip_active = is_vip_active(user)
    txt = "💎 *VIP-СТАТУС*\n\n"
    
    if vip_active:
        until = datetime.datetime.fromisoformat(user["vip_until"])
        days_left = (until - datetime.datetime.now()).days
        txt += f"👑 *VIP АКТИВЕН*\n"
        txt += f"📅 Дней осталось: `{days_left}`\n"
        txt += f"⏳ До: `{until.strftime('%d.%m.%Y')}`\n\n"
        txt += "🎁 *Ваши бонусы:*\n"
        txt += "• x3 выигрыши в казино\n"
        txt += "• +40% к шансу ограбления\n"
        txt += "• x5 ежедневный бонус\n"
        txt += "• -50% налоги\n"
    else:
        txt += "❌ VIP не активирован\n\n"
        txt += f"💵 *Цена:* `{VIP_PRICE}₽` на `{VIP_DAYS}` дней\n\n"
        txt += "🎁 *Бонусы VIP:*\n"
        txt += "• 🔥 x3 выигрыши в казино\n"
        txt += "• 🦹 +40% к шансу ограбления\n"
        txt += "• 🎁 x5 ежедневный бонус\n"
        txt += "• 💸 -50% налоги\n\n"
        txt += "📋 *Для покупки:*\n"
        txt += f"1. Оплатите `{VIP_PRICE}₽` по СБП:\n"
        txt += f"[Оплатить через СБП]({SBP_LINK})\n\n"
        txt += "2. Отправьте команду:\n"
        txt += "`донат` или `купить вип`\n\n"
        txt += "3. Админ проверит и активирует VIP!"
    
    return txt

def show_bank(user):
    bank_balance = user.get("bank_balance", 0)
    bank_int = calculate_bank_interest(user)
    tax = user.get("tax_balance", 0)
    txt = "🏦 Банк\n\n"
    txt += f"💰 На счету: {user['balance']:,} 🪙\n"
    txt += f"🏦 В банке: {bank_balance:,} 🪙\n"
    if bank_int > 0:
        txt += f"📈 Проценты: +{bank_int:,} 🪙\n"
    if tax > 0:
        txt += f"💸 Налоги: {tax:,} 🪙\n"
    txt += f"💹 Ставка: {BANK_PERCENT}% в день\n\n"
    txt += "📥 банк [сумма] - положить\n📤 снять [сумма] - снять\n💸 налоги - оплатить"
    return txt

def show_businesses(user):
    biz_info = get_biz_info(user)
    txt = f"🏪 Бизнесы ({biz_info['count']}/{biz_info['max']})\n\n"
    if biz_info['count'] > 0:
        txt += "✅ Ваши:\n"
        for biz_id in user.get("businesses", []):
            biz = BUSINESSES.get(biz_id)
            if biz:
                txt += f"• {biz['name']}: +{biz['income']:,}/ч\n"
        txt += f"\n💰 Доход: {biz_info['total_income']:,}/ч\n\n"
    else:
        txt += "У вас нет бизнесов!\n\n"
    txt += "📋 Доступные:\n\n"
    for biz_id, biz in BUSINESSES.items():
        owned = biz_id in user.get("businesses", [])
        txt += f"{biz_id}. {biz['name']}\n💰 {biz['income']:,}/ч | 💵 {biz['price']:,} 🪙\n{'✅' if owned else '❌'}\n\n"
    txt += "Покупка: купить бизнес [номер]"
    return txt

def get_main_keyboard(uid):
    kb = [
        [InlineKeyboardButton("👤 Профиль", callback_data="p")],
        [InlineKeyboardButton("🎰 Казино", callback_data="c")],
        [InlineKeyboardButton("⛏ Майнинг", callback_data="m")],
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cs")],
        [InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="d")],
        [InlineKeyboardButton("🏆 Топ", callback_data="t")],
        [InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL)],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("⚙️ Админ", callback_data="a")])
    return kb

async def start(update, context):
    u = update.effective_user
    uid = str(u.id)
    get_user(uid, u.first_name or u.username)
    kb = get_main_keyboard(uid)
    await update.message.reply_text(
        f"🎰 Lucky Casino\n\nПривет, {u.first_name or u.username}!\n\n"
        f"банк | бизнес | налоги\nперевести ID сумма\nограбить казну\n"
        f"донат - VIP за {VIP_PRICE}₽",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def buttons(update, context):
    global TREASURY, DONATE_REQUESTS
    q = update.callback_query
    try:
        await q.answer()
    except:
        pass
    uid = str(q.from_user.id)
    user = get_user(uid, q.from_user.first_name or q.from_user.username)
    admin = is_admin(uid)
    d = q.data

    if d == "p":
        cm(user)
        collect_biz_income(user)
        user = get_user(uid)
        info = mi(user)
        biz_info = get_biz_info(user)
        vip = is_vip_active(user)
        bank_int = calculate_bank_interest(user)
        txt = f"👤 {user['name']}\n\n"
        txt += f"🪪 ID: {uid}\n"
        txt += f"{'👑 VIP' if vip else '⭐ Обычный'}\n"
        txt += f"💰 Баланс: {fm(user['balance'])}\n"
        txt += f"🏦 В банке: {fm(user.get('bank_balance', 0))}"
        if bank_int > 0:
            txt += f" (+{fm(bank_int)})"
        txt += f"\n💸 Налоги: {user.get('tax_balance', 0):,} 🪙\n"
        txt += f"💎 Майнинг: {fm(user['mined_total'])}\n"
        txt += f"🖥 Карт: {info['cards']} шт.\n💷 Доход майнинга: {info['total']:,}/ч\n"
        txt += f"🏪 Бизнесов: {biz_info['count']}/{biz_info['max']}\n"
        txt += f"💷 Доход бизнесов: {biz_info['total_income']:,}/ч\n"
        txt += f"🎲 Игр: {user['games']}\n📅 {user['reg_date']}"
        kb = [[InlineKeyboardButton("⛏ Собрать майнинг", callback_data="cl")], [InlineKeyboardButton("🏪 Собрать бизнес", callback_data="cbiz")], [InlineKeyboardButton("💸 Оплатить налоги", callback_data="paytax")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "vip_info":
        await q.edit_message_text(show_donate_info(user), parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="mn")]]), disable_web_page_preview=True)
    
    elif d == "cbiz":
        inc = collect_biz_income(user)
        await q.answer(f"+{inc:,} 🪙" if inc > 0 else "Нечего")
    elif d == "paytax":
        msg = pay_taxes(user)
        await q.answer(msg[:100])
    elif d == "cl":
        inc = cm(user)
        await q.answer(f"+{inc:,}" if inc > 0 else "Нечего")
    elif d == "c":
        kb = [[InlineKeyboardButton("🪙 Монетка", callback_data="gc")], [InlineKeyboardButton("🎲 Кости", callback_data="gd")], [InlineKeyboardButton("🎰 Слоты", callback_data="gs")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text(f"🎰 Казино\n💰 {user['balance']:,}", reply_markup=InlineKeyboardMarkup(kb))
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
        txt = f"⛏ Майнинг\n💷 {info['total']:,}/ч\n📝 {info['cards']} шт.\n🆙 След: {info['price']:,}\n💰 {user['balance']:,}"
        if pending > 0:
            txt += f"\n⏳ {pending:,}"
        kb = [[InlineKeyboardButton("🖥 Купить", callback_data="bc")]]
        if pending > 0:
            kb.append([InlineKeyboardButton("💰 Собрать", callback_data="cl")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="mn")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "bc":
        ok, price = bc(user)
        await q.answer(f"Карт: {mi(user)['cards']}" if ok else f"Нужно {price:,}")
    elif d == "cs":
        kb = [[InlineKeyboardButton(f"📦 Обычный - {CASES['common']['price']:,}", callback_data="oc")], [InlineKeyboardButton(f"🎁 Редкий - {CASES['rare']['price']:,}", callback_data="or")], [InlineKeyboardButton(f"💎 Эпический - {CASES['epic']['price']:,}", callback_data="oe")], [InlineKeyboardButton(f"👑 Легендарный - {CASES['legendary']['price']:,}", callback_data="ol")], [InlineKeyboardButton("↩️ Назад", callback_data="mn")]]
        await q.edit_message_text("🎁 Кейсы", reply_markup=InlineKeyboardMarkup(kb))
    elif d in ["oc", "or", "oe", "ol"]:
        ct = {"oc": "common", "or": "rare", "oe": "epic", "ol": "legendary"}[d]
        case = CASES[ct]
        if user["balance"] < case["price"]:
            await q.answer(f"Нужно {case['price']:,}")
            return
        user["balance"] -= case["price"]
        reward = random.choice(case["rewards"])
        if random.random() < 0.05:
            reward = case["rewards"][-1]
        user["balance"] += reward
        user["cases_opened"] += 1
        user["earned"] = user.get("earned", 0) + reward
        TREASURY += int(case["price"] * 0.1)
        save_db()
        txt = f"🎁 {case['name']}\n💰 +{reward:,}\n💳 {user['balance']:,}"
        if reward == case["rewards"][-1]:
            txt = "🔥 ДЖЕКПОТ!\n" + txt
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Ещё", callback_data="cs")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
    elif d in ["gc", "gd", "gs"]:
        gs = {"gc": "Монетка", "gd": "Кости", "gs": "Слоты"}
        user["current_game"] = d
        save_db()
        await q.edit_message_text(f"🎮 {gs[d]}\n💰 {user['balance']:,}\nСтавка:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cn")]]))
    elif d == "cn":
        user["current_game"] = None
        save_db()
        await q.edit_message_text("❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Казино", callback_data="c")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
    elif d == "d":
        today = str(datetime.date.today())
        if user.get("last_daily") != today:
            bonus = DAILY_START
            biz_info = get_biz_info(user)
            bonus += biz_info["total_income"] // 10
            if is_vip_active(user):
                bonus *= 5  # VIP: x5 бонус
            user["balance"] += bonus
            user["last_daily"] = today
            user["earned"] = user.get("earned", 0) + bonus
            save_db()
            await q.edit_message_text(f"✅ +{bonus:,}\n💰 {user['balance']:,}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
        else:
            await q.edit_message_text("❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))
    elif d == "t":
        su = sorted(DB.items(), key=lambda x: x[1]["balance"] + x[1].get("bank_balance", 0), reverse=True)[:10]
        txt = "🏆 Топ-10\n"
        for i, item in enumerate(su, 1):
            total = item[1]['balance'] + item[1].get('bank_balance', 0)
            txt += f"{i}. {item[1]['name'][:15]}: {total:,}\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="mn")]]))
    elif d == "a" and admin:
        txt = f"⚙️ Админ\n👥 {len(DB)}\n🏦 Казна: {TREASURY:,}\n\n📋 Заявок VIP: {len(DONATE_REQUESTS)}"
        kb = [[InlineKeyboardButton("👥 Список", callback_data="au")], [InlineKeyboardButton("💰 Выдать", callback_data="ag")], [InlineKeyboardButton("📋 Заявки VIP", callback_data="avip")], [InlineKeyboardButton("📢 Рассылка", callback_data="as")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif d == "avip" and admin:
        if not DONATE_REQUESTS:
            await q.answer("Нет заявок!")
            return
        kb = [[InlineKeyboardButton(f"{req['name']} (ID:{uid})", callback_data=f"gvip_{uid}")] for uid, req in DONATE_REQUESTS.items()]
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="a")])
        await q.edit_message_text("📋 Выдать VIP:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("gvip_") and admin:
        target = d.replace("gvip_", "")
        if target in DONATE_REQUESTS and target in DB:
            msg = give_vip(DB[target])
            await q.answer(f"VIP выдан {DB[target]['name']}!")
            del DONATE_REQUESTS[target]
    elif d == "au" and admin:
        txt = "👥\n"
        for i, (uid, u) in enumerate(list(DB.items())[:20], 1):
            vip = "👑" if is_vip_active(u) else ""
            txt += f"{i}. {vip}{u['name'][:15]}: {u['balance']:,}\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️", callback_data="a")]]))
    elif d == "ag" and admin:
        kb = [[InlineKeyboardButton(f"{u['name'][:20]} - {u['balance']:,}", callback_data=f"g_{uid}")] for uid, u in list(DB.items())[:15]]
        kb.append([InlineKeyboardButton("↩️", callback_data="a")])
        await q.edit_message_text("💰", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("g_") and admin:
        target = d.replace("g_", "")
        context.user_data["target"] = target
        context.user_data["action"] = "give"
        await q.edit_message_text(f"Сумма для {DB[target]['name']}:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️", callback_data="a")]]))
    elif d == "as" and admin:
        context.user_data["action"] = "send"
        await q.edit_message_text("Сообщение:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️", callback_data="a")]]))
    elif d == "mn":
        kb = get_main_keyboard(uid)
        await q.edit_message_text("🎰 Меню", reply_markup=InlineKeyboardMarkup(kb))

async def messages(update, context):
    global TREASURY, DONATE_REQUESTS
    if not update.message or not update.message.text:
        return
    uid = str(update.message.from_user.id)
    name = update.message.from_user.first_name or update.message.from_user.username
    user = get_user(uid, name)
    admin = is_admin(uid)
    text = update.message.text.strip().lower()

    # Донат
    if text in ["донат", "купить вип", "куплю вип", "хочу вип"]:
        if is_vip_active(user):
            await update.message.reply_text("❌ У вас уже активен VIP!")
            return
        DONATE_REQUESTS[uid] = {"name": user["name"], "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}
        await update.message.reply_text(
            f"📋 *Заявка на VIP*\n\n"
            f"💵 Стоимость: `{VIP_PRICE}₽`\n"
            f"📅 Срок: `{VIP_DAYS}` дней\n\n"
            f"💳 [Оплатить через СБП]({SBP_LINK})\n\n"
            f"✅ После оплаты админ активирует VIP!\n"
            f"🆔 Ваш ID: `{uid}`",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=int(admin_id), text=f"📋 Новая заявка на VIP!\n👤 {user['name']} (ID: {uid})")
            except:
                pass
        return

    if text in ["вип", "vip"]:
        await update.message.reply_text(show_donate_info(user), parse_mode='Markdown', disable_web_page_preview=True)
        return

    # Банк
    if text == "банк":
        await update.message.reply_text(show_bank(user))
        return
    if text.startswith("банк "):
        parts = text.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[1])
                msg = deposit_bank(user, amount)
                await update.message.reply_text(msg)
            except:
                await update.message.reply_text("❌ Пример: банк 1000")
        return
    if text.startswith("снять "):
        parts = text.split()
        if len(parts) >= 2:
            if parts[1] == "все":
                interest = calculate_bank_interest(user)
                total = user.get("bank_balance", 0) + interest
                if total > 0:
                    user["balance"] += total
                    user["bank_balance"] = 0
                    user["bank_time"] = None
                    save_db()
                    await update.message.reply_text(f"✅ Снято все: {total:,} 🪙\n💰 Баланс: {user['balance']:,}")
                else:
                    await update.message.reply_text("❌ Банк пуст!")
            else:
                try:
                    amount = int(parts[1])
                    msg = withdraw_bank(user, amount)
                    await update.message.reply_text(msg)
                except:
                    await update.message.reply_text("❌ Пример: снять 500")
        return

    # Бизнесы
    if text in ["бизнес", "бизнесы"]:
        await update.message.reply_text(show_businesses(user))
        return
    if text.startswith("купить бизнес "):
        parts = text.split()
        if len(parts) >= 3:
            try:
                biz_id = int(parts[2])
                msg = buy_business(user, biz_id)
                await update.message.reply_text(msg)
            except:
                await update.message.reply_text("❌ Неверный номер! (1-6)")
        return

    # Налоги
    if text == "налоги":
        msg = pay_taxes(user)
        await update.message.reply_text(msg)
        return

    # Перевод
    if text.startswith("перевести ") or text.startswith("перевод "):
        parts = text.split()
        if len(parts) >= 3:
            try:
                target_id = parts[1]
                amount = int(parts[2])
                msg = transfer_money(user, target_id, amount)
                await update.message.reply_text(msg)
            except:
                await update.message.reply_text("❌ Пример: перевести 1439955343 5000")
        return

    # Ограбление
    if text in ["ограбить казну", "ограбить", "ограбление"]:
        result = try_robbery(user)
        await update.message.reply_text(result)
        return

    # Админ
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
                        await update.message.reply_text(f"✅ +{amount:,}")
                except:
                    pass
            context.user_data["action"] = None
            return
        elif act == "send":
            ok = 0
            for u in DB:
                try:
                    await context.bot.send_message(chat_id=int(u), text=update.message.text)
                    ok += 1
                except:
                    pass
            await update.message.reply_text(f"✅ {ok}")
            context.user_data["action"] = None
            return

    # Игры
    if not user.get("current_game"):
        return
    try:
        bet = int(text)
    except:
        return
    if bet < 1 or bet > user["balance"]:
        await update.message.reply_text(f"❌ Неверно!\n💰 {user['balance']:,} 🪙")
        return
    vip = 3 if is_vip_active(user) else 1  # VIP: x3 выигрыш
    game = user["current_game"]
    win = 0
    if game == "gc":
        coin = random.choice(["Орёл", "Решка"])
        win = bet * 2 * vip if random.random() < 0.5 else 0
        msg = f"🪙 {coin}\n" + ("✅ +" if win > 0 else "❌ -") + f"{abs(win-bet):,} 🪙"
    elif game == "gd":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        t = d1 + d2
        win = bet * 2 * vip if t % 2 == 0 else 0
        msg = f"🎲 {d1}+{d2}={t}\n" + ("✅ +" if win > 0 else "❌ -") + f"{abs(win-bet):,} 🪙"
    else:
        s = random.choices(["🍒","🍋","🍊","7️⃣","💎","⭐"], k=3)
        if s[0] == s[1] == s[2]:
            win = bet * 5 * vip
        elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
            win = bet * 2 * vip
        msg = f"🎰 {' '.join(s)}\n" + ("✅ +" if win > 0 else "❌ -") + f"{abs(win-bet):,} 🪙"
    user["balance"] += win - bet
    user["games"] += 1
    if win > 0:
        user["earned"] = user.get("earned", 0) + win - bet
    else:
        user["lost"] = user.get("lost", 0) + bet
        TREASURY += int(bet * 0.05)
    user["current_game"] = None
    save_db()
    await update.message.reply_text(f"{msg}\n💰 Баланс: {user['balance']:,} 🪙", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Играть", callback_data="c")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))

def main():
    load_db()
    add_treasury()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT, messages))
    save_db()
    print("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
