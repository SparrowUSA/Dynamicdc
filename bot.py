import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from content_fetcher import ContentFetcher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize client
app = Client(
    name=Config.SESSION_NAME,
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    phone_number=Config.PHONE_NUMBER,
    workers=10,
    sleep_threshold=30
)

# Initialize fetcher
fetcher = None

@app.on_message(filters.private & filters.incoming)
async def handle_message(client: Client, message: Message):
    """Handle incoming private messages"""
    global fetcher
    
    # Check if message is from authorized user
    if message.from_user.id != Config.YOUR_USER_ID:
        await message.reply("❌ Unauthorized access.")
        return
    
    try:
        # Initialize fetcher if not done
        if fetcher is None:
            fetcher = ContentFetcher(client)
        
        # Process command
        response = await fetcher.process_command(message.text, Config.YOUR_USER_ID)
        
        # Send response
        await message.reply(response)
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    if message.from_user.id != Config.YOUR_USER_ID:
        return
    
    await message.reply(
        "🚀 **Content Fetcher Bot Started!**\n\n"
        "I can fetch content from private Telegram channels "
        "even when forwarding is disabled.\n\n"
        "Use /help to see available commands."
    )

async def main():
    """Main function"""
    global fetcher
    
    await app.start()
    
    # Get user info
    me = await app.get_me()
    logger.info(f"Logged in as: {me.first_name} (@{me.username})")
    
    # Initialize fetcher
    fetcher = ContentFetcher(app)
    
    # Send startup notification
    await app.send_message(
        Config.YOUR_USER_ID,
        f"✅ **Bot is now active!**\n\n"
        f"👤 Logged in as: {me.first_name}\n"
        f"🆔 User ID: {me.id}\n"
        f"📊 Ready to fetch content.\n\n"
        f"Send /help to see commands."
    )
    
    logger.info("Bot started successfully!")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
