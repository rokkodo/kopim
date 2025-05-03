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
        "/setlimit [категория] [сумма]
