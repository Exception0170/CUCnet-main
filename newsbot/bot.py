import os
import json
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration from .env
BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_CHAT_ID = int(os.getenv('ALLOWED_CHAT_ID'))
NEWS_CHANNEL_ID = os.getenv('NEWS_CHANNEL_ID')
JSON_FILE = "news.json"

# Load existing news
def load_news():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Save news to JSON
def save_news(news_list):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)

# Check if user is authorized
def is_authorized(chat_id):
    return chat_id == ALLOWED_CHAT_ID

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
        "Welcome to News Bot!\n"
        "Commands:\n"
        "/news - Add news (reply to this command with your news)\n"
        "/list - Show all news\n"
        "/delete <id> - Delete news by ID"
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized access.")
        return
    
    # Store that we're waiting for news input
    context.user_data['waiting_for_news'] = True
    await update.message.reply_text("Please send your news message:")

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
            bot = Bot(token=BOT_TOKEN)
            message = await bot.send_message(
                chat_id=NEWS_CHANNEL_ID,
                text=f"📰 {news_text}\n\nDate: {news_entry['date']}"
            )
            # Save the channel message ID for future deletion
            save_message_id(news_id, message.message_id)
            
        except Exception as e:
            logging.error(f"Error posting to channel: {e}")
        
        context.user_data['waiting_for_news'] = False
        await update.message.reply_text(f"News added successfully! ID: {news_id}")

async def list_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized access.")
        return
    
    news_list = load_news()
    
    if not news_list:
        await update.message.reply_text("No news available.")
        return
    
    response = "📰 News List:\n\n"
    for news in news_list[-10:]:  # Show last 10 news
        response += f"ID: {news['id']}\n"
        response += f"Date: {news['date']}\n"
        response += f"Text: {news['text'][:100]}...\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response)

async def delete_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized access.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /delete <news_id>")
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
            await update.message.reply_text(f"News with ID {news_id} not found.")
            return
        
        # Delete from channel if message ID exists
        if news_to_delete.get('channel_message_id'):
            try:
                bot = Bot(token=BOT_TOKEN)
                await bot.delete_message(
                    chat_id=NEWS_CHANNEL_ID,
                    message_id=news_to_delete['channel_message_id']
                )
            except Exception as e:
                logging.error(f"Error deleting message from channel: {e}")
                await update.message.reply_text(f"News deleted but channel deletion failed: {e}")
        
        # Remove from news list
        news_list = [news for news in news_list if news['id'] != news_id]
        
        # Reindex IDs
        for i, news in enumerate(news_list, 1):
            news['id'] = i
        
        save_news(news_list)
        await update.message.reply_text(f"News with ID {news_id} deleted successfully.")
        
    except ValueError:
        await update.message.reply_text("Please provide a valid numeric ID.")

def main():
    # Validate environment variables
    if not all([BOT_TOKEN, ALLOWED_CHAT_ID, NEWS_CHANNEL_ID]):
        logging.error("Missing required environment variables. Please check your .env file.")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
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