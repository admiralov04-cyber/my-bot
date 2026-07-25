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

# Базовая цена и доход видеокарты
CARD_BASE_PRICE = 5000
CARD_BASE_INCOME = 100

# Кейсы
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
            "cards": 1,  # Количество видеокарт
            "cards_income": CARD_BASE_INCOME,  # Доход с 1 карты
            "cards_price": CARD_BASE_PRICE,  # Цена следующей карты
            "tax_balance": 0,  # Налоговый счет
            "tax_limit": 5000000,  # Лимит налогов
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

def get_mining_info(user):
    cards = user.get("cards", 1)
    income_per_card = user.get("cards_income", CARD_BASE_INCOME)
    total_income = cards * income_per_card
    next_price = user.get("cards_price", CARD_BASE_PRICE)
    tax = user.get("tax_balance", 0)
    tax_limit = user.get("tax_limit", 5000000)
    
    return {
        "cards": cards,
        "income_per_card": income_per_card,
        "total_income": total_income,
        "next_price": next_price,
        "tax": tax,
        "tax_limit": tax_limit,
    }

def buy_card(user):
    info = get_mining_info(user)
    price = info["next_price"]
    
    if user["balance"] < price:
        return False, price
    
    # Покупаем карту
    user["balance"] -= price
    user["cards"] = user.get("cards", 1) + 1
    
    # Увеличиваем цену следующей карты (x1.5)
    user["cards_price"] = int(price * 1.5)
    
    # Каждые 10 карт увеличиваем доход
    if user["cards"] % 10 == 0:
        user["cards_income"] = int(user["cards_income"] * 1.2)
    
    # Налог 5% с покупки
    tax_amount = int(price * 0.05)
    user["tax_balance"] = user.get("tax_balance", 0) + tax_amount
    
    save_db()
    return True, price

def pay_tax(user):
    tax = user.get("tax_balance", 0)
    if tax <= 0:
        return False, 0
    
    if user["balance"] < tax:
        # Списываем сколько можем
        paid = user["balance"]
        user["balance"] = 0
        user["tax_balance"] = tax - paid
    else:
        user["balance"] -= tax
        paid = tax
        user["tax_balance"] = 0
    
    save_db()
    return True, paid

def collect_mining(user):
    if not user.get("mining_start"):
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
        return 0
    
    info = get_mining_info(user)
    try:
        start = datetime.datetime.fromisoformat(user["mining_start"])
        hours = (datetime.datetime.now() - start).total_seconds() / 3600
        income = max(0, int(hours * info["total_income"]))
    except:
        income = 0
    
    if income > 0:
        user["balance"] += income
        user["mined_total"] = user.get("mined_total", 0) + income
        user["mining_start"] = datetime.datetime.now().isoformat()
        save_db()
    
    return income

async def start(update, context):
    u = update.effective_user
    uid = str(u.id)
    get_user(uid, u.first_name)
    kb = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
        [InlineKeyboardButton("⛏ Майнинг ферма", callback_data="mining")],
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
        info = get_mining_info(user)
        txt = f"👤 Профиль\n\n"
        txt += f"💰 Баланс: {user['balance']:,} 🪙\n"
        txt += f"📅 Регистрация: {user['reg_date']}\n"
        txt += f"🎮 Игр: {user['games']}\n"
        txt += f"🎁 Кейсов: {user['cases_opened']}\n\n"
        txt += f"⛏ Майнинг:\n"
        txt += f"🖥 Видеокарт: {info['cards']} шт.\n"
        txt += f"💷 Доход: {info['total_income']:,} 🪙/час\n"
        txt += f"💎 Намайнено: {user['mined_total']:,} 🪙\n"
        txt += f"💸 Налог: {user['tax_balance']:,}/{user['tax_limit']:,} 🪙\n"
        txt += f"🏪 Бизнес: {'✅' if user['business'] else '❌'}\n"
        txt += f"💎 VIP: {'✅' if user['vip'] else '❌'}\n\n"
        txt += f"💚 Заработано: {user['earned']:,} 🪙\n"
        txt += f"💔 Проиграно: {user['lost']:,} 🪙"
        kb = [
            [InlineKeyboardButton("⛏ Собрать майнинг", callback_data="collect")],
            [InlineKeyboardButton("💰 Оплатить налог", callback_data="paytax")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "collect":
        inc = collect_mining(user)
        await q.answer(f"Собрано: {inc:,} 🪙" if inc > 0 else "Нечего собирать")
    
    elif d == "paytax":
        ok, paid = pay_tax(user)
        if ok:
            await q.answer(f"Оплачено: {paid:,} 🪙")
        else:
            await q.answer("Нет налогов для оплаты")
    
    elif d == "casino":
        kb = [
            [InlineKeyboardButton("🪙 Монетка (x2)", callback_data="game_coin")],
            [InlineKeyboardButton("🎲 Кости (x2)", callback_data="game_dice")],
            [InlineKeyboardButton("🎰 Слоты (x5)", callback_data="game_slots")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text(f"🎰 Казино\n💰 Баланс: {user['balance']:,} 🪙\n\nВыберите игру:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "mining":
        collect_mining(user)
        user = get_user(uid)
        info = get_mining_info(user)
        pending = 0
        if user.get("mining_start"):
            try:
                start = datetime.datetime.fromisoformat(user["mining_start"])
                hours = (datetime.datetime.now() - start).total_seconds() / 3600
                pending = max(0, int(hours * info["total_income"]))
            except:
                pass
        
        txt = f"⛏ *Майнинг ферма*\n\n"
        txt += f"💷 Доход: `{info['total_income']:,}` 🪙/час\n"
        txt += f"📝 Видеокарты: `{info['cards']}` шт./♾️ шт.\n"
        txt += f"💵 Доход с карты: `{info['income_per_card']:,}` 🪙/час\n"
        txt += f"🆙 Цена следующей: `{info['next_price']:,}` 🪙\n\n"
        txt += f"💸 Налоги: `{info['tax']:,}`/`{info['tax_limit']:,}` 🪙\n"
        txt += f"💰 На счету: `{user['balance']:,}` 🪙\n"
        if pending > 0:
            txt += f"\n⏳ Ожидает сбора: `{pending:,}` 🪙"
        
        kb = [
            [InlineKeyboardButton("🖥 Купить видеокарту", callback_data="buycard")],
        ]
        if pending > 0:
            kb.append([InlineKeyboardButton("💰 Собрать доход", callback_data="collect")])
        if info["tax"] > 0:
            kb.append([InlineKeyboardButton("💸 Оплатить налог", callback_data="paytax")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="menu")])
        
        await q.edit_message_text(txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "buycard":
        info = get_mining_info(user)
        ok, price = buy_card(user)
        if ok:
            info2 = get_mining_info(user)
            await q.answer(f"✅ Куплена! Видеокарт: {info2['cards']} шт.")
        else:
            await q.answer(f"❌ Нужно {price:,} 🪙")
    
    elif d == "cases":
        kb = [
            [InlineKeyboardButton(f"📦 Обычный - {CASES['common']['price']:,}🪙", callback_data="open_common")],
            [InlineKeyboardButton(f"🎁 Редкий - {CASES['rare']['price']:,}🪙", callback_data="open_rare")],
            [InlineKeyboardButton(f"💎 Эпический - {CASES['epic']['price']:,}🪙", callback_data="open_epic")],
            [InlineKeyboardButton(f"👑 Легендарный - {CASES['legendary']['price']:,}🪙", callback_data="open_legendary")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
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
        kb = [
            [InlineKeyboardButton("🏪 Бизнес", callback_data="shop_business")],
            [InlineKeyboardButton("💎 VIP", callback_data="shop_vip")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text("🛍 Магазин\n\nКатегория:", reply_markup=InlineKeyboardMarkup(kb))
    
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
        kb = [
            [InlineKeyboardButton("👥 Список", callback_data="admin_users")],
            [InlineKeyboardButton("💰 Выдать", callback_data="admin_give")],
            [InlineKeyboardButton("🔄 Сброс бонусов", callback_data="admin_reset")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_send")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]
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
        kb = [
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("⛏ Майнинг ферма", callback_data="mining")],
            [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
            [InlineKeyboardButton("🛍 Магазин", callback_data="shop")],
            [InlineKeyboardButton("🎁 Бонус", callback_data="daily")],
            [InlineKeyboardButton("🏆 Топ", callback_data="top")],
        ]
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
            msg =
