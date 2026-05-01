import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# === 1. HEALTH CHECK SERVER (Keep Render/JustRunMy.App happy) ===
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running!')

def run_health_check_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHTTPRequestHandler)
    print("🌍 Health check server started on port 10000")
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# === 2. CREDENTIALS ===
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")
PASSWORD = os.environ.get("TELEGRAM_PASSWORD", "")

# === 3. CHAT IDs ===
WHOLESALE_GROUPS = [
    -2670331096,
    -3607938528,
    -3591198481,
    -3508958197,
    -3550177477,
    -5219636345,
]
SALES_CHANNEL_ID = -4952068101
TARGET_GROUP_ID = -5105606585

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# === 4. PRICE CALCULATION (for wholesale → sales channel) ===
def calculate_prices(text):
    """Extract wholesale price and calculate selling/offer prices"""
    if not text:
        return text

    price_match = re.search(r"[Pp]rice\s*[:：]\s*(\d+)\s*[Tt][Kk]", text)
    if price_match:
        wholesale = int(price_match.group(1))
        regular = wholesale * 2
        offer = int(wholesale * 1.67)
        new_text = f"{text}\n\nregular price: {regular}\noffer price: {offer}"
        return new_text
    return text


# === 5. WHOLESALE PRICE REMOVAL (for sales channel → target group) ===
def remove_wholesale_price(text):
    """Remove any line containing 'tk', 'Tk', or 'TK'"""
    if not text:
        return text
    
    lines = text.split('\n')
    new_lines = []
    
    for line in lines:
        if "tk" in line.lower():
            print(f"🗑️ Filtering out line: {line.strip()}")
            continue
        new_lines.append(line)
    
    new_text = '\n'.join(new_lines)
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)
    return new_text.strip()


# === 6. FORWARD TO SALES CHANNEL (from wholesale groups) ===
@client.on(events.Album(chats=WHOLESALE_GROUPS))
async def wholesale_album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 Album from wholesale group {event.chat_id}: {len(event.messages)} photos")
    
    new_text = calculate_prices(original_text)
    
    try:
        media_files = [msg.media for msg in event.messages if msg.media]
        await client.send_file(SALES_CHANNEL_ID, file=media_files, caption=new_text, parse_mode=None)
        print(f"✅ Forwarded album to sales channel")
    except Exception as e:
        print(f"❌ Error forwarding album to sales: {e}")


@client.on(events.NewMessage(chats=WHOLESALE_GROUPS))
async def wholesale_single_handler(event):
    if event.grouped_id:
        return
    
    msg = event.message
    original_text = msg.text or msg.raw_text or ""
    new_text = calculate_prices(original_text)
    
    try:
        if msg.media:
            await client.send_file(SALES_CHANNEL_ID, file=msg.media, caption=new_text, parse_mode=None)
            print(f"✅ Forwarded media from group {event.chat_id} to sales")
        else:
            await client.send_message(SALES_CHANNEL_ID, new_text)
            print(f"✅ Forwarded text from group {event.chat_id} to sales")
    except Exception as e:
        print(f"❌ Error forwarding to sales: {e}")


# === 7. FORWARD TO TARGET GROUP (from sales channel) ===
@client.on(events.Album(chats=SALES_CHANNEL_ID))
async def sales_album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 Album from sales channel: {len(event.messages)} items")
    
    new_text = remove_wholesale_price(original_text)
    
    try:
        media_files = [msg.media for msg in event.messages if msg.media]
        await client.send_file(TARGET_GROUP_ID, file=media_files, caption=new_text, parse_mode=None)
        print(f"✅ Cleaned album forwarded to target group")
    except Exception as e:
        print(f"❌ Error forwarding album to target: {e}")


@client.on(events.NewMessage(chats=SALES_CHANNEL_ID))
async def sales_single_handler(event):
    if event.grouped_id:
        return
    
    msg = event.message
    original_text = msg.text or msg.raw_text or ""
    new_text = remove_wholesale_price(original_text)
    
    try:
        if msg.media:
            await client.send_file(TARGET_GROUP_ID, file=msg.media, caption=new_text, parse_mode=None)
            print(f"✅ Cleaned media forwarded to target group")
        else:
            await client.send_message(TARGET_GROUP_ID, new_text)
            print(f"✅ Cleaned text forwarded to target group")
    except Exception as e:
        print(f"❌ Error forwarding to target: {e}")


async def main():
    print("🔌 Connecting to Telegram...")
    await client.start(phone=PHONE, password=PASSWORD if PASSWORD else None)
    
    session_str = client.session.save()
    print(f"\n💾 Session string: {session_str}\n")
    
    print(f"🤖 Bot running...")
    print(f"   📥 Watching {len(WHOLESALE_GROUPS)} wholesale groups → Sales Channel")
    print(f"   📤 Watching Sales Channel → Target Group\n")
    
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
