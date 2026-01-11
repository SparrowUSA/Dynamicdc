import asyncio
import logging
import re
from typing import List, Tuple, Optional
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

class ContentFetcher:
    def __init__(self, client: Client):
        self.client = client
    
    @staticmethod
    def parse_telegram_link(link: str) -> Tuple[Optional[str], Optional[int]]:
        """Parse Telegram link to get chat username/id and message ID"""
        patterns = [
            # t.me/c/1234567890/123
            r"t\.me/c/(\d+)/(\d+)",
            # t.me/username/123
            r"t\.me/(\w+)/(\d+)",
            # https://t.me/username/123
            r"https://t\.me/(\w+)/(\d+)",
            # https://t.me/c/1234567890/123
            r"https://t\.me/c/(\d+)/(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                if 'c/' in pattern:
                    # Channel link with -100 prefix
                    chat_id = f"-100{match.group(1)}"
                    message_id = int(match.group(2))
                    return chat_id, message_id
                else:
                    # Username link
                    username = match.group(1)
                    message_id = int(match.group(2))
                    return username, message_id
        
        return None, None
    
    async def get_chat_id_from_link(self, link: str) -> Optional[int]:
        """Get chat ID from link"""
        chat_identifier, _ = self.parse_telegram_link(link)
        if not chat_identifier:
            return None
        
        try:
            if isinstance(chat_identifier, str) and chat_identifier.startswith("-100"):
                return int(chat_identifier)
            else:
                # Get chat by username
                chat = await self.client.get_chat(chat_identifier)
                return chat.id
        except Exception as e:
            logger.error(f"Error getting chat ID: {e}")
            return None
    
    async def fetch_single_message(self, link: str) -> Optional[Message]:
        """Fetch a single message from link"""
        chat_identifier, message_id = self.parse_telegram_link(link)
        if not chat_identifier or not message_id:
            return None
        
        try:
            # Try to get the message
            message = await self.client.get_messages(
                chat_identifier,
                message_ids=message_id
            )
            return message
        except Exception as e:
            logger.error(f"Error fetching message: {e}")
            return None
    
    async def fetch_messages_range(self, start_link: str, end_link: str) -> List[Message]:
        """Fetch all messages between start and end links"""
        start_chat, start_msg_id = self.parse_telegram_link(start_link)
        end_chat, end_msg_id = self.parse_telegram_link(end_link)
        
        if not all([start_chat, start_msg_id, end_chat, end_msg_id]):
            raise ValueError("Invalid links provided")
        
        if start_chat != end_chat:
            raise ValueError("Links must be from the same chat")
        
        # Determine range
        min_id = min(start_msg_id, end_msg_id)
        max_id = max(start_msg_id, end_msg_id)
        
        logger.info(f"Fetching messages from ID {min_id} to {max_id} in chat {start_chat}")
        
        all_messages = []
        current_offset_id = max_id
        
        try:
            while True:
                # Fetch messages in batches
                messages = await self.client.get_chat_history(
                    chat_id=start_chat,
                    limit=100,
                    offset_id=current_offset_id
                )
                
                if not messages:
                    break
                
                filtered_messages = []
                for msg in messages:
                    if min_id <= msg.id <= max_id:
                        filtered_messages.append(msg)
                    elif msg.id < min_id:
                        break
                
                all_messages.extend(filtered_messages)
                
                # Check if we've reached the minimum ID
                if any(msg.id <= min_id for msg in messages):
                    break
                
                # Update offset for next batch
                current_offset_id = messages[-1].id
                
                # Small delay to avoid flood
                await asyncio.sleep(1)
            
            # Sort messages by ID (ascending order)
            all_messages.sort(key=lambda x: x.id)
            
            logger.info(f"Fetched {len(all_messages)} messages")
            return all_messages
            
        except FloodWait as e:
            logger.warning(f"Flood wait: {e.x} seconds")
            await asyncio.sleep(e.x + 5)
            return await self.fetch_messages_range(start_link, end_link)
        except Exception as e:
            logger.error(f"Error fetching messages range: {e}")
            return []
    
    async def send_message_batch(self, messages: List[Message], destination_id: int, 
                                 batch_size: int = 10, delay: int = 5) -> bool:
        """Send messages in batches to avoid rate limits"""
        if not messages:
            return False
        
        total_batches = (len(messages) + batch_size - 1) // batch_size
        sent_count = 0
        
        try:
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                # Send batch notification
                await self.client.send_message(
                    destination_id,
                    f"📦 **Batch {batch_num}/{total_batches}**\n"
                    f"Sending {len(batch)} messages..."
                )
                
                # Send each message in batch
                for message in batch:
                    try:
                        await message.copy(destination_id)
                        sent_count += 1
                        
                        # Small delay between messages
                        await asyncio.sleep(0.5)
                        
                    except FloodWait as e:
                        logger.warning(f"Flood wait: {e.x} seconds")
                        await asyncio.sleep(e.x + 2)
                        await message.copy(destination_id)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Error copying message {message.id}: {e}")
                        # Try to send text only
                        if message.text or message.caption:
                            text = message.text or message.caption
                            await self.client.send_message(destination_id, f"📝 {text}")
                
                # Delay between batches
                if i + batch_size < len(messages):
                    await asyncio.sleep(delay)
            
            # Send completion notification
            await self.client.send_message(
                destination_id,
                f"✅ **Completed!**\n"
                f"Successfully sent {sent_count}/{len(messages)} messages."
            )
            return True
            
        except Exception as e:
            logger.error(f"Error sending batch: {e}")
            await self.client.send_message(
                destination_id,
                f"❌ **Error occurred**\n"
                f"Sent {sent_count} messages before error: {str(e)}"
            )
            return False
    
    async def process_command(self, command_text: str, destination_id: int) -> str:
        """Process user command and return response"""
        try:
            if command_text.startswith('/batch'):
                # Parse batch command
                parts = command_text.split()
                if len(parts) != 3:
                    return "❌ Usage: /batch <start_link> <end_link>"
                
                start_link, end_link = parts[1], parts[2]
                
                # Send processing message
                await self.client.send_message(
                    destination_id,
                    "🔄 Processing batch request...\n"
                    f"From: {start_link}\n"
                    f"To: {end_link}"
                )
                
                # Fetch messages
                messages = await self.fetch_messages_range(start_link, end_link)
                
                if not messages:
                    return "❌ No messages found or error fetching"
                
                # Send messages
                success = await self.send_message_batch(
                    messages, 
                    destination_id,
                    batch_size=10,
                    delay=3
                )
                
                return "✅ Batch processing completed" if success else "❌ Batch processing failed"
            
            elif command_text.startswith('/single'):
                # Parse single message command
                parts = command_text.split()
                if len(parts) != 2:
                    return "❌ Usage: /single <message_link>"
                
                link = parts[1]
                message = await self.fetch_single_message(link)
                
                if message:
                    await message.copy(destination_id)
                    return "✅ Message sent"
                else:
                    return "❌ Unable to fetch message"
            
            elif command_text.startswith('/help'):
                return (
                    "🤖 **Content Fetcher Bot**\n\n"
                    "**Commands:**\n"
                    "• `/single <link>` - Fetch single message\n"
                    "• `/batch <start_link> <end_link>` - Fetch all messages between links\n"
                    "• `/help` - Show this help\n\n"
                    "**Examples:**\n"
                    "`/single https://t.me/channel/123`\n"
                    "`/batch https://t.me/channel/100 https://t.me/channel/150`\n\n"
                    "**Note:** Works with private channels where forwarding is disabled."
                )
            
            else:
                return "❌ Unknown command. Use /help to see available commands."
                
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            return f"❌ Error: {str(e)}"
