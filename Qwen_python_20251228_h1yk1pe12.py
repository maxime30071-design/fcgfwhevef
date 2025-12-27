import os
import subprocess
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# === CONFIG ===
HOSTING_BOT_TOKEN = "8560105826:AAHgVX9eZgwiZgL1crf3K2CCemq8F7lIaYA"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOTS_DIR = os.path.join(BASE_DIR, "bots")
os.makedirs(BOTS_DIR, exist_ok=True)

# Состояния диалога
TOKEN, BOT_CODE, REQUIREMENTS = range(3)

# === ФУНКЦИИ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("Привет! Отправь токен твоего Telegram-бота (от @BotFather):")
    return TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    if len(token) < 10 or ':' not in token:
        await update.message.reply_text("❌ Неверный формат токена. Попробуй ещё раз:")
        return TOKEN
    context.user_data["bot_token"] = token
    await update.message.reply_text("Отлично! Теперь отправь файл `bot.py` (с кодом твоего бота):")
    return BOT_CODE

async def receive_bot_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document or update.message.document.file_name != "bot.py":
        await update.message.reply_text("Пожалуйста, отправь именно файл с именем `bot.py`.")
        return BOT_CODE

    bot_dir = os.path.join(BOTS_DIR, str(update.effective_user.id))
    os.makedirs(bot_dir, exist_ok=True)
    file = await update.message.document.get_file()
    await file.download_to_drive(os.path.join(bot_dir, "bot.py"))
    await update.message.reply_text("Принято! Теперь отправь `requirements.txt`:")
    return REQUIREMENTS

async def receive_requirements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document or update.message.document.file_name != "requirements.txt":
        await update.message.reply_text("Пожалуйста, отправь именно файл с именем `requirements.txt`.")
        return REQUIREMENTS

    user_id = update.effective_user.id
    bot_dir = os.path.join(BOTS_DIR, str(user_id))
    file = await update.message.document.get_file()
    await file.download_to_drive(os.path.join(bot_dir, "requirements.txt"))

    # Сохраняем токен в .env или через env
    with open(os.path.join(bot_dir, ".env"), "w") as f:
        f.write(f"BOT_TOKEN={context.user_data['bot_token']}")

    await update.message.reply_text("Все файлы получены! Запускаю бота...")

    success = setup_and_run_bot(bot_dir, context.user_data["bot_token"])
    if success:
        await update.message.reply_text("🟢 Бот успешно запущен! Проверь его в Telegram.")
    else:
        await update.message.reply_text("🔴 Ошибка при запуске. Проверь логи.")

    return ConversationHandler.END

def setup_and_run_bot(bot_dir: str, bot_token: str) -> bool:
    try:
        venv_dir = os.path.join(bot_dir, "venv")
        if not os.path.exists(venv_dir):
            subprocess.run(["python3", "-m", "venv", venv_dir], check=True)

        pip = os.path.join(venv_dir, "bin", "pip")
        python = os.path.join(venv_dir, "bin", "python")

        # Установка зависимостей
        subprocess.run([pip, "install", "-r", os.path.join(bot_dir, "requirements.txt")], check=True)
        subprocess.run([pip, "install", "python-dotenv"], check=True)  # для .env

        # Запуск в фоне
        log_file = os.path.join(bot_dir, "bot.log")
        env = os.environ.copy()
        env["BOT_TOKEN"] = bot_token

        with open(log_file, "w") as log:
            subprocess.Popen(
                [python, os.path.join(bot_dir, "bot.py")],
                cwd=bot_dir,
                stdout=log,
                stderr=log,
                env=env
            )
        return True
    except Exception as e:
        logging.exception("Ошибка в setup_and_run_bot")
        with open(os.path.join(bot_dir, "error.log"), "w") as f:
            f.write(str(e))
        return False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

# === MAIN ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    app = Application.builder().token(HOSTING_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            BOT_CODE: [MessageHandler(filters.Document.ALL, receive_bot_code)],
            REQUIREMENTS: [MessageHandler(filters.Document.ALL, receive_requirements)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    print("🚀 Хостинг-бот запущен!")
    app.run_polling()