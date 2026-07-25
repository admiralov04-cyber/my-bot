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
DATA_FILE = "data.json"
DAILY_START = 10000

# Глобальное хранилище данных (чтобы не терять при перезапуске)
users_data = {}
last_save_time = None

# Загрузка данных
def load_data():
    global users_data
    try:
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    users_data = json.loads(content)
                    print(f"✅ Загружено пользователей: {len(users_data)}")
                    return
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
    
    # Если файл пустой или не существует
    users_data = {}
    print("📄 Создана новая база данных")

# Сохранение данных
def save_data():
    global users_data, last_save_time
    try:
        # Сохраняем в файл
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        last_save_time = datetime.datetime.now()
        print(f"💾 Данные сохранены! Пользователей: {len(users_data)}")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        
        # Пробуем сохранить в альтернативный файл
        try:
            with open("backup_data.json", 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            print("💾 Сохранено в backup_data.json")
        except:
            print("❌ Полная ошибка сохранения!")

# Получить пользователя
def get_user(user_id, username=None):
    global users_data
    user_id = str(user_id)
    
    if user_id not in users_data:
        users_data[user_id] = {
            "username": username or f"Player{user_id[:6]}",
            "balance": 10000,
            "last_daily": None,
            "current_game": None,
            "business": False,
            "mining_farm": False,
            "vip": False,
            "register_date": datetime.date.today().isoformat(),
            "total_earned": 0,
            "total_lost": 0
        }
        save_data()
        print(f"👤 Новый пользователь: {user_id}")
    elif username and users_data[user_id].get("username") != username:
        users_data[user_id]["username"] = username
        save_data()
    
    return users_data[user_id]

# Получить позицию в топе
def get_top_position(user_id):
    user_id = str(user_id)
    if not users_data:
        return 1, 1
    
    sorted_users = sorted(
        users_data.items(),
        key=lambda x: x[1]["balance"],
        reverse=True
    )
    for i, (uid, _) in enumerate(sorted_users, 1):
        if uid == user_id:
            return i, len(sorted_users)
    return len(sorted_users) + 1, len(sorted_users) + 1

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
        [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user = update.effective_user
    text = f"🎰 *Казино-Бот*\n\nПривет, *{user.first_name}*!\nВыбери действие:"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    username = query.from_user.username or query.from_user.first_name
    user = get_user(user_id, username)
    
    # Профиль
    if query.data == "profile":
        top_pos, total = get_top_position(user_id)
        reg_date = user.get("register_date", "Неизвестно")
        
        business_status = "✅ Есть (+5000/час)" if user.get("business") else "❌ Нет"
        mining_status = "✅ Есть (+2000/час)" if user.get("mining_farm") else "❌ Нет"
        vip_status = "👑 VIP" if user.get("vip") else "⭐ Обычный"
        
        profile_text = (
            f"👤 *Профиль игрока*\n\n"
            f"📛 *Имя:* `{user['username']}`\n"
            f"🆔 *ID:* `{user_id}`\n\n"
            f"💰 *Баланс:* `{user['balance']:,}` 🪙\n"
            f"📅 *Регистрация:* `{reg_date}`\n"
            f"🏆 *Топ:* `{top_pos}` из `{total}`\n\n"
            f"🏪 *Бизнес:* {business_status}\n"
            f"⛏ *Майнинг ферма:* {mining_status}\n"
            f"💎 *Статус:* {vip_status}\n\n"
            f"📊 *Статистика:*\n"
            f"💚 Заработано: `{user.get('total_earned', 0):,}` 🪙\n"
            f"💔 Проиграно: `{user.get('total_lost', 0):,}` 🪙"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="profile")],
            [InlineKeyboardButton("↩️ Назад", callback_data="back")]
        ]
        await query.edit_message_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Казино
    elif query.data == "casino":
        keyboard = [
            [InlineKeyboardButton("🪙 Орел/Решка (x2)", callback_data="coin")],
            [InlineKeyboardButton("🎲 Кости (x2)", callback_data="dice")],
            [InlineKeyboardButton("🎰 Слоты (x5)", callback_data="slots")],
            [InlineKeyboardButton("↩️ Назад", callback_data="back")],
        ]
        await query.edit_message_text(
            "🎰 *Казино*\n\n💰 Ваш баланс: `{:,}` 🪙\n\n*Выберите игру:*".format(user['balance']),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Выбор игры
    elif query.data in ["coin", "dice", "slots"]:
        game_names = {
            "coin": "Орел/Решка (x2)",
            "dice": "Кости (x2)",
            "slots": "Слоты (x5)"
        }
        game_name = game_names[query.data]
        user["current_game"] = query.data
        save_data()
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
        await query.edit_message_text(
            f"🎮 *{game_name}*\n\n💰 Баланс: `{user['balance']:,}` 🪙\n\n✏️ *Введите ставку числом:*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Отмена ставки
    elif query.data == "cancel":
        user["current_game"] = None
        save_data()
        
        keyboard = [
            [InlineKeyboardButton("🎲 В казино", callback_data="casino")],
            [InlineKeyboardButton("↩️ Меню", callback_data="back")]
        ]
        await query.edit_message_text(
            "❌ Ставка отменена",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Ежедневный бонус
    elif query.data == "daily":
        today = datetime.date.today().isoformat()
        
        if user.get("last_daily") != today:
            bonus = DAILY_START
            
            # Бонусы от бизнеса и фермы
            if user.get("business"):
                bonus += 5000
            if user.get("mining_farm"):
                bonus += 2000
            if user.get("vip"):
                bonus *= 2
            
            user["balance"] += bonus
            user["last_daily"] = today
            user["total_earned"] = user.get("total_earned", 0) + bonus
            save_data()
            
            bonus_parts = []
            bonus_parts.append(f"🎁 Базовый: +{DAILY_START:,}")
            if user.get("business"):
                bonus_parts.append(f"🏪 Бизнес: +5,000")
            if user.get("mining_farm"):
                bonus_parts.append(f"⛏ Майнинг: +2,000")
            if user.get("vip"):
                bonus_parts.append(f"💎 VIP x2")
            
            bonus_text = "\n".join(bonus_parts)
            
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            await query.edit_message_text(
                f"✅ *Бонус получен!*\n\n{bonus_text}\n\n🎁 Итого: `+{bonus:,}` 🪙\n💰 Баланс: `{user['balance']:,}` 🪙",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("↩️ Меню", callback_data="back")]]
            
            # Показываем время до следующего бонуса
            now = datetime.datetime.now()
            tomorrow = now + datetime.timedelta(days=1)
            tomorrow = tomorrow.replace(hour=0, minute=0, second=0)
            time_left = tomorrow - now
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            
            await query.edit_message_text(
                f"❌ *Бонус уже получен!*\n\n⏰ Следующий через: `{hours}ч {minutes}мин`",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # Топ
    elif query.data == "top":
        sorted_users = sorted(
            users_data.items(),
            key=lambda x: x[1]["balance"],
            reverse=True
        )[:10]
        
        msg = "🏆 *Топ-10 игроков:*\n\n"
        for i, (uid, u_data) in enumerate(sorted_users, 1):
            name = u_data.get("username", f"ID:{uid[:8]}")
            vip_icon = "👑 " if u_data.get("vip") else ""
            business_icon = "🏪" if u_data.get("business") else ""
            mining_icon = "⛏" if u_data.get("mining_farm") else ""
            
            msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '👤'} {i}. {vip_icon}{name} {business_icon}{mining_icon}: `{u_data['balance']:,}` 🪙\n"
        
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="back")]]
        await query.edit_message_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Назад в меню
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
            [InlineKeyboardButton("🎲 Казино", callback_data="casino")],
            [InlineKeyboardButton("🗓 Ежедневный бонус", callback_data="daily")],
            [InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
        ]
        await query.edit_message_text(
            "🎰 *Главное меню*\n\nВыбери действие:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Обработка сообщений (ставки)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or update.message.from_user.first_name
    user = get_user(user_id, username)
    
    if not user.get("current_game"):
        return
    
    try:
        bet = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите целое число!")
        return
    
    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше нуля!")
        return
    
    if bet > user["balance"]:
        await update.message.reply_text(
            f"❌ *Недостаточно средств!*\n💰 Баланс: `{user['balance']:,}` 🪙",
            parse_mode='Markdown'
        )
        return
    
    # Множитель для VIP
    vip_multiplier = 2 if user.get("vip") else 1
    
    # Игры
    if user["current_game"] == "coin":
        coin = random.choice(["орёл", "решка"])
        won = random.choice([True, False])
        if won:
            win = bet * 2 * vip_multiplier
            msg = f"🪙 Монетка: *{coin}*\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🪙 Монетка: *{coin}*\n❌ Проигрыш -{bet:,} 🪙"
    
    elif user["current_game"] == "dice":
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        if total % 2 == 0:
            win = bet * 2 * vip_multiplier
            msg = f"🎲 {d1}+{d2}=*{total}* (Чёт)\n✅ Победа! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🎲 {d1}+{d2}=*{total}* (Нечет)\n❌ Проигрыш -{bet:,} 🪙"
    
    elif user["current_game"] == "slots":
        # Слоты: три символа
        symbols = ["🍒", "🍋", "🍊", "7️⃣", "💎", "⭐"]
        s1, s2, s3 = random.choices(symbols, k=3)
        
        if s1 == s2 == s3:
            win = bet * 5 * vip_multiplier
            msg = f"🎰 {s1}{s2}{s3}\n🎉 *ДЖЕКПОТ!* +{win-bet:,} 🪙"
        elif s1 == s2 or s2 == s3 or s1 == s3:
            win = bet * 2 * vip_multiplier
            msg = f"🎰 {s1}{s2}{s3}\n✅ Две пары! +{win-bet:,} 🪙"
        else:
            win = 0
            msg = f"🎰 {s1}{s2}{s3}\n❌ Проигрыш -{bet:,} 🪙"
    
    # Обновляем баланс и статистику
    user["balance"] = user["balance"] - bet + win
    if win > 0:
        user["total_earned"] = user.get("total_earned", 0) + (win - bet)
    else:
        user["total_lost"] = user.get("total_lost", 0) + bet
    
    user["current_game"] = None
    save_data()
    
    keyboard = [
        [InlineKeyboardButton("🎲 Играть еще", callback_data="casino")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("↩️ Меню", callback_data="back")]
    ]
    
    vip_text = " (VIP x2)" if user.get("vip") and win > 0 else ""
    await update.message.reply_text(
        f"{msg}{vip_text}\n💰 Баланс: `{user['balance']:,}` 🪙",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команды
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(
        users_data.items(),
        key=lambda x: x[1]["balance"],
        reverse=True
    )[:10]
    
    msg = "🏆 *Топ-10 игроков:*\n\n"
    for i, (uid, u_data) in enumerate(sorted_users, 1):
        name = u_data.get("username", f"ID:{uid[:8]}")
        vip_icon = "👑 " if u_data.get("vip") else ""
        msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '👤'} {i}. {vip_icon}{name}: `{u_data['balance']:,}` 🪙\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name
    user = get_user(user_id, username)
    
    top_pos, total = get_top_position(user_id)
    
    business_status = "✅ Есть" if user.get("business") else "❌ Нет"
    mining_status = "✅ Есть" if user.get("mining_farm") else "❌ Нет"
    vip_status = "👑 VIP" if user.get("vip") else "⭐ Обычный"
    
    profile_text = (
        f"👤 *Профиль*\n\n"
        f"💰 Баланс: `{user['balance']:,}` 🪙\n"
        f"📅 Регистрация: `{user.get('register_date', 'Н/Д')}`\n"
        f"🏆 Топ: `{top_pos}` из `{total}`\n\n"
        f"🏪 Бизнес: {business_status}\n"
        f"⛏ Майнинг ферма: {mining_status}\n"
        f"💎 Статус: {vip_status}\n\n"
        f"💚 Заработано: `{user.get('total_earned', 0):,}` 🪙\n"
        f"💔 Проиграно: `{user.get('total_lost', 0):,}` 🪙"
    )
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name
    user = get_user(user_id, username)
    
    await update.message.reply_text(
        f"💰 *Ваш баланс:* `{user['balance']:,}` 🪙",
        parse_mode='Markdown'
    )

# Запуск
def main():
    print("🚀 Запуск бота...")
    
    # Загружаем данные
    load_data()
    
    # Если данных нет, создаем пустую базу
    if not users_data:
        save_data()
    
    print(f"📊 Загружено пользователей: {len(users_data)}")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("balance", balance_command))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен!")
    
    # Сохраняем данные перед запуском
    save_data()
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
