import os
import re
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# === LOAD FROM ENVIRONMENT VARIABLES ===
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")
PASSWORD = os.environ.get("TELEGRAM_PASSWORD", "")

# === SOURCE & TARGET ===
SOURCE_CHANNEL = -4952068101      # Your sales channel
TARGET_GROUP = -5173607131         # REPLACE WITH ACTUAL TARGET GROUP ID

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def remove_wholesale_price(text):
    """Remove wholesale price line, keep regular & offer price"""
    if not text:
        return text
    
    lines = text.split('\n')
    new_lines = []
    
    for line in lines:
        if re.search(r'[Pp]rice\s*[:：]\s*\d+\s*[Tt][Kk]', line):
            continue
        new_lines.append(line)
    
    new_text = '\n'.join(new_lines)
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)
    return new_text.strip()


@client.on(events.Album(chats=SOURCE_CHANNEL))
async def album_handler(event):
    original_text = event.text or event.raw_text or ""
    print(f"📸 Album: {len(event.messages)} photos")
    
    new_text = remove_wholesale_price(original_text)
    
    try:
        media_files = [msg.media for msg in event.messages if msg.media]
        await client.send_file(TARGET_GROUP, file=media_files, caption=new_text, parse_mode=None)
        print(f"✅ Cleaned album forwarded")
    except Exception as e:
        print(f"❌ Error: {e}")


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def single_handler(event):
    if event.grouped_id:
        return
    
    msg = event.message
    original_text = msg.text or msg.raw_text or ""
    new_text = remove_wholesale_price(original_text)
    
    try:
        if msg.media:
            await client.send_file(TARGET_GROUP, file=msg.media, caption=new_text, parse_mode=None)
            print(f"✅ Cleaned media forwarded")
        else:
            await client.send_message(TARGET_GROUP, new_text)
            print(f"✅ Cleaned text forwarded")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    print("🔌 Connecting to Telegram...")
    await client.start(phone=PHONE, password=PASSWORD if PASSWORD else None)
    
    session_str = client.session.save()
    print(f"\n💾 Session: {session_str[:50]}...")
    
    print(f"\n🤖 Bot running...")
    print(f"📥 Source: {SOURCE_CHANNEL}")
    print(f"📤 Target: {TARGET_GROUP}")
    print(f"🧹 Removing wholesale price lines\n")
    
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())