import os
import sqlite3
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
import pytz

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

async def send_morning_briefing(app):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system="당신은 황유택의 AI 어시스턴트입니다. 핵심만 간결하게 답하세요.",
        messages=[{"role": "user", "content": "오늘 하루를 시작하는 간단한 아침 인사와 오늘 집중할 것들을 체크해볼 수 있는 짧은 메시지를 보내줘. 3줄 이내로."}]
    )
    message = response.content[0].text
    await app.bot.send_message(chat_id=OWNER_ID, text=f"좋은 아침이에요!\n\n{message}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("안녕하세요! 무엇이든 물어보세요.\n\n매일 오전 9시에 아침 브리핑을 보내드려요.")

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

def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 스케줄러 설정 - 매일 오전 9시 (한국 시간)
    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=9, minute=0, timezone=KST),
        args=[app]
    )
    scheduler.start()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("봇 시작!")
    app.run_polling()

if __name__ == "__main__":
    main()
