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
            "name": name or "Игрок", "balance": 10000, "last_daily": None,
            "current_game": None, "business": False, "vip": False,
            "cards": 1, "cards_income": CARD_BASE_INCOME, "cards_price": CARD_BASE_PRICE,
            "tax_balance": 0, "tax_limit": 5000000, "mining_start": None, "mined_total": 0,
            "reg_date": datetime.datetime.now().strftime("%d.%m.%Y в %H:%M:%S"),
            "earned": 0, "lost": 0, "games": 0, "cases_opened": 0,
            "energy": 10, "rating": 0, "exp": 0,
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
    await update.message.reply_text(f"🎰 Lucky Casino\n\nПривет, {u.first_name}!", reply_markup=InlineKeyboardMarkup(kb))

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
        txt += f"🎁 Кейсов: {user['cases_opened']}\n🏪 Бизнес: {'✅' if user['business'] else '❌'}\n"
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
        await q.edit_message_text("🎁 Кейсы\n\nВыберите:", reply_markup=InlineKeyboardMarkup(kb))
    
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
        await q.edit_message_text(f"💎 VIP\n\n💵 200,000 🪙\n💰 x2 выигрыши\n{'✅ Активен' if user['vip'] else '❌'}", reply_markup=InlineKeyboardMarkup(kb))
    
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
        txt = f"⚙️ Админ\n\n👥 {len(DB)} чел.\n💰 {sum(u['balance'] for u in DB.values()):,} 🪙"
        kb = [[InlineKeyboardButton("👥 Список", callback_data="au")], [InlineKeyboardButton("💰 Выдать", callback_data="ag")], [InlineKeyboardButton("🔄 Сброс", callback_data="ar")], [InlineKeyboardButton("📢 Рассылка", callback_data="as")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
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
        kb = [[InlineKeyboardButton("👤 Профиль", callback_data="p")], [InlineKeyboardButton("🎰 Казино", callback_data="c")], [InlineKeyboardButton("⛏ Майнинг", callback_data="m")], [InlineKeyboardButton("🎁 Кейсы", callback_data="cs")], [InlineKeyboardButton("🛍 Магазин", callback_data="s")], [InlineKeyboardButton("🎁 Бонус", callback_data="d")], [InlineKeyboardButton("🏆 Топ", callback_data="t")]]
        if admin:
            kb.append([InlineKeyboardButton("⚙️ Админ", callback_data="a")])
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
    user["exp"] = user.get("exp", 0) + random.randint(5, 50)
    if win > 0:
        user["earned"] += win - bet
    else:
        user["lost"] += bet
    user["current_game"] = None
    save_db()
    
    await update.message.reply_text(f"{msg}\n💰 {user['balance']:,} 🪙", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Играть", callback_data="c")], [InlineKeyboardButton("↩️ Меню", callback_data="mn")]]))

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
