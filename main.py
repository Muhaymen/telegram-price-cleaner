import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError


# ============================================================
# 1. HEALTH CHECK SERVER
# ============================================================
# Kept from your original working bot.
# Required because this is running as a Render Web Service.

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


threading.Thread(
    target=run_health_check_server,
    daemon=True
).start()


# ============================================================
# 2. CREDENTIALS
# ============================================================

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")
PASSWORD = os.environ.get("TELEGRAM_PASSWORD", "")


# ============================================================
# 3. CATEGORY ROUTING
# ============================================================
#
# IMPORTANT:
# Keep the IDs below in Telethon format.
#
# BAG:
# 8 source groups -> 3 destinations
#
# JEWELLERY:
# 4 source groups -> 3 destinations
#
# COSMETICS:
# 5 source groups -> 3 destinations
#
# MIXED ITEMS:
# 5 source groups -> 3 destinations
#
# 5469616109 is intentionally present in ALL FOUR categories.
#
# Therefore:
#
# 5469616109
#      |
#      +--> BAGS       -> 3 groups
#      |
#      +--> JEWELLERY  -> 3 groups
#      |
#      +--> COSMETICS  -> 3 groups
#      |
#      +--> MIXED      -> 3 groups
#
# There is NO deduplication between categories.
# ============================================================


CATEGORY_ROUTES = {

    "BAGS": {
        "sources": [
            -1002090867645,
            -1003508958197,
            -1001852806730,
            -1001787684116,
            -1001951740591,
            -1001625624771,
            -1002155025748,
            -5469616109,
        ],

        "destinations": [
            {
                "name": "BAGS - Destination 1 (x2 / x1.67)",
                "target": -1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "BAGS - Destination 2 (x1.11)",
                "target": -1002307941036,
                "price_fn": "bot2",
            },
            {
                "name": "BAGS - Destination 3 (x1.25)",
                "target": -1002304065773,
                "price_fn": "bot3",
            },
        ],
    },


    "JEWELLERY": {
        "sources": [
            -1001950071055,
            -1003607938528,
            -1002289435020,
            -5469616109,
        ],

        "destinations": [
            {
                "name": "JEWELLERY - Destination 1 (x2 / x1.67)",
                "target": -1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "JEWELLERY - Destination 2 (x1.11)",
                "target": -5541245327,
                "price_fn": "bot2",
            },
            {
                "name": "JEWELLERY - Destination 3 (x1.25)",
                "target": -5523004801,
                "price_fn": "bot3",
            },
        ],
    },


    "COSMETICS": {
        "sources": [
            -1002105437124,
            -1003591198481,
            -1002624473160,
            -1002440998125,
            -5469616109,
        ],

        "destinations": [
            {
                "name": "COSMETICS - Destination 1 (x2 / x1.67)",
                "target": -1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "COSMETICS - Destination 2 (x1.11)",
                "target": -5456273276,
                "price_fn": "bot2",
            },
            {
                "name": "COSMETICS - Destination 3 (x1.25)",
                "target": -5598693604,
                "price_fn": "bot3",
            },
        ],
    },


    "MIXED ITEMS": {
        "sources": [
            -1002324384553,
            -1003550177477,
            -1002690885699,
            -1002568161985,
            -5469616109,
        ],

        "destinations": [
            {
                "name": "MIXED ITEMS - Destination 1 (x2 / x1.67)",
                "target": -1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "MIXED ITEMS - Destination 2 (x1.11)",
                "target": -5471249349,
                "price_fn": "bot2",
            },
            {
                "name": "MIXED ITEMS - Destination 3 (x1.25)",
                "target": -5313617530,
                "price_fn": "bot3",
            },
        ],
    },
}


# ============================================================
# 4. PRICE FUNCTIONS
# ============================================================

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


PRICE_FUNCTIONS = {
    "bot1": bot1_price_text,
    "bot2": bot2_price_text,
    "bot3": bot3_price_text,
}


# ============================================================
# 5. CREATE SOURCE -> CATEGORY MAP
# ============================================================
#
# A source can belong to multiple categories.
#
# 5469616109 is intentionally mapped to all four.
# ============================================================

SOURCE_TO_CATEGORIES = {}

for category_name, category_data in CATEGORY_ROUTES.items():

    for source_id in category_data["sources"]:

        if source_id not in SOURCE_TO_CATEGORIES:
            SOURCE_TO_CATEGORIES[source_id] = []

        SOURCE_TO_CATEGORIES[source_id].append(category_name)


# Unique source groups watched by Telethon.
WHOLESALE_GROUPS = list(SOURCE_TO_CATEGORIES.keys())


# ============================================================
# 6. TELEGRAM CLIENT
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)


# ============================================================
# 7. TEXT PROCESSING
# ============================================================

PRICE_RE = re.compile(
    r"[Pp]rice\s*[:：]\s*(\d+)\s*[Tt][Kk]"
)


def remove_wholesale_lines(text):
    """
    Remove any line containing 'tk', 'Tk', or 'TK'.
    """

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

    new_text = re.sub(
        r"\n{3,}",
        "\n\n",
        new_text
    )

    return new_text.strip()


def build_text_for_route(original_text, price_fn):
    """
    Remove wholesale price line and append
    the destination-specific price calculation.
    """

    if not original_text:
        return original_text

    match = PRICE_RE.search(original_text)

    cleaned = remove_wholesale_lines(original_text)

    if match:
        wholesale = int(match.group(1))
        cleaned += price_fn(wholesale)

    return cleaned


# ============================================================
# 8. GET ALL ROUTES FOR A SOURCE GROUP
# ============================================================

def get_routes_for_source(source_id):

    categories = SOURCE_TO_CATEGORIES.get(
        source_id,
        []
    )

    routes = []

    for category_name in categories:

        category = CATEGORY_ROUTES[category_name]

        for destination in category["destinations"]:

            routes.append({
                "category": category_name,
                "name": destination["name"],
                "target": destination["target"],
                "price_fn": PRICE_FUNCTIONS[
                    destination["price_fn"]
                ],
            })

    return routes


# ============================================================
# 9. SAFE SEND FILE
# ============================================================
#
# Handles Telegram FloodWaitError.
#
# If Telegram says "wait 918 seconds", we wait and then
# continue instead of abandoning the route.
# ============================================================

async def safe_send_file(
    target,
    file,
    caption,
    route_name
):

    while True:

        try:

            await client.send_file(
                target,
                file=file,
                caption=caption,
                parse_mode=None
            )

            print(
                f"✅ Media sent to {route_name}"
            )

            return True

        except FloodWaitError as e:

            wait_seconds = e.seconds

            print(
                f"⏳ Telegram FloodWait for "
                f"{route_name}: "
                f"waiting {wait_seconds} seconds..."
            )

            await asyncio.sleep(
                wait_seconds + 2
            )

            print(
                f"🔄 FloodWait finished. "
                f"Retrying {route_name}..."
            )

        except Exception as e:

            print(
                f"❌ Error forwarding media "
                f"to {route_name}: {e}"
            )

            return False


# ============================================================
# 10. SAFE SEND MESSAGE
# ============================================================

async def safe_send_message(
    target,
    text,
    route_name
):

    while True:

        try:

            await client.send_message(
                target,
                text
            )

            print(
                f"✅ Text sent to {route_name}"
            )

            return True

        except FloodWaitError as e:

            wait_seconds = e.seconds

            print(
                f"⏳ Telegram FloodWait for "
                f"{route_name}: "
                f"waiting {wait_seconds} seconds..."
            )

            await asyncio.sleep(
                wait_seconds + 2
            )

            print(
                f"🔄 FloodWait finished. "
                f"Retrying {route_name}..."
            )

        except Exception as e:

            print(
                f"❌ Error forwarding text "
                f"to {route_name}: {e}"
            )

            return False


# ============================================================
# 11. ALBUM HANDLER
# ============================================================

@client.on(events.Album(chats=WHOLESALE_GROUPS))
async def album_handler(event):

    source_id = event.chat_id

    original_text = (
        event.text
        or event.raw_text
        or ""
    )

    print(
        f"\n📸 Album from wholesale group "
        f"{source_id}: "
        f"{len(event.messages)} photos"
    )

    categories = SOURCE_TO_CATEGORIES.get(
        source_id,
        []
    )

    print(
        f"📂 Categories triggered: "
        f"{', '.join(categories)}"
    )

    media_files = [
        msg.media
        for msg in event.messages
        if msg.media
    ]

    routes = get_routes_for_source(source_id)

    for route in routes:

        text_for_route = build_text_for_route(
            original_text,
            route["price_fn"]
        )

        await safe_send_file(
            route["target"],
            media_files,
            text_for_route,
            route["name"]
        )


# ============================================================
# 12. SINGLE MESSAGE HANDLER
# ============================================================

@client.on(events.NewMessage(chats=WHOLESALE_GROUPS))
async def single_handler(event):

    if event.grouped_id:
        return
        # Album handler processes grouped messages.

    source_id = event.chat_id

    msg = event.message

    original_text = (
        msg.text
        or msg.raw_text
        or ""
    )

    print(
        f"\n📨 Message from wholesale group "
        f"{source_id}"
    )

    categories = SOURCE_TO_CATEGORIES.get(
        source_id,
        []
    )

    print(
        f"📂 Categories triggered: "
        f"{', '.join(categories)}"
    )

    routes = get_routes_for_source(source_id)

    for route in routes:

        text_for_route = build_text_for_route(
            original_text,
            route["price_fn"]
        )

        if msg.media:

            await safe_send_file(
                route["target"],
                msg.media,
                text_for_route,
                route["name"]
            )

        else:

            await safe_send_message(
                route["target"],
                text_for_route,
                route["name"]
            )


# ============================================================
# 13. MAIN LOOP WITH AUTO-RECONNECT
# ============================================================

async def main():

    while True:

        try:

            print("🔌 Connecting to Telegram...")

            await client.start(
                phone=PHONE,
                password=PASSWORD if PASSWORD else None
            )

            me = await client.get_me()

            print(
                f"🤖 Bot logged in as: "
                f"{me.first_name} "
                f"(ID: {me.id})"
            )

            print(
                f"📥 Watching "
                f"{len(WHOLESALE_GROUPS)} "
                f"unique wholesale groups"
            )

            print("\n📋 ROUTING CONFIGURATION")

            for category_name, category in CATEGORY_ROUTES.items():

                print(
                    f"\n📂 {category_name}"
                )

                print(
                    "   📥 Source groups:"
                )

                for source in category["sources"]:
                    print(
                        f"      {source}"
                    )

                print(
                    "   📤 Destinations:"
                )

                for destination in category["destinations"]:

                    print(
                        f"      "
                        f"{destination['name']} "
                        f"-> "
                        f"{destination['target']}"
                    )

            print(
                "\n🟢 Bot is running...\n"
            )

            await client.run_until_disconnected()

        except Exception as e:

            print(
                f"⚠️ Client crashed/disconnected: "
                f"{e}"
            )

        print(
            "🔁 Reconnecting in 5s..."
        )

        await asyncio.sleep(5)


# ============================================================
# 14. START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
