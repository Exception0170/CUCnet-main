import os
import json
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging
from config import NEWS_BOT_TOKEN, NEWS_JSON_FILE, NEWS_CHANNEL_ID, ADMIN_CHAT_ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# Load existing news
def load_news():
    if os.path.exists(NEWS_JSON_FILE):
        with open(NEWS_JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


# Save news to JSON
def save_news(news_list):
    with open(NEWS_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)


# Check if user is authorized
def is_authorized(chat_id):
    return chat_id == ADMIN_CHAT_ID


# Store message IDs for deletion
def save_message_id(news_id, message_id):
    news_list = load_news()
    for news in news_list:
        if news['id'] == news_id:
            news['channel_message_id'] = message_id
            break
    save_news(news_list)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized access.")
        return

    await update.message.reply_text(
        "Бот новостей CUCnet-а!\n"
        "Команды:\n"
        "/news - Добавить новость(Нужно ответить!)\n"
        "/list - Список новостей(да ладно0\n"
        "/delete <id> - Удалить новость по айдишнику(из канала тоже удалит дада)"
    )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Неавторизованный доступ!!! 403!!!.")
        return

    # Store that we're waiting for news input
    context.user_data['waiting_for_news'] = True
    await update.message.reply_text("Ответь сообещнием с новостью(Именно ответь):")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return

    if context.user_data.get('waiting_for_news'):
        # This is a news message
        news_text = update.message.text
        news_list = load_news()

        # Create news entry
        news_id = len(news_list) + 1
        news_entry = {
            "id": news_id,
            "text": news_text,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat()
        }

        news_list.append(news_entry)
        save_news(news_list)

        # Post to channel
        try:
            bot = Bot(token=NEWS_BOT_TOKEN)
            message = await bot.send_message(
                chat_id=NEWS_CHANNEL_ID,
                text=f"[{news_entry['date']}]: {news_text}"
            )
            # Save the channel message ID for future deletion
            save_message_id(news_id, message.message_id)

        except Exception as e:
            logging.error(f"Ошибка постинга в канал: {e}")

        context.user_data['waiting_for_news'] = False
        await update.message.reply_text(f"Новость успешно добавлена! ID: {news_id}")


async def list_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Неавторизованный доступ!! 403!!! get dunked on!")
        return

    news_list = load_news()

    if not news_list:
        await update.message.reply_text("Новостей нету.")
        return

    response = "📰 News List:\n\n"
    for news in news_list[-10:]:  # Show last 10 news
        response += f"ID: {news['id']}\n"
        response += f"Дата: {news['date']}\n"
        response += f"{news['text'][:100]}...\n"
        response += "─" * 30 + "\n"

    await update.message.reply_text(response)


async def delete_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Неавторизованный доступ!!! 403!!.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /delete <news_id>")
        return

    try:
        news_id = int(context.args[0])
        news_list = load_news()

        # Find news to delete
        news_to_delete = None
        for news in news_list:
            if news['id'] == news_id:
                news_to_delete = news
                break

        if not news_to_delete:
            await update.message.reply_text(f"Новость с ID {news_id} не найдена. 404!")
            return

        # Delete from channel if message ID exists
        if news_to_delete.get('channel_message_id'):
            try:
                bot = Bot(token=NEWS_BOT_TOKEN)
                await bot.delete_message(
                    chat_id=NEWS_CHANNEL_ID,
                    message_id=news_to_delete['channel_message_id']
                )
            except Exception as e:
                logging.error(f"Ошибка удаление новочтей с канала: {e}")
                await update.message.reply_text(f"Новость удалена но не с канала: {e}")

        # Remove from news list
        news_list = [news for news in news_list if news['id'] != news_id]

        # Reindex IDs
        for i, news in enumerate(news_list, 1):
            news['id'] = i

        save_news(news_list)
        await update.message.reply_text(f"Новость с ID {news_id} успешно удалена.")

    except ValueError:
        await update.message.reply_text("Дай мне валидный ID(int).")


def main():
    # Validate environment variables
    if not all([NEWS_BOT_TOKEN, ADMIN_CHAT_ID, NEWS_CHANNEL_ID]):
        logging.error("Missing required environment variables. Please check your .env file.")
        return

    application = Application.builder().token(NEWS_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("list", list_news))
    application.add_handler(CommandHandler("delete", delete_news))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    logging.info("Bot started successfully!")
    application.run_polling()


if __name__ == "__main__":
    main()
