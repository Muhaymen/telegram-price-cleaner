import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession


# ============================================================
# 1. HEALTH CHECK SERVER
# ============================================================
# Kept exactly for Render Web Service.
# If you later switch to a Background Worker, this can be removed.

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
# These IDs are kept exactly as provided.
#
# Pricing:
# Destination 1 = x2 regular / x1.67 offer
# Destination 2 = x1.11
# Destination 3 = x1.25
#
# 5469616109 is intentionally present in ALL categories
# for testing, exactly as requested.
# ============================================================

CATEGORY_ROUTES = {

    "BAGS": {
        "sources": [
            1002090867645,
            1003508958197,
            1001852806730,
            1001787684116,
            1001951740591,
            1001625624771,
            1002155025748,
            5469616109,
        ],

        "destinations": [
            {
                "name": "Bags - Destination 1 (x2 / x1.67)",
                "target": 1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "Bags - Destination 2 (x1.11)",
                "target": 1002307941036,
                "price_fn": "bot2",
            },
            {
                "name": "Bags - Destination 3 (x1.25)",
                "target": 1002304065773,
                "price_fn": "bot3",
            },
        ],
    },


    "JEWELLERY": {
        "sources": [
            1001950071055,
            1003607938528,
            1002289435020,
            5469616109,
        ],

        "destinations": [
            {
                "name": "Jewellery - Destination 1 (x2 / x1.67)",
                "target": 1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "Jewellery - Destination 2 (x1.11)",
                "target": 5541245327,
                "price_fn": "bot2",
            },
            {
                "name": "Jewellery - Destination 3 (x1.25)",
                "target": 5523004801,
                "price_fn": "bot3",
            },
        ],
    },


    "COSMETICS": {
        "sources": [
            1002105437124,
            1003591198481,
            1002624473160,
            1002440998125,
            5469616109,
        ],

        "destinations": [
            {
                "name": "Cosmetics - Destination 1 (x2 / x1.67)",
                "target": 1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "Cosmetics - Destination 2 (x1.11)",
                "target": 5456273276,
                "price_fn": "bot2",
            },
            {
                "name": "Cosmetics - Destination 3 (x1.25)",
                "target": 5598693604,
                "price_fn": "bot3",
            },
        ],
    },


    "MIXED ITEMS": {
        "sources": [
            1002324384553,
            1003550177477,
            1002690885699,
            1002568161985,
            5469616109,
        ],

        "destinations": [
            {
                "name": "Mixed Items - Destination 1 (x2 / x1.67)",
                "target": 1003569937421,
                "price_fn": "bot1",
            },
            {
                "name": "Mixed Items - Destination 2 (x1.11)",
                "target": 5471249349,
                "price_fn": "bot2",
            },
            {
                "name": "Mixed Items - Destination 3 (x1.25)",
                "target": 5313617530,
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

    return (
        f"\n\nregular price: {regular}"
        f"\noffer price: {offer}"
    )


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
# 5. BUILD SOURCE -> CATEGORY MAP
# ============================================================
#
# A source can belong to multiple categories.
#
# Example:
# 5469616109 belongs to:
# BAGS
# JEWELLERY
# COSMETICS
# MIXED ITEMS
#
# Therefore its message will be routed through all four
# category configurations.
# ============================================================

SOURCE_TO_CATEGORIES = {}

for category_name, category_data in CATEGORY_ROUTES.items():

    for source_id in category_data["sources"]:

        if source_id not in SOURCE_TO_CATEGORIES:
            SOURCE_TO_CATEGORIES[source_id] = []

        SOURCE_TO_CATEGORIES[source_id].append(category_name)


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
    Remove wholesale price line and append the
    destination-specific price calculation.
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
# 8. GET ROUTES FOR A SOURCE GROUP
# ============================================================

def get_routes_for_source(source_id):
    """
    Return all destination routes belonging to this source.

    A source may belong to multiple categories.

    Duplicate destination IDs are removed so that the same
    Telegram destination does not receive duplicate copies.

    Example:
    5469616109 belongs to all four categories.

    Since Destination 1 is:
    1003569937421

    in all four categories, that destination receives
    only ONE copy.
    """

    categories = SOURCE_TO_CATEGORIES.get(source_id, [])

    routes = []

    seen_destinations = set()

    for category_name in categories:

        category = CATEGORY_ROUTES[category_name]

        for destination in category["destinations"]:

            target = destination["target"]

            if target in seen_destinations:

                print(
                    f"ℹ️ Duplicate destination {target} "
                    f"detected for {source_id}; "
                    f"skipping duplicate send."
                )

                continue

            seen_destinations.add(target)

            routes.append({
                "category": category_name,
                "name": destination["name"],
                "target": target,
                "price_fn": PRICE_FUNCTIONS[
                    destination["price_fn"]
                ],
            })

    return routes


# ============================================================
# 9. ALBUM HANDLER
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
        f"📸 Album from wholesale group "
        f"{source_id}: {len(event.messages)} photos"
    )

    categories = SOURCE_TO_CATEGORIES.get(
        source_id,
        []
    )

    print(
        f"📂 Source belongs to categories: "
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

        try:

            await client.send_file(
                route["target"],
                file=media_files,
                caption=text_for_route,
                parse_mode=None
            )

            print(
                f"✅ Album sent to "
                f"{route['name']}"
            )

        except Exception as e:

            print(
                f"❌ Error forwarding album to "
                f"{route['name']}: {e}"
            )


# ============================================================
# 10. SINGLE MESSAGE HANDLER
# ============================================================

@client.on(events.NewMessage(chats=WHOLESALE_GROUPS))
async def single_handler(event):

    if event.grouped_id:
        return
        # Album handler will process it.

    source_id = event.chat_id

    msg = event.message

    original_text = (
        msg.text
        or msg.raw_text
        or ""
    )

    print(
        f"📨 Message from wholesale group "
        f"{source_id}"
    )

    categories = SOURCE_TO_CATEGORIES.get(
        source_id,
        []
    )

    print(
        f"📂 Source belongs to categories: "
        f"{', '.join(categories)}"
    )

    routes = get_routes_for_source(source_id)

    for route in routes:

        text_for_route = build_text_for_route(
            original_text,
            route["price_fn"]
        )

        try:

            if msg.media:

                await client.send_file(
                    route["target"],
                    file=msg.media,
                    caption=text_for_route,
                    parse_mode=None
                )

                print(
                    f"✅ Media sent to "
                    f"{route['name']}"
                )

            else:

                await client.send_message(
                    route["target"],
                    text_for_route
                )

                print(
                    f"✅ Text sent to "
                    f"{route['name']}"
                )

        except Exception as e:

            print(
                f"❌ Error forwarding message to "
                f"{route['name']}: {e}"
            )


# ============================================================
# 11. MAIN LOOP WITH AUTO-RECONNECT
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

            print("\n📋 ROUTING CONFIGURATION:")

            for category_name, category in CATEGORY_ROUTES.items():

                print(
                    f"\n📂 {category_name}"
                )

                print(
                    f"   📥 Sources: "
                    f"{len(category['sources'])}"
                )

                for destination in category["destinations"]:

                    print(
                        f"   📤 "
                        f"{destination['name']} "
                        f"-> "
                        f"{destination['target']}"
                    )

            print("\n🟢 Bot is running...\n")

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
# 12. START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
