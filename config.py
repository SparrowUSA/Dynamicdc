import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API credentials
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Your phone number (with country code)
    PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
    
    # Your user ID (destination)
    YOUR_USER_ID = int(os.getenv("YOUR_USER_ID", 0))
    
    # Session name
    SESSION_NAME = os.getenv("SESSION_NAME", "content_fetcher_bot")
    
    # Batch size for sending messages
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 10))
    
    # Delay between batches (seconds)
    BATCH_DELAY = int(os.getenv("BATCH_DELAY", 5))
    
    # Maximum messages to fetch in one request
    MAX_FETCH_LIMIT = int(os.getenv("MAX_FETCH_LIMIT", 1000))
