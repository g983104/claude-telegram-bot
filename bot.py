import os
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# 대화 히스토리 저장 (유저별)
conversation_history = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "안녕하세요! Claude입니다. 무엇이든 물어보세요."
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conversation_history[user_id] = []
    await update.message.reply_text("대화 기록을 초기화했습니다.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text

    # 유저별 히스토리 초기화
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # 히스토리에 추가
    conversation_history[user_id].append({
        "role": "user",
        "content": user_message
    })

    # 히스토리 최대 20개 유지
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

    try:
        # 타이핑 표시
        await update.message.chat.send_action("typing")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system="당신은 황유택의 AI 어시스턴트입니다. 예술단체 낯선사람(The Stranger)의 대표이자 연출가, 기획자, 크리에이티브 디렉터인 황유택을 돕습니다. 명료하고 위트 있게, 핵심을 짚는 방식으로 대화하세요.",
            messages=conversation_history[user_id]
        )

        assistant_message = response.content[0].text

        # 히스토리에 응답 추가
        conversation_history[user_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        await update.message.reply_text(assistant_message)

    except Exception as e:
        await update.message.reply_text(f"오류가 발생했습니다: {str(e)}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("봇 시작!")
    app.run_polling()

if __name__ == "__main__":
    main()
