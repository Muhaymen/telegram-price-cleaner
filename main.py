import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# === 1. HEALTH CHECK SERVER ===
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check_server():
    server = HTTPServer(("0.0.0.0", 10000), SimpleHTTPRequestHandler)
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

# === 4. PRICE CALCULATION (Wholesale -> Sales Channel) ===
def calculate_prices(text):
    if not text:
        return text
    price_match = re.search(r"[Pp]rice\s*[:：]\s*(\d+)\s*[Tt][Kk]", text)
    if price_match:
        wholesale = int(price_match.group(1))
        regular = wholesale * 2
        offer = int(wholesale * 1.67)
        return f"{text}\n\nregular price: {regular}\noffer price: {offer}"
    return text

# === 5. WHOLESALE PRICE REMOVAL (Sales Channel -> Target Group) ===
def remove_wholesale_price(text):
    if not text:
        return text
    lines = text.split("\n")
    new_lines = []
    for line in lines:
        if "tk" in line.lower():
            print(f"🗑️ Filtering out line: {line.strip()}")
            continue
        new_lines.append(line)
    new_text = "\n".join(new_lines)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    return new_text.strip()


# === 6. WHOLESALE -> SALES CHANNEL HANDLERS ===
@client.on(events.Album(chats=WHOLESALE_GROUPS))
async def wholesale_album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 [WHOLESALE] Album from {event.chat_id}: {len(event.messages)} photos")
    new_text = calculate_prices(original_text)
    try:
        media_files = [msg.media for msg in event.messages if msg.media]
        sent = await client.send_file(SALES_CHANNEL_ID, file=media_files, caption=new_text, parse_mode=None)
        print(f"✅ [WHOLESALE] Album sent to Sales Channel (msg_id: {sent[0].id if isinstance(sent, list) else sent.id})")
    except Exception as e:
        print(f"❌ [WHOLESALE] Error: {e}")

@client.on(events.NewMessage(chats=WHOLESALE_GROUPS))
async def wholesale_single_handler(event):
    if event.grouped_id:
        return
    msg = event.message
    original_text = msg.text or msg.raw_text or ""
    new_text = calculate_prices(original_text)
    try:
        if msg.media:
            sent = await client.send_file(SALES_CHANNEL_ID, file=msg.media, caption=new_text, parse_mode=None)
            print(f"✅ [WHOLESALE] Media sent to Sales Channel (msg_id: {sent.id})")
        else:
            sent = await client.send_message(SALES_CHANNEL_ID, new_text)
            print(f"✅ [WHOLESALE] Text sent to Sales Channel (msg_id: {sent.id})")
    except Exception as e:
        print(f"❌ [WHOLESALE] Error: {e}")


# === 7. SALES CHANNEL -> TARGET GROUP HANDLERS ===
# CRITICAL FIX: Use incoming=True to only catch messages RECEIVED by the channel,
# not messages sent FROM the channel by this bot
@client.on(events.NewMessage(chats=SALES_CHANNEL_ID, incoming=True))
async def sales_single_handler(event):
    if event.grouped_id:
        return

    msg = event.message
    original_text = msg.text or msg.raw_text or ""

    print(f"📨 [SALES] New message in Sales Channel from sender {event.sender_id}")
    print(f"   Text preview: {original_text[:80]}...")

    new_text = remove_wholesale_price(original_text)

    try:
        if msg.media:
            sent = await client.send_file(TARGET_GROUP_ID, file=msg.media, caption=new_text, parse_mode=None)
            print(f"✅ [SALES] Media forwarded to Target Group (msg_id: {sent.id})")
        else:
            sent = await client.send_message(TARGET_GROUP_ID, new_text)
            print(f"✅ [SALES] Text forwarded to Target Group (msg_id: {sent.id})")
    except Exception as e:
        print(f"❌ [SALES] Error forwarding to target: {e}")

@client.on(events.Album(chats=SALES_CHANNEL_ID))
async def sales_album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 [SALES] Album in Sales Channel: {len(event.messages)} items")

    new_text = remove_wholesale_price(original_text)

    try:
        media_files = [msg.media for msg in event.messages if msg.media]
        sent = await client.send_file(TARGET_GROUP_ID, file=media_files, caption=new_text, parse_mode=None)
        print(f"✅ [SALES] Album forwarded to Target Group")
    except Exception as e:
        print(f"❌ [SALES] Error: {e}")


async def main():
    print("🔌 Connecting to Telegram...")
    await client.start(phone=PHONE, password=PASSWORD if PASSWORD else None)

    me = await client.get_me()
    print(f"🤖 Bot logged in as: {me.first_name} (ID: {me.id})")

    session_str = client.session.save()
    print(f"💾 Session string: {session_str}\n")

    print(f"📥 WHOLESALE -> SALES: Watching {len(WHOLESALE_GROUPS)} groups -> {SALES_CHANNEL_ID}")
    print(f"📤 SALES -> TARGET: Watching {SALES_CHANNEL_ID} -> {TARGET_GROUP_ID}\n")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
