import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_FILE = os.path.join(os.path.dirname(__file__), "autoreply_session")

if not os.path.exists(SESSION_FILE + ".session"):
    print("Xatolik: autoreply_session.session fayli topilmadi. Avval main.py orqali tizimga kiring.")
    exit(1)

client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
client.connect()

if not client.is_user_authorized():
    print("Xatolik: Foydalanuvchi tizimga kirmagan.")
    client.disconnect()
    exit(1)

string_session = StringSession.save(client.session)
client.disconnect()

print("\n" + "=" * 60)
print("SIZNING TELETHON STRING SESSION KODINGIZ:")
print("=" * 60)
print(string_session)
print("=" * 60)
print("Ushbu kodni Railway yoki Render'ning Environment Variables bo'limiga:")
print("TELETHON_SESSION nomi bilan qo'ying.")
print("=" * 60 + "\n")
