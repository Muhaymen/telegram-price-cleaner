import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# === 1. HEALTH CHECK SERVER ===
# NOTE: Only needed if this stays on a Render "Web Service".
# If you switch this single service to a "Background Worker" (recommended),
# you can delete this whole section + the UptimeRobot monitor for it,
# since Background Workers don't need inbound HTTP traffic to stay alive.
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health_check_server():
    server = HTTPServer(("0.0.0.0", 10000), SimpleHTTPRequestHandler)
    print("🌍 Health check server started on port 10000")
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# === 2. CREDENTIALS (single account, single session) ===
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")
PASSWORD = os.environ.get("TELEGRAM_PASSWORD", "")

# === 3. SOURCE GROUPS (union of all three bots' lists) ===
WHOLESALE_GROUPS = [
    -1002670331096,
    -1003591198481,
    -1003508958197,
    -1003550177477,
    -1003607938528,
    -1002105437124,
    -1001950071055,
    -1002324384553,
    -1002090867645,
    -1001852806730,
    -1001787684116,
    -5469616109,   # was only in bot (1)
    -5398204033,   # was only in main (1)
    -5067767363,   # was only in bot.py
]

# === 4. ROUTES (destination + its own pricing formula) ===
def bot1_price_text(wholesale):
    regular = wholesale * 2
    offer = int(wholesale * 1.67)
    return f"\n\nregular price: {regular}\noffer price: {offer}"

def bot2_price_text(wholesale):
    offer = int(wholesale * 1.11)
    return f"\n\nWholesale Price: {offer}"

def bot3_price_text(wholesale):
    offer = int(wholesale * 1.25)
    return f"\n\nResaller Price: {offer}"

ROUTES = [
    {"name": "Group 1 (x2 / x1.67)", "target": -1003569937421, "price_fn": bot1_price_text},
    {"name": "Group 2 (x1.11)",      "target": -1002307941036, "price_fn": bot2_price_text},
    {"name": "Group 3 (x1.25)",      "target": -1002304065773, "price_fn": bot3_price_text},
]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# === 5. TEXT PROCESSING ===
PRICE_RE = re.compile(r"[Pp]rice\s*[:：]\s*(\d+)\s*[Tt][Kk]")

def remove_wholesale_lines(text):
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

def build_text_for_route(original_text, price_fn):
    """Remove wholesale line, then append this route's own price calculation"""
    if not original_text:
        return original_text
    match = PRICE_RE.search(original_text)
    cleaned = remove_wholesale_lines(original_text)
    if match:
        wholesale = int(match.group(1))
        cleaned += price_fn(wholesale)
    return cleaned


# === 6. ALBUM HANDLER ===
@client.on(events.Album(chats=WHOLESALE_GROUPS))
async def album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 Album from wholesale group {event.chat_id}: {len(event.messages)} photos")

    media_files = [msg.media for msg in event.messages if msg.media]

    for route in ROUTES:
        text_for_route = build_text_for_route(original_text, route["price_fn"])
        try:
            await client.send_file(route["target"], file=media_files, caption=text_for_route, parse_mode=None)
            print(f"✅ Album sent to {route['name']}")
        except Exception as e:
            print(f"❌ Error forwarding album to {route['name']}: {e}")


# === 7. SINGLE MESSAGE HANDLER ===
@client.on(events.NewMessage(chats=WHOLESALE_GROUPS))
async def single_handler(event):
    if event.grouped_id:
        return  # handled by album_handler

    msg = event.message
    original_text = msg.text or msg.raw_text or ""
    print(f"📨 Message from wholesale group {event.chat_id}")

    for route in ROUTES:
        text_for_route = build_text_for_route(original_text, route["price_fn"])
        try:
            if msg.media:
                await client.send_file(route["target"], file=msg.media, caption=text_for_route, parse_mode=None)
                print(f"✅ Media sent to {route['name']}")
            else:
                await client.send_message(route["target"], text_for_route)
                print(f"✅ Text sent to {route['name']}")
        except Exception as e:
            print(f"❌ Error forwarding message to {route['name']}: {e}")


# === 8. MAIN LOOP WITH AUTO-RECONNECT ===
async def main():
    while True:
        try:
            print("🔌 Connecting to Telegram...")
            await client.start(phone=PHONE, password=PASSWORD if PASSWORD else None)

            me = await client.get_me()
            print(f"🤖 Bot logged in as: {me.first_name} (ID: {me.id})")

            print(f"📥 Watching {len(WHOLESALE_GROUPS)} wholesale groups")
            for route in ROUTES:
                print(f"📤 {route['name']} -> {route['target']}")

            await client.run_until_disconnected()
        except Exception as e:
            print(f"⚠️ Client crashed/disconnected: {e}")

        print("🔁 Reconnecting in 5s...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
