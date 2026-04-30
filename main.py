import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# === 1. HEALTH CHECK SERVER (To keep Render happy) ===
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running!')

def run_health_check_server():
    # Render uses port 10000 by default
    server = HTTPServer(('0.0.0.0', 10000), SimpleHTTPRequestHandler)
    print("🌍 Health check server started on port 10000")
    server.serve_forever()

# Start server in background thread
threading.Thread(target=run_health_check_server, daemon=True).start()

# === 2. LOAD FROM ENVIRONMENT VARIABLES ===
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")
PASSWORD = os.environ.get("TELEGRAM_PASSWORD", "")

# === 3. SOURCE & TARGET ===
SOURCE_CHANNEL = -4952068101   # Use the full ID with -100 prefix if needed
TARGET_GROUP = -5105606585     # Replace with your actual target group ID

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def remove_wholesale_price(text):
    """Remove any line containing 'tk', 'Tk', or 'TK'"""
    if not text:
        return text
    
    lines = text.split('\n')
    new_lines = []
    
    for line in lines:
        # Check if "tk" exists in the line (case-insensitive)
        if "tk" in line.lower():
            print(f"🗑️ Filtering out line: {line.strip()}")
            continue
        new_lines.append(line)
    
    new_text = '\n'.join(new_lines)
    # Fix extra blank lines
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)
    return new_text.strip()

# === 4. EVENT HANDLERS ===

@client.on(events.Album(chats=SOURCE_CHANNEL))
async def album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 Processing Album: {len(event.messages)} items")
    
    new_text = remove_wholesale_price(original_text)
    
    try:
        media_files = [msg.media for msg in event.messages if msg.media]
        await client.send_file(TARGET_GROUP, file=media_files, caption=new_text, parse_mode=None)
        print(f"✅ Cleaned album forwarded to {TARGET_GROUP}")
    except Exception as e:
        print(f"❌ Error in album_handler: {e}")

@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def single_handler(event):
    # Ignore messages that are part of an album (handled above)
    if event.grouped_id:
        return
    
    msg = event.message
    original_text = msg.text or msg.raw_text or ""
    new_text = remove_wholesale_price(original_text)
    
    try:
        if msg.media:
            await client.send_file(TARGET_GROUP, file=msg.media, caption=new_text, parse_mode=None)
            print(f"✅ Cleaned media forwarded to {TARGET_GROUP}")
        else:
            await client.send_message(TARGET_GROUP, new_text)
            print(f"✅ Cleaned text forwarded to {TARGET_GROUP}")
    except Exception as e:
        print(f"❌ Error in single_handler: {e}")

async def main():
    print("🔌 Connecting to Telegram...")
    await client.start(phone=PHONE, password=PASSWORD if PASSWORD else None)
    
    # This prints the session string in logs once. 
    # Use it to update your TELEGRAM_SESSION variable if the current one expires.
    session_str = client.session.save()
    print(f"\n💾 Current Session String: {session_str}\n")
    
    print(f"🤖 Bot is live and listening to {SOURCE_CHANNEL}...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
