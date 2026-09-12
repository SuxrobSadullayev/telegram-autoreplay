import os
import json
import time
import logging
# Logging sozlash
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Muhit o'zgaruvchilarini darhol yuklaymiz
load_dotenv()

from telethon import TelegramClient, events
from telethon.tl.types import User
from ai_helper import generate_ai_reply

USE_AI = os.getenv("USE_AI", "True").lower() in ("true", "1", "yes")

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
AUTO_REPLY_MESSAGE = os.getenv(
    "AUTO_REPLY_MESSAGE",
    "Assalomu alaykum! Hozirda bandman. Xabaringizni ko'rishim bilan javob qaytaraman. Rahmat!"
)
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "0"))
REPLY_ONLY_NON_CONTACTS = os.getenv("REPLY_ONLY_NON_CONTACTS", "False").lower() in ("true", "1", "yes")
REPLY_GROUP_MENTIONS = os.getenv("REPLY_GROUP_MENTIONS", "False").lower() in ("true", "1", "yes")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "replied_users.json")
SESSION_NAME = os.path.join(os.path.dirname(__file__), "autoreply_session")

def load_cache() -> dict:
    """Oldin javob berilgan foydalanuvchilar vaqtlari keshini yuklaydi."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Kesh faylini o'qishda xatolik: {e}")
    return {}

def save_cache(cache: dict):
    """Keshni faylga saqlaydi."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Keshni saqlashda xatolik: {e}")

# Keshni xotiraga yuklash
replied_users = load_cache()

def clean_expired_cache():
    """Muddati o'tgan kesh yozuvlarini tozalaydi."""
    now = time.time()
    cutoff = now - (COOLDOWN_MINUTES * 60)
    keys_to_delete = [uid for uid, timestamp in replied_users.items() if timestamp < cutoff]
    for uid in keys_to_delete:
        del replied_users[uid]
    if keys_to_delete:
        save_cache(replied_users)

def should_reply(user_id: int) -> bool:
    """Foydalanuvchiga javob berish vaqti kelganligini tekshiradi."""
    if COOLDOWN_MINUTES <= 0:
        return True
    clean_expired_cache()
    last_time = replied_users.get(str(user_id))
    if not last_time:
        return True
    return (time.time() - last_time) >= (COOLDOWN_MINUTES * 60)

def record_reply(user_id: int):
    """Foydalanuvchiga javob berilgan vaqtni qayd qiladi."""
    replied_users[str(user_id)] = time.time()
    save_cache(replied_users)

def validate_credentials():
    if not API_ID or not API_HASH or API_ID.strip() == "" or API_HASH.strip() == "":
        logger.error(
            "\n" + "=" * 60 + "\n"
            "XATOLIK: .env faylida API_ID yoki API_HASH ko'rsatilmagan!\n"
            "Iltimos, https://my.telegram.org saytiga kiring, API ma'lumotlarini oling\n"
            "va ularni .env fayliga kiriting.\n" + "=" * 60
        )
        return False
    try:
        int(API_ID)
    except ValueError:
        logger.error("XATOLIK: API_ID faqat raqamlardan iborat bo'lishi kerak!")
        return False
    return True

from telethon.sessions import StringSession

if not validate_credentials():
    exit(1)

TELETHON_SESSION_STR = os.getenv("TELETHON_SESSION", "").strip()
if TELETHON_SESSION_STR:
    try:
        session_target = StringSession(TELETHON_SESSION_STR)
    except Exception as e:
        logger.error(f"\n{'=' * 60}\nXATOLIK: TELETHON_SESSION kodi noto'g'ri yoki buzilgan!\nTafsilot: {e}\n{'=' * 60}")
        exit(1)
else:
    session_target = SESSION_NAME

client = TelegramClient(session_target, int(API_ID), API_HASH)

@client.on(events.NewMessage(incoming=True))
async def auto_reply_handler(event):
    # O'zimiz yuborgan xabarlarni inkor qilish
    if event.out:
        return

    # Guruhlarni tekshirish (agar yoqilgan bo'lsa, faqat murojaatlarga javob beradi)
    if not event.is_private:
        if not REPLY_GROUP_MENTIONS:
            return
        me = await client.get_me()
        is_mentioned = False
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.sender_id == me.id:
                is_mentioned = True
        if not is_mentioned and (event.mentioned or (me.username and f"@{me.username.lower()}" in (event.raw_text or "").lower())):
            is_mentioned = True
        if not is_mentioned:
            return

    sender = await event.get_sender()
    if not sender or not isinstance(sender, User):
        return

    # Botlarni va rasmiy Telegram servis xabarlarini inkor qilish
    if sender.bot or sender.id in (777000, 42777):
        return

    me = await client.get_me()
    if sender.id == me.id:
        return

    # Kontaktda mavjud bo'lganlarni inkor qilish tekshiruvi (agar sozlamada yoqilgan bo'lsa)
    if REPLY_ONLY_NON_CONTACTS and sender.contact:
        logger.info(f"Foydalanuvchi {sender.first_name} ({sender.id}) kontaktlarda mavjud, javob o'tkazib yuborildi.")
        return

    # Cooldown (qayta yuborish vaqti) tekshiruvi (agar > 0 bo'lsa)
    if not should_reply(sender.id):
        logger.info(f"Foydalanuvchi {sender.first_name} ({sender.id}) yaqinda javob olgan (cooldown faol).")
        return

    incoming_text = event.raw_text or ""
    sender_name = sender.first_name or "Foydalanuvchi"

    logger.info(f"Yangi xabar olindi: {sender_name} (ID: {sender.id}) -> '{incoming_text[:50]}'")

    # AI orqali javob olishga harakat qilamiz
    reply_text = None
    if USE_AI:
        logger.info("Gemini AI orqali aqlli javob tayyorlanmoqda...")
        reply_text = await generate_ai_reply(sender_name, incoming_text)

    # Agar AI o'chirilgan bo'lsa yoki xatolik bo'lsa, zaxira andozadan foydalanamiz
    if not reply_text:
        reply_text = AUTO_REPLY_MESSAGE
        logger.info("Standart andoza xabaridan foydalanilmoqda.")

    try:
        await event.reply(reply_text)
        record_reply(sender.id)
        logger.info(f"Javob muvaffaqiyatli yuborildi: {sender_name} (ID: {sender.id})")
    except Exception as e:
        logger.error(f"Javob yuborishda xatolik yuz berdi: {e}")

async def main():
    await client.start()
    me = await client.get_me()
    logger.info("=" * 50)
    logger.info("Telegram Auto-Reply Userbot muvaffaqiyatli ishga tushdi!")
    logger.info(f"Akkaunt: {me.first_name} (@{me.username or 'username yoq'}) [ID: {me.id}]")
    logger.info(f"AI rejimi: {'YOQILGAN (Gemini AI)' if USE_AI else 'OCHIRILGAN (Faqat andoza matn)'}")
    logger.info(f"Kutish oralig'i (cooldown): {COOLDOWN_MINUTES} daqiqa")
    logger.info(f"Faqat begonalarga javob: {REPLY_ONLY_NON_CONTACTS}")
    logger.info("=" * 50)
    logger.info("Xabarlar tinglanmoqda... (To'xtatish uchun Ctrl+C bosing)")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Dastur foydalanuvchi tomonidan to'xtatildi.")
