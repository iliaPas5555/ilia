import os
import logging

from dotenv import load_dotenv
from anthropic import Anthropic
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# История переписки по chat_id, хранится в памяти (сбрасывается при рестарте бота)
history: dict[int, list[dict]] = {}
MAX_HISTORY_MESSAGES = 20


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Пиши сюда задачу — перешлю в Claude и пришлю ответ в этот же чат.\n"
        "/reset — очистить контекст переписки."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history.pop(update.effective_chat.id, None)
    await update.message.reply_text("Контекст очищен.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text

    messages = history.get(chat_id, [])
    messages.append({"role": "user", "content": user_text})

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=messages,
        )
        answer = response.content[0].text
    except Exception as e:
        logger.exception("Claude API error")
        await update.message.reply_text(f"Ошибка при обращении к Claude: {e}")
        return

    messages.append({"role": "assistant", "content": answer})
    history[chat_id] = messages[-MAX_HISTORY_MESSAGES:]

    # Telegram режет сообщения длиннее 4096 символов
    for i in range(0, len(answer), 4000):
        await update.message.reply_text(answer[i : i + 4000])


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
