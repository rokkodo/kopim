import os
import sqlite3
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Укажи ваши Telegram ID
ALLOWED_USERS = [1241046646, 259679740]  # ← замени на свои и Даши ID

# Лимиты при запуске
LIMITS = {
    "еда": (150, "week"),
    "даша": (200, "month"),
    "рома": (200, "month"),
    "кофе": (150, "month")
}

# База данных
conn = sqlite3.connect("expenses.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY, chat_id INTEGER, user TEXT, category TEXT, amount REAL, timestamp DATE)")
cursor.execute("CREATE TABLE IF NOT EXISTS limits (category TEXT PRIMARY KEY, amount REAL, period TEXT)")
conn.commit()

for cat, (amount, period) in LIMITS.items():
    cursor.execute("INSERT OR REPLACE INTO limits (category, amount, period) VALUES (?, ?, ?)", (cat, amount, period))
conn.commit()

def get_start_date(period):
    today = datetime.date.today()
    return today - datetime.timedelta(days=today.weekday()) if period == "week" else today.replace(day=1)

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def get_all_categories():
    cursor.execute("SELECT DISTINCT category FROM expenses")
    e = {r[0] for r in cursor.fetchall()}
    cursor.execute("SELECT DISTINCT category FROM limits")
    l = {r[0] for r in cursor.fetchall()}
    return sorted(e.union(l))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    msg = (
        "📋 Команды:\n"
        "/balance — Остатки по лимитам\n"
        "/limits — Текущие лимиты\n"
        "/setlimit [категория] [сумма] [week|month] — установить лимит\n"
        "/resetlimit [категория] — удалить лимит\n"
        "/categories — список всех категорий\n"
        "/renamecategory [старое] [новое] — переименовать\n"
        "/deletecategory [категория] — удалить категорию с данными\n"
        "/help — показать команды\n"
        "Также можно писать: еда 25"
    )
    await update.message.reply_text(msg)

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    text = update.message.text.strip().lower()
    parts = text.split()
    if len(parts) != 2: return
    category, amount = parts
    try:
        amount = float(amount)
    except ValueError:
        return
    user = update.effective_user.first_name or "пользователь"
    chat_id = update.effective_chat.id
    today = datetime.date.today()
    cursor.execute("INSERT INTO expenses (chat_id, user, category, amount, timestamp) VALUES (?, ?, ?, ?, ?)", (chat_id, user, category, amount, today))
    conn.commit()
    await update.message.reply_text(f"{user} добавил {amount} € в категорию '{category}'.")

async def show_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    chat_id = update.effective_chat.id
    msg = "💰 Остатки по категориям:\n"
    cursor.execute("SELECT * FROM limits")
    limits = cursor.fetchall()
    for cat, limit, period in limits:
        start = get_start_date(period)
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE chat_id = ? AND category = ? AND timestamp >= ?", (chat_id, cat, start))
        spent = cursor.fetchone()[0] or 0
        remaining = limit - spent
        msg += f"{cat.title()}: {spent:.2f} € / {limit} € ({period}) → остаток: {remaining:.2f} €\n"
    await update.message.reply_text(msg)

async def show_all_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    cursor.execute("SELECT category, amount, period FROM limits")
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Лимиты пока не заданы.")
        return
    msg = "🔒 Текущие лимиты:\n"
    for cat, amount, period in rows:
        msg += f"{cat.title()}: {amount} € / {period}\n"
    await update.message.reply_text(msg)

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    args = [a.lower() for a in context.args]
    if len(args) != 3:
        await update.message.reply_text("Формат: /setlimit категория сумма период")
        return
    category, amount, period = args
    try:
        amount = float(amount)
        if period not in ("week", "month"):
            raise ValueError()
    except:
        await update.message.reply_text("Ошибка: проверь сумму и период (week/month).")
        return
    cursor.execute("INSERT OR REPLACE INTO limits (category, amount, period) VALUES (?, ?, ?)", (category, amount, period))
    conn.commit()
    await update.message.reply_text(f"Лимит для '{category}' установлен: {amount} € / {period}")

async def reset_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    if len(context.args) != 1:
        await update.message.reply_text("Формат: /resetlimit категория")
        return
    category = context.args[0].lower()
    cursor.execute("DELETE FROM limits WHERE category = ?", (category,))
    conn.commit()
    await update.message.reply_text(f"Лимит для '{category}' удалён.")

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    cats = get_all_categories()
    msg = "📂 Все категории:\n" + "\n".join(sorted(cats)) if cats else "Категорий пока нет."
    await update.message.reply_text(msg)

async def rename_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    if len(context.args) != 2:
        await update.message.reply_text("Формат: /renamecategory старое новое")
        return
    old, new = [a.lower() for a in context.args]
    cursor.execute("UPDATE expenses SET category = ? WHERE category = ?", (new, old))
    cursor.execute("UPDATE limits SET category = ? WHERE category = ?", (new, old))
    conn.commit()
    await update.message.reply_text(f"Категория '{old}' переименована в '{new}'.")

async def delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    if len(context.args) != 1:
        await update.message.reply_text("Формат: /deletecategory категория")
        return
    category = context.args[0].lower()
    cursor.execute("DELETE FROM expenses WHERE category = ?", (category,))
    cursor.execute("DELETE FROM limits WHERE category = ?", (category,))
    conn.commit()
    await update.message.reply_text(f"Категория '{category}' удалена.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)

def main():
    TOKEN = os.getenv("TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", show_limits))
    app.add_handler(CommandHandler("limits", show_all_limits))
    app.add_handler(CommandHandler("setlimit", set_limit))
    app.add_handler(CommandHandler("resetlimit", reset_limit))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CommandHandler("renamecategory", rename_category))
    app.add_handler(CommandHandler("deletecategory", delete_category))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense))

    app.run_polling()

if __name__ == "__main__":
    main()
