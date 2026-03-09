import os
import sqlite3
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
import pytz
import asyncio

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DB_PATH = "/app/memory.db"
OWNER_ID = 1023383754
KST = pytz.timezone("Asia/Seoul")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  role TEXT,
                  content TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_history(user_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT role, content FROM messages 
                 WHERE user_id = ? 
                 ORDER BY id DESC LIMIT ?''', (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)',
              (user_id, role, content))
    conn.commit()
    conn.close()

def clear_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

async def send_news_briefing(bot):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": "오늘 주요 국제뉴스 3가지를 요약하고 향후 전망을 간단히 알려줘. 총 5줄 이내로."}]
    )
    await bot.send_message(chat_id=OWNER_ID, text="🌍 오늘의 국제뉴스\n\n" + response.content[0].text)

async def send_economy_briefing(bot):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": "이번 주 주요 경제 상황 요약과 주목할 주식 2-3개 추천해줘. 5줄 이내로."}]
    )
    await bot.send_message(chat_id=OWNER_ID, text="📈 이번 주 경제 브리핑\n\n" + response.content[0].text)

async def send_english_study(bot):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": "영어 단어 5개와 관용구 2개를 알려줘. 각각 한국어 뜻과 예문 한 줄씩 포함해줘."}]
    )
    await bot.send_message(chat_id=OWNER_ID, text="📚 오늘의 영어 공부\n\n" + response.content[0].text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("안녕하세요!\n\n매일 9시 국제뉴스, 월요일 11시 경제브리핑, 매일 12:30 영어공부를 보내드려요.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    clear_history(user_id)
    await update.message.reply_text("대화 기록을 초기화했습니다.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text

    save_message(user_id, "user", user_message)
    history = get_history(user_id)

    try:
        await update.message.chat.send_action("typing")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="당신은 황유택의 AI 어시스턴트입니다. 핵심만 간결하게 답하세요.",
            messages=history
        )
        assistant_message = response.content[0].text
        save_message(user_id, "assistant", assistant_message)
        await update.message.reply_text(assistant_message)
    except Exception as e:
        await update.message.reply_text(f"오류: {str(e)}")

async def post_init(app):
    await app.bot.send_message(chat_id=OWNER_ID, text="봇 시작! 루틴 알림 준비됐어요 🎉")
    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(send_news_briefing, CronTrigger(hour=9, minute=0, timezone=KST), args=[app.bot])
    scheduler.add_job(send_economy_briefing, CronTrigger(day_of_week="mon", hour=11, minute=0, timezone=KST), args=[app.bot])
    scheduler.add_job(send_english_study, CronTrigger(hour=12, minute=30, timezone=KST), args=[app.bot])
    scheduler.start()

def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("봇 시작!")
    app.run_polling()

if __name__ == "__main__":
    main()
