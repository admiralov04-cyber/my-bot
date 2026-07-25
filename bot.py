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
                DB = json.loads(f.read() or "{}")
    except:
        DB = {}

def save_db():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(DB, f)
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
            "cards": 1,
            "cards_income": CARD_BASE_INCOME,
            "cards_price": CARD_BASE_PRICE,
            "tax_balance": 0,
            "tax_limit": 5000000,
            "mining_start": None,
            "mined_total": 0,
            "reg_date": datetime.datetime.now().strftime("%d.%m.%Y в %H:%M:%S"),
            "earned": 0,
            "lost": 0,
            "games": 0,
            "cases_opened": 0,
            "energy": 10,
            "rating": 0,
            "exp": 0,
        }
        save_db()
    return DB[uid]

def format_number(n):
    if n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.1f} трлн"
    elif n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f} млрд"
    elif n >= 1_000_000:
        return f"{n/1_000_000:.1f} млн"
    elif n >= 1_000:
        return f"{n/1_000:.1f} тыс"
    return str(n)

def get_mining_info(user):
    cards = user.get("cards", 1)
    inc = user.get("cards_income", CARD_BASE_INCOME)
    return {
        "cards": cards,
        "income_per_card": inc,
        "total_income": cards * inc,
        "next_price": user.get("cards_price", CARD_BASE_PRICE),
        "tax": user.get("tax_balance", 0),
        "tax_limit": user.get("tax_limit", 5000000)
    }

def buy_card(user):
    info = get_mining_info(user)
    price = info["next_price"]
    if user["balance"] < price:
        return False, price
    user["balance"] -= price
    user["cards"] += 1
    user["cards_price"] = int(price * 1.5)
    if user["cards"] % 10 == 0:
        user["cards_income"] = int(user["cards_income"] * 1.2)
    user["tax_balance"] += int(price * 0.05)
    save_db()
    return True, price

def pay_tax(user):
    tax = user.get("tax_balance", 0)
    if tax <= 0:
        return False, 0
    paid = min(user["balance"], tax)
    user["balance"] -= paid
    user["tax_balance"] -= paid
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
        user["mined_total"] += income
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
        info = get_mining_info(user)
        
        status = "👑 VIP" if user['vip'] else "⭐ Обычный"
        bal = format_number(user['balance'])
        earned = format_number(user['earned'])
        lost = format_number(user['lost'])
        mined = format_number(user['mined_total'])
        exp = format_number(user.get('exp', 0))
        
        txt = f"👤 *{user['name']}*, ваш профиль:\n\n"
        txt += f"🪪 ID: `{uid}`\n"
        txt += f"🏆 Статус: *{status}*\n"
        txt += f"💰 Денег: `{bal}` 🪙\n"
        txt += f"💎 Намайнено: `{mined}` 🪙\n"
        txt += f"💸 Налог: `{user['tax_balance']:,}`/`{user['tax_limit']:,}` 🪙\n"
        txt += f"🏋 Энергия: `{user.get('energy', 10)}`\n"
        txt += f"👑 Рейтинг: `{user.get('rating', 0)}`\n"
        txt += f"🌟 Опыт: `{exp}`\n"
        txt += f"🎲 Всего сыграно игр: `{user['games']}`\n"
        txt += f"🎁 Кейсов открыто: `{user['cases_opened']}`\n"
        txt += f"🏪 Бизнес: {'✅' if user['business'] else '❌'}\n"
        txt += f"🖥 Видеокарт: `{info['cards']}` шт.\n"
        txt += f"💷 Доход майнинга: `{info['total_income']:,}` 🪙/час\n"
        txt += f"\n💚 Заработано: `{earned}` 🪙\n"
        txt += f"💔 Проиграно: `{lost}` 🪙\n"
        txt += f"\n📅 Дата регистрации:\n`{user['reg_date']}`"
        
        kb = [
            [InlineKeyboardButton("⛏ Собрать майнинг", callback_data="collect")],
            [InlineKeyboardButton("💰 Оплатить налог", callback_data="paytax")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text(txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "collect":
        inc = collect_mining(user)
        await q.answer(f"Собрано: {inc:,} 🪙" if inc > 0 else "Нечего собирать")
    
    elif d == "paytax":
        ok, paid = pay_tax(user)
        await q.answer(f"Оплачено: {paid:,} 🪙" if ok else "Нет налогов")
    
    elif d == "casino":
        kb = [
            [InlineKeyboardButton("🪙 Монетка", callback_data="game_coin")],
            [InlineKeyboardButton("🎲 Кости", callback_data="game_dice")],
            [InlineKeyboardButton("🎰 Слоты", callback_data="game_slots")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text(
            f"🎰 Казино\n💰 {user['balance']:,} 🪙\n\nВыберите игру:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif d == "mining":
        collect_mining(user)
        user = get_user(uid)
        info = get_mining_info(user)
        pending = 0
        if user.get("mining_start"):
            try:
                start = datetime.datetime.fromisoformat(user["mining_start"])
                pending = max(0, int(((datetime.datetime.now() - start).total_seconds() / 3600) * info["total_income"]))
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
        
        kb = [[InlineKeyboardButton("🖥 Купить карту", callback_data="buycard")]]
        if pending > 0:
            kb.append([InlineKeyboardButton("💰 Собрать", callback_data="collect")])
        if info["tax"] > 0:
            kb.append([InlineKeyboardButton("💸 Налог", callback_data="paytax")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="menu")])
        await q.edit_message_text(txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "buycard":
        ok, price = buy_card(user)
        await q.answer(f"Куплена! Карт: {get_mining_info(user)['cards']} шт." if ok else f"Нужно {price:,} 🪙")
    
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
        if not case or user["balance"] < case["price"]:
            await q.answer(f"Нужно {case['price']:,} 🪙" if case else "Ошибка")
            return
        user["balance"] -= case["price"]
        reward = random.choice(case["rewards"])
        if random.random() < 0.05:
            reward = case["rewards"][-1]
        user["balance"] += reward
        user["cases_opened"] += 1
        user["earned"] += reward
        user["exp"] = user.get("exp", 0) + random.randint(10, 100)
        save_db()
        txt = f"🎁 {case['name']}\n\n💵 Цена: {case['price']:,} 🪙\n🎉 Выигрыш: {reward:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙"
        if reward == case["rewards"][-1]:
            txt += "\n🔥 ДЖЕКПОТ!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Ещё", callback_data="cases")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]))
    
    elif d == "shop":
        kb = [
            [InlineKeyboardButton("🏪 Бизнес", callback_data="shop_business")],
            [InlineKeyboardButton("💎 VIP", callback_data="shop_vip")],
            [InlineKeyboardButton("↩️ Назад", callback_data="menu")]
        ]
        await q.edit_message_text("🛍 Магазин\n\nКатегория:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "shop_business":
        kb = []
        if not user["business"]:
            kb.append([InlineKeyboardButton("Купить - 100,000🪙", callback_data="buyb")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="shop")])
        await q.edit_message_text(
            f"🏪 Бизнес\n\n💵 100,000 🪙\n💰 +5,000 к бонусу\n{'✅ Куплен' if user['business'] else '❌'}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif d == "shop_vip":
        kb = []
        if not user["vip"]:
            kb.append([InlineKeyboardButton("Купить - 200,000🪙", callback_data="buyv")])
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="shop")])
        await q.edit_message_text(
            f"💎 VIP\n\n💵 200,000 🪙\n💰 x2 выигрыши\n{'✅ Активен' if user['vip'] else '❌'}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif d == "buyb":
        if not user["business"] and user["balance"] >= 100000:
            user["balance"] -= 100000
            user["business"] = True
            save_db()
            await q.answer("Бизнес куплен!")
        else:
            await q.answer("Нужно 100,000 🪙")
    
    elif d == "buyv":
        if not user["vip"] and user["balance"] >= 200000:
            user["balance"] -= 200000
            user["vip"] = True
            save_db()
            await q.answer("VIP активен!")
        else:
            await q.answer("Нужно 200,000 🪙")
    
    elif d in ["game_coin", "game_dice", "game_slots"]:
        games = {"game_coin": "Монетка", "game_dice": "Кости", "game_slots": "Слоты"}
        user["current_game"] = d
        save_db()
        await q.edit_message_text(
            f"🎮 {games[d]}\n💰 {user['balance']:,} 🪙\n\nВведите ставку:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
        )
    
    elif d == "cancel":
        user["current_game"] = None
        save_db()
        await q.edit_message_text(
            "❌ Отменено",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
                [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
            ])
        )
    
    elif d == "daily":
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
            await q.edit_message_text(
                f"✅ Бонус: +{bonus:,} 🪙\n💰 Баланс: {user['balance']:,} 🪙",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="menu")]])
            )
        else:
            await q.edit_message_text(
                "❌ Уже получен!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Меню", callback_data="menu")]])
            )
    
    elif d == "top":
        su = sorted(DB.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        txt = "🏆 Топ-10\n\n"
        for i, item in enumerate(su, 1):
            u = item[1]
            txt += f"{i}. {u['name'][:15]}: {u['balance']:,} 🪙\n"
        await q.edit_message_text(
            txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="menu")]])
        )
    
    elif d == "admin":
        if not admin:
            return
        txt = f"⚙️ Админ\n\n👥 {len(DB)} чел.\n💰 {sum(u['balance'] for u in DB.values()):,} 🪙"
        kb = [
            [InlineKeyboardButton("👥 Список", callback_data="admin_users")],
            [InlineKeyboardButton("💰 Выдать", callback_data="admin_give")],
            [InlineKeyboardButton("🔄 Сброс", callback_data="admin_reset")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_send")],
            [InlineKeyboardButton("↩️ Меню", callback_data="menu")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif d == "admin_users" and admin:
        txt = "👥 Игроки:\n\n"
        for i, (uid, u) in enumerate(list(DB.items())[:20], 1):
            txt += f"{i}. {u['name'][:15]}: {u['balance']:,} 🪙\n"
        await q.edit_message_text(
            txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data="admin")]])
        )
    
    elif d == "admin_give" and admin:
        kb = [[InlineKeyboardButton(f"{u['name'][:20]} - {u['balance']:,}🪙", callback_data=f"give_{uid}")] for uid, u in list(DB.items())[:15]]
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data="admin")])
        await q.edit_message_text("💰 Выдать\n\nКому:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif d.startswith("give_") and admin:
        target = d.replace("give_", "")
        context.user_data["target"] = target
        context.user_data["action"] = "give"
        await q.edit_message_text(
            f"💰 Сумма для {DB[target]['name']}:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="admin")]])
        )
    
    elif d == "admin_reset" and admin:
        for u in DB.values():
            u["last_daily"] = None
        save_db()
        await q.answer("Сброшено!")
    
    elif d == "admin_send" and admin:
        context.user_data["action"] = "send"
        await q.edit_message_text(
            "📢 Сообщение для всех:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="admin")]])
        )
    
    elif d == "menu":
        kb = [
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton("⛏ Майнинг", callback_data="mining")],
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
        win = bet * 2 * vip if random.random() < 0.5 else 0
        msg = f"🪙 {coin}\n{'✅ +' if win > 0 else '❌ -'}{abs(win-bet):,} 🪙"
    elif game == "game_dice":
        d1, d2 = random.randint(1,6), random.randint(1,6)
        t = d1 + d2
        win = bet * 2 * vip if t % 2 == 0 else 0
        msg = f"🎲 {d1}+{d2}={t}\
