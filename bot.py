import os
import sqlite3
import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Категории и лимиты
LIMITS = {
    "еда": (150, "week"),
    "даша": (200, "month"),
    "рома": (200, "month"),
    "кофе": (150, "month")
}
CATEGORIES = ["еда", "даша", "рома", "машина", "подарки", "рестораны", "кофе", "дом", "земля", "другое"]

# Инициализация базы
conn = sqlite3.connect("expenses.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    user TEXT,
    category TEXT,
    amount REAL,
    timestamp DATE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS limits (
    category TEXT PRIMARY KEY,
    amount REAL,
    period TEXT
)
""")
conn.commit()

for cat, (amount, period) in LIMITS.items():
    cursor.execute("INSERT OR REPLACE INTO limits (category, amount, period) VALUES (?, ?, ?)", (cat, amount, period))
conn.commit()

def get_start_date(period):
    today = datetime.date.today()
    if period == "week":
        return today - datetime.timedelta(days=today.weekday())
    elif period == "month":
        return today.replace(day=1)
    return today

def add_expense(update, context):
    text = update.message.text.strip().lower()
    parts = text.split()
    if len(parts) != 2:
        return
    category, amount = parts
    if category not in CATEGORIES:
        return
    try:
        amount = float(amount)
    except ValueError:
        return

    user = update.message.from_user.first_name or "пользователь"
    chat_id = update.message.chat_id
    today = datetime.date.today()

    cursor.execute("INSERT INTO expenses (chat_id, user, category, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (chat_id, user, category, amount, today))
    conn.commit()
    update.message.reply_text(f"{user} добавил {amount} € в категорию '{category}'.")

def show_limits(update, context):
    chat_id = update.message.chat_id
    msg = "Остатки по категориям:\n"

    cursor.execute("SELECT * FROM limits")
    limits = cursor.fetchall()
    for cat, limit, period in limits:
        start_date = get_start_date(period)
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE chat_id = ? AND category = ? AND timestamp >= ?
        """, (chat_id, cat, start_date))
        spent = cursor.fetchone()[0] or 0
        remaining = limit - spent
        msg += f"{cat.title()}: потрачено {spent:.2f} € / лимит {limit} € ({period}) → остаток {remaining:.2f} €\n"

    update.message.reply_text(msg)

def show_all_limits(update, context):
    cursor.execute("SELECT category, amount, period FROM limits")
    rows = cursor.fetchall()
    if not rows:
        update.message.reply_text("Лимиты пока не заданы.")
        return
    msg = "Текущие лимиты:\n"
    for cat, amount, period in rows:
        msg += f"{cat.title()}: {amount} € / {period}\n"
    update.message.reply_text(msg)

def set_limit(update, context):
    args = context.args
    if len(args) != 3:
        update.message.reply_text("Формат: /лимит категория сумма период(week/month)")
        return

    category, amount, period = args
    category = category.lower()
    if category not in CATEGORIES:
        update.message.reply_text("Неизвестная категория.")
        return
    try:
        amount = float(amount)
        if period not in ("week", "month"):
            raise ValueError()
    except:
        update.message.reply_text("Формат: /лимит категория сумма период(week/month)")
        return

    cursor.execute("INSERT OR REPLACE INTO limits (category, amount, period) VALUES (?, ?, ?)",
                   (category, amount, period))
    conn.commit()
    update.message.reply_text(f"Лимит для '{category}' установлен: {amount} € / {period}")

def main():
    TOKEN = os.getenv("TOKEN")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("остаток", show_limits))
    dp.add_handler(CommandHandler("лимиты", show_all_limits))
    dp.add_handler(CommandHandler("лимит", set_limit, pass_args=True))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, add_expense))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
