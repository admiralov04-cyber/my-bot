import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import datetime
import random

# --- НАСТРОЙКИ ---
DB_NAME = "casino.db"
DAILY_START = 10_000
DAILY_INCREMENT = 10_000


# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Основная таблица пользователей
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 10000,
            last_daily DATE -- Дата последнего получения бонуса
        )
    """
    )

    # Таблица магазина предметов
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shop (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER,
            description TEXT
        )
    """
    )

    # Заполним магазин базовыми предметами, если он пуст
    cursor.execute("SELECT COUNT(*) FROM shop")
    if cursor.fetchone()[0] == 0:
        items = [
            ("Счастливая монета", 50_000, "🎲 Увеличивает шанс выигрыша"),
            ("Удвоитель опыта", 75_000, "💸 Временное удвоение всех выигрышей"),
            ("VIP-статус", 200_000, "🔑 Открывает эксклюзивные игры"),
        ]
        cursor.executemany(
            'INSERT INTO shop (name, price, description) VALUES (?, ?, ?)', items
        )

    conn.commit()
    conn.close()


async def get_user(update: Update):
    """Получаем данные пользователя из базы"""
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Регистрируем нового игрока, если его нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username),
    )
    conn.commit()

    # Получаем баланс и дату бонуса
    cursor.execute("SELECT balance, last_daily FROM users WHERE user_id = ?", (user.id,))
    data = cursor.fetchone() or (None, None)
    conn.close()
    return {"balance": data[0], "last_daily": data[1]}


async def save_balance(user_id: int, amount: int):
    """Сохраняем баланс пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


# --- КОМАНДЫ И МЕНЮ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками"""
    user_data = await get_user(update)
    keyboard = [
        [InlineKeyboardButton(f"💰 Баланс: {user_data['balance']:,} 🪙", callback_data="balance")],
        [InlineKeyboardButton(emoji.emojize(":game_die: Казино"), callback_data="casino")],
        [InlineKeyboardButton(emoji.emojize(":shopping_cart: Магазин"), callback_data="shop")],
        [InlineKeyboardButton(emoji.emojize(":calendar: Ежедневный бонус"), callback_data="daily")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{update.effective_user.first_name}*!\nВыбери действие:"
    try:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        print(e)


# --- ОБРАБОТЧИК КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие

    match query.data:
        case "mainmenu":
            await main_menu_from_callback(query)

        case "balance":
            user_data = await get_user(update)
            await query.edit_message_text(
                text=f"Твой текущий баланс: *{user_data['balance']:,}* 🪙",
                parse_mode="Markdown",
            )

        case "daily":
            await daily(query, context)

        case "shop":
            await show_shop(query, context)

        case "casino":
            casino_keyboard = [
                [
                    InlineKeyboardButton(
                        emoji.emojize(":money_with_wings: Орел / Решка"),
                        callback_data="coin_flip",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        emoji.emojize(":game_dice: Кости"), callback_data="dice_roll"
                    ),
                ],
                [
                    InlineKeyboardButton(  # ❗️ Вот здесь мы добавили кнопку Отмены!
                        emoji.emojize(":back_arrow: Назад"), callback_data="cancel"
                    )
                ],
            ]
            await query.edit_message_text(
                text="*Выберите игру:*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(casino_keyboard),
            )

        case "coin_flip" | "dice_roll":
            game_name = {
                "coin_flip": "Орел / Решка",
                "dice_roll": "Кости",
            }[query.data]

            msg = f"Введите сумму ставки для игры \"*{game_name}*\":\n\n" f"Текущий баланс: *{(await get_user(update))['balance']:,}* 🪙"
            await query.edit_message_text(msg, parse_mode="Markdown")
            # Сохраняем выбранную игру в контекст, чтобы потом её обработать
            context.user_data["selected_game"] = query.data

        case "cancel":
            await cancel_bet(update, context)


async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасываем выбор игры."""
    query = update.callback_query
    await query.answer()

    if "selected_game" in context.user_data:
        del context.user_data["selected_game"]

    await main_menu_from_callback(query)


# --- ЛИДЕРЫ И ЕЖЕДНЕВНЫЙ БОНУС ---

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    msg = "🏆 Топ самых богатых игроков:\n"
    for i, (username, bal) in enumerate(leaders, 1):
        name = username or "Аноним"
        msg += f"{i}. {name}: {bal:,} 🪙\n"
    await update.message.reply_text(msg)


async def daily(query, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    user = query.from_user

    user_data = await get_user(update=query)
    last_date_str = user_data["last_daily"]

    # ⚠️ Фикс ошибки: раньше не работало при первом заходе (пустая дата)
    if not last_date_str:
        days_passed = 1
    else:
        last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
        days_passed = (today - last_date).days

    if days_passed < 1:
        await query.edit_message_text("❌ Вы уже забирали бонус сегодня.")
        return

    bonus = DAILY_START + max(DAILY_INCREMENT * (days_passed - 1), 0)
    new_balance = user_data["balance"] + bonus

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?",
        (new_balance, today.isoformat(), user.id),
    )
    conn.commit()
    conn.close()

    await query.edit_message_text(
        f"✅ Успех! Вы забрали бонус за {days_passed} день/дня: *{bonus:,}* 🪙.\nНовый баланс: *{new_balance:,}* 🪙",
        parse_mode="Markdown",
    )


# --- ПОКАЗАТЬ МАГАЗИН ---

async def show_shop(query, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Собираем кнопки товаров
    buttons = []
    for row in cur.execute("SELECT item_id, name, price FROM shop"):
        item_id, name, price = row
        buttons.append([InlineKeyboardButton(name, callback_data=f"buy_{item_id}")])

    # Добавляем кнопку возврата
    buttons.append(
        [InlineKeyboardButton(emoji.emojize(":back_arrow: Назад"), callback_data="mainmenu")]
    )

    # Формируем текст со списком товаров
    text = "*🛒 Добро пожаловать в магазин:*\n"
    for name, price, desc in cur.execute("SELECT name, price, description FROM shop"):
        text += f"\n• {name}\nЦена: {price:,} 🪙\n{desc}"

    conn.close()

    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# --- ИГРОПРОВОДНИК —

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает текстовое сообщение со ставкой после того, как игрок выбрал игру.
    """
    # Проверим, есть ли у нас сохранённая игра
    selected_game = context.user_data.get("selected_game")
    if not selected_game:
        return

    bet_text = update.message.text.replace(",", "").replace(" ", "")
    try:
        bet = int(bet_text)
    except ValueError:
        # Игнорируем всё, кроме чисел
        return

    if bet <= 0:
        await update.message.reply_text("Ставка должна быть больше нуля.")
        return

    user_data = await get_user(update)
    if bet > user_data["balance"]:
        await update.message.reply_text("❌ Недостаточно средств на балансе.")
        return

    result_msg = ""
    win_amount = 0

    # Логика игр
    if selected_game == "coin_flip":
        choice = random.choice(["орёл", "решка"])
        coin = random.choice(["орёл", "решка"])
        won = choice == coin
        multiplier = 1.95

        result_msg = f"🎲 Выпал *{coin}*."
        if won:
            win_amount = int(bet * multiplier)
            result_msg += " Ваша ставка сыграла!"
        else:
            result_msg += " Попробуйте еще раз."

    elif selected_game == "dice_roll":
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        total = dice1 + dice2

        # Простая механика: чётное выигрывает x2, нечётное проигрыш
        if total % 2 == 0:
            win_amount = bet * 2
            result_msg = f"🎲 Выпало {dice1} + {dice2} = *{total}* (Чет). Победа!"
        else:
            result_msg = f"🎲 Выпало {dice1} + {dice2} = *{total}* (Нечет). Проигрыш."

    # Считаем новый баланс
    new_balance = user_data["balance"] + win_amount - bet

    await save_balance(update.effective_user.id, new_balance)

    summary = (
        f"{result_msg}\n\n{'+' if win_amount > 0 else '-'}{abs(win_amount - bet):,} 🪙\nВаш новый баланс: *{new_balance:,}* 🪙"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")

    # Очищаем контекст, чтобы следующая цифра не была воспринята как ставка
    del context.user_data["selected_game"]


# Вспомогательные функции
async def main_menu_from_callback(query):
    """Показать главное меню из коллбека (без message object)"""
    user_data = await get_user(update=query)
    keyboard = [
        [InlineKeyboardButton(f"💰 Баланс: {user_data['balance']:,} 🪙", callback_data="balance")],
        [InlineKeyboardButton(emoji.emojize(":game_die: Казино"), callback_data="casino")],
        [InlineKeyboardButton(emoji.emojize(":shopping_cart: Магазин"), callback_data="shop")],
        [InlineKeyboardButton(emoji.emojize(":calendar: Ежедневный бонус"), callback_data="daily")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Привет, *{query.from_user.first_name}*!\nВыбери действие:"
    await query.edit_message_text(
        text=text, parse_mode="Markdown", reply_markup=reply_markup
    )


# ✍️ Кастомный фильтр для ввода суммы
def game_input_filter(_: Update, ctx: ContextTypes.DEFAULT_TYPE | None = None) -> bool:
    """Реагирует только на сообщения-цифры от пользователя в приватном чате, когда выбрана игра."""
    return (
        ctx is not None
        and ctx.user_data.get("selected_game") is not None
        and _.message is not None
        and _.effective_chat.type == "private"
        and _.message.text.isdigit()
    )


if __name__ == "__main__":
    init_db()

    app = ApplicationBuilder().token("API_TOKEN").build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))  # Оставил команду топа

    # Главный обработчик ВСЕХ inline-кнопок
    app.add_handler(CallbackQueryHandler(button_handler))

    # Этот обработчик сработает ТОЛЬКО тогда, когда пользователь ввёл цифру после выбора игры
    app.add_handler(MessageHandler(game_input_filter, process_bet), group=0)

    print("Бот запущен...")
    app.run_polling(drop_pending_updates=True)
    
