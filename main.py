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

    def do_HEAD(self):
        """Handle HEAD requests from UptimeRobot"""
        self.send_response(200)
        self.end_headers()

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
    -5219636345,
    -3591198481,
    -3508958197,
    -3550177477,
    -3607938528,
]
SALES_CHANNEL_ID = -4952068101
TARGET_GROUP_ID = -5105606585

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# === 4. TEXT PROCESSING ===
def calculate_prices(text):
    """Extract wholesale price and add regular/offer prices"""
    if not text:
        return text
    price_match = re.search(r"[Pp]rice\s*[:：]\s*(\d+)\s*[Tt][Kk]", text)
    if price_match:
        wholesale = int(price_match.group(1))
        regular = wholesale * 2
        offer = int(wholesale * 1.67)
        return f"{text}\n\nregular price: {regular}\noffer price: {offer}"
    return text

def remove_wholesale_price(text):
    """Remove any line containing 'tk', 'Tk', or 'TK'"""
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


def process_for_sales(text):
    """Add calculated prices to text"""
    return calculate_prices(text)

def process_for_target(text):
    """Remove wholesale price lines from text"""
    text_with_prices = calculate_prices(text)
    return remove_wholesale_price(text_with_prices)


# === 5. ALBUM HANDLER ===
@client.on(events.Album(chats=WHOLESALE_GROUPS))
async def album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 Album from wholesale group {event.chat_id}: {len(event.messages)} photos")

    sales_text = process_for_sales(original_text)
    target_text = process_for_target(original_text)

    media_files = [msg.media for msg in event.messages if msg.media]

    try:
        await client.send_file(SALES_CHANNEL_ID, file=media_files, caption=sales_text, parse_mode=None)
        print(f"✅ Album sent to Sales Channel")

        await client.send_file(TARGET_GROUP_ID, file=media_files, caption=target_text, parse_mode=None)
        print(f"✅ Album sent to Target Group")
    except Exception as e:
        print(f"❌ Error forwarding album: {e}")


# === 6. SINGLE MESSAGE HANDLER ===
@client.on(events.NewMessage(chats=WHOLESALE_GROUPS))
async def single_handler(event):
    if event.grouped_id:
        return

    msg = event.message
    original_text = msg.text or msg.raw_text or ""

    print(f"📨 Message from wholesale group {event.chat_id}")

    sales_text = process_for_sales(original_text)
    target_text = process_for_target(original_text)

    try:
        if msg.media:
            await client.send_file(SALES_CHANNEL_ID, file=msg.media, caption=sales_text, parse_mode=None)
            print(f"✅ Media sent to Sales Channel")

            await client.send_file(TARGET_GROUP_ID, file=msg.media, caption=target_text, parse_mode=None)
            print(f"✅ Media sent to Target Group")
        else:
            await client.send_message(SALES_CHANNEL_ID, sales_text)
            print(f"✅ Text sent to Sales Channel")

            await client.send_message(TARGET_GROUP_ID, target_text)
            print(f"✅ Text sent to Target Group")
    except Exception as e:
        print(f"❌ Error forwarding message: {e}")


async def main():
    print("🔌 Connecting to Telegram...")
    await client.start(phone=PHONE, password=PASSWORD if PASSWORD else None)

    me = await client.get_me()
    print(f"🤖 Bot logged in as: {me.first_name} (ID: {me.id})")

    session_str = client.session.save()
    print(f"💾 Session string: {session_str}\n")

    print(f"📥 Watching {len(WHOLESALE_GROUPS)} wholesale groups")
    print(f"📤 Sales Channel: {SALES_CHANNEL_ID} (with calculated prices)")
    print(f"📤 Target Group: {TARGET_GROUP_ID} (wholesale price removed)\n")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
