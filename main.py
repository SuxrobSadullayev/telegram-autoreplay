import os
import json
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Logging sozlash
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Muhit o'zgaruvchilarini yuklaymiz
load_dotenv()

from telethon import TelegramClient, events
from telethon.tl.types import User
from telethon.sessions import StringSession

from ai_helper import generate_ai_reply
from services.voice_service import handle_text_command, transcribe_message
from services.anti_delete_service import (
    save_incoming_event,
    handle_deleted_message_event,
    clean_old_media_cache
)
from services.summary_service import handle_summary_command
from services.reminder_service import (
    handle_remind_command,
    handle_reminders_list_command,
    handle_delremind_command,
    reminder_worker_loop
)
from services.utility_service import (
    handle_translate_command,
    handle_ai_command,
    handle_calc_command,
    handle_info_command,
    handle_help_command
)

USE_AI = os.getenv("USE_AI", "True").lower() in ("true", "1", "yes")

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Boshqaruv sozlamalari
REPLY_DELAY_SECONDS = int(os.getenv("REPLY_DELAY_SECONDS", "0"))
BOT_PAUSED = False

# Standart xabarlar
FIRST_TIME_MESSAGE = os.getenv(
    "FIRST_TIME_MESSAGE",
    "Assalomu alaykum! Hozirda offline holatdaman. Bo'sh vaqtim bo'lishi bilan xabarlaringizga albatta javob qaytaraman. Rahmat!"
)
AUTO_REPLY_MESSAGE = os.getenv(
    "AUTO_REPLY_MESSAGE",
    "Assalomu alaykum! Hozirda bandman. Xabaringizni ko'rishim bilan javob qaytaraman. Rahmat!"
)

COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "0"))
REPLY_ONLY_NON_CONTACTS = os.getenv("REPLY_ONLY_NON_CONTACTS", "False").lower() in ("true", "1", "yes")
REPLY_GROUP_MENTIONS = os.getenv("REPLY_GROUP_MENTIONS", "False").lower() in ("true", "1", "yes")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "replied_users.json")
KNOWN_USERS_FILE = os.path.join(os.path.dirname(__file__), "known_users.json")
SESSION_NAME = os.path.join(os.path.dirname(__file__), "autoreply_session")

# ==========================================
# 1. Birinchi marta yozganlarni aniqlash
# ==========================================
def load_known_users() -> set:
    if os.path.exists(KNOWN_USERS_FILE):
        try:
            with open(KNOWN_USERS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logger.warning(f"known_users.json ni o'qishda xatolik: {e}")
    return set()

def save_known_users(users: set):
    try:
        with open(KNOWN_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f)
    except Exception as e:
        logger.error(f"known_users.json ni saqlashda xatolik: {e}")

known_users = load_known_users()

async def check_is_first_time(chat_id: int, user_id: int) -> bool:
    """Foydalanuvchi birinchi marta yozayotganini tekshiradi."""
    uid_str = str(user_id)
    if uid_str in known_users:
        return False

    is_first = False
    try:
        messages = await client.get_messages(chat_id, limit=2)
        if len(messages) <= 1:
            is_first = True
    except Exception as e:
        logger.warning(f"Chat tarixini olishda xatolik: {e}")

    known_users.add(uid_str)
    save_known_users(known_users)
    return is_first

# ==========================================
# 2. Cooldown va Kesh boshqaruvi
# ==========================================
def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Kesh faylini o'qishda xatolik: {e}")
    return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Keshni saqlashda xatolik: {e}")

replied_users = load_cache()

def clean_expired_cache():
    now = time.time()
    cutoff = now - (COOLDOWN_MINUTES * 60)
    keys_to_delete = [uid for uid, timestamp in replied_users.items() if timestamp < cutoff]
    for uid in keys_to_delete:
        del replied_users[uid]
    if keys_to_delete:
        save_cache(replied_users)

def should_reply(user_id: int) -> bool:
    if COOLDOWN_MINUTES <= 0:
        return True
    clean_expired_cache()
    last_time = replied_users.get(str(user_id))
    if not last_time:
        return True
    return (time.time() - last_time) >= (COOLDOWN_MINUTES * 60)

def record_reply(user_id: int):
    replied_users[str(user_id)] = time.time()
    save_cache(replied_users)

# ==========================================
# 3. Validatsiya va TelegramClient
# ==========================================
def validate_credentials():
    if not API_ID or not API_HASH or API_ID.strip() == "" or API_HASH.strip() == "":
        logger.error("\nXATOLIK: .env faylida API_ID yoki API_HASH ko'rsatilmagan!\n")
        return False
    try:
        int(API_ID)
    except ValueError:
        logger.error("XATOLIK: API_ID faqat raqamlardan iborat bo'lishi kerak!")
        return False
    return True

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

# ==========================================
# 4. O'chirilgan xabarlarni tutish (Anti-Delete)
# ==========================================
@client.on(events.MessageDeleted)
async def deleted_message_handler(event):
    """Suhbatdosh biror xabar yoki mediani o'chirsa, uni Saqlangan xabarlarga yuboradi."""
    await handle_deleted_message_event(client, event)

# ==========================================
# 5. Buyruqlar dispetcheri (Commands Handler)
# ==========================================
async def dispatch_command(event) -> bool:
    """Foydalanuvchi buyruqlarini aniqlaydi va tegishli servisga yo'naltiradi."""
    global BOT_PAUSED
    raw = (event.raw_text or "").strip()
    if not raw:
        return False

    cmd_lower = raw.lower()

    # Boshqaruv buyruqlari
    if cmd_lower in (".stop", ".pause", "/stop", "/pause"):
        BOT_PAUSED = True
        msg = "⏸ **AI Avto-javob vaqtincha to'xtatildi.**\nQayta yoqish uchun `.start` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return True

    if cmd_lower in (".start", ".resume", "/start", "/resume"):
        BOT_PAUSED = False
        msg = "▶️ **AI Avto-javob qayta yoqildi!**"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return True

    if cmd_lower in (".help", "/help"):
        await handle_help_command(event)
        return True

    if cmd_lower in (".info", "/info"):
        await handle_info_command(event, BOT_PAUSED)
        return True

    if cmd_lower.startswith((".text", ".transcribe", ".ovoz")):
        await handle_text_command(event)
        return True

    if cmd_lower.startswith(".summary"):
        await handle_summary_command(event)
        return True

    if cmd_lower.startswith(".reminders"):
        await handle_reminders_list_command(event)
        return True

    if cmd_lower.startswith(".delremind"):
        await handle_delremind_command(event)
        return True

    if cmd_lower.startswith(".remind"):
        await handle_remind_command(event)
        return True

    if cmd_lower.startswith((".tr", ".translate")):
        await handle_translate_command(event)
        return True

    if cmd_lower.startswith(".ai"):
        await handle_ai_command(event)
        return True

    if cmd_lower.startswith(".calc"):
        await handle_calc_command(event)
        return True

    return False

# ==========================================
# 6. O'zingiz yozgan xabarlarni kuzatish (Outgoing)
# ==========================================
@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    # Buyruq bo'lsa uni bajaramiz
    handled = await dispatch_command(event)
    if handled:
        return

# ==========================================
# 7. Yangi xabarlarga avto-javob va Anti-Delete
# ==========================================
@client.on(events.NewMessage(incoming=True))
async def auto_reply_handler(event):
    if event.out:
        return

    me = await client.get_me()

    # O'zingizning Saqlangan xabarlar (Saved Messages)ingizga kelgan buyruqlar
    if event.chat_id == me.id:
        handled = await dispatch_command(event)
        if handled:
            return

    # Faqat shaxsiy (PM) xabarlarni Anti-Delete uchun keshga va DB ga saqlaymiz
    if event.is_private:
        await save_incoming_event(client, event)

    if BOT_PAUSED:
        return

    # Guruhlarni tekshirish (agar yoqilgan bo'lsa)
    if not event.is_private:
        if not REPLY_GROUP_MENTIONS:
            return
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

    # Botlar va Telegram rasmiy servislarini inkor qilish
    if sender.bot or sender.id in (777000, 42777):
        return

    if sender.id == me.id:
        return

    incoming_text = event.raw_text or ""
    sender_name = sender.first_name or "Foydalanuvchi"

    # Agar xabar ovozli bo'lsa va matni bo'lmasa, ovozni transkripsiya qilib AI ga uzatamiz
    if not incoming_text and (getattr(event.message, "voice", False) or getattr(event.message, "audio", False)):
        logger.info(f"Ovozli xabar olindi ({sender_name}), transkripsiya qilinmoqda...")
        voice_text = await transcribe_message(client, event.message)
        if voice_text:
            incoming_text = f"[Suhbatdosh ovozli xabar yubordi: \"{voice_text}\"]"

    # Kontaktda mavjud bo'lganlarni inkor qilish tekshiruvi
    if REPLY_ONLY_NON_CONTACTS and sender.contact:
        logger.info(f"Foydalanuvchi {sender_name} ({sender.id}) kontaktlarda mavjud, javob o'tkazib yuborildi.")
        return

    # Cooldown (qayta yuborish vaqti) tekshiruvi
    if not should_reply(sender.id):
        logger.info(f"Foydalanuvchi {sender_name} ({sender.id}) yaqinda javob olgan (cooldown faol).")
        return

    # Qisqa tanaffus (jonli suhbatni tekshirish uchun)
    if REPLY_DELAY_SECONDS > 0:
        await asyncio.sleep(REPLY_DELAY_SECONDS)

    # Tanaffusdan so'ng tekshiramiz: balki o'zingiz javob yozgandirsiz?
    recent_msgs = await client.get_messages(event.chat_id, limit=2)
    if any(m.out for m in recent_msgs):
        logger.info(f"Siz {sender_name} ga o'zingiz javob yozdingiz, AI to'xtatildi.")
        return

    # Birinchi marta yozayotganini tekshiramiz
    is_first_time = await check_is_first_time(event.chat_id, sender.id)
    if is_first_time:
        logger.info(f"Foydalanuvchi {sender_name} ({sender.id}) birinchi marta yozmoqda! (Offline xabari tayyorlanadi)")

    logger.info(f"Yangi xabar olindi: {sender_name} (ID: {sender.id}) -> '{incoming_text[:50]}'")

    reply_text = None
    if USE_AI:
        logger.info(f"Gemini AI orqali aqlli javob tayyorlanmoqda (Birinchi marta: {is_first_time})...")
        reply_text = await generate_ai_reply(sender_name, incoming_text, is_first_time=is_first_time)

    # Agar AI ishlamasa yoki o'chiq bo'lsa zaxira andozadan foydalanamiz
    if not reply_text:
        if is_first_time:
            reply_text = FIRST_TIME_MESSAGE
        else:
            reply_text = AUTO_REPLY_MESSAGE
        logger.info("Standart andoza xabaridan foydalanilmoqda.")

    try:
        await event.reply(reply_text)
        record_reply(sender.id)
        logger.info(f"Javob muvaffaqiyatli yuborildi: {sender_name} (ID: {sender.id})")
    except Exception as e:
        logger.error(f"Javob yuborishda xatolik yuz berdi: {e}")

# ==========================================
# 8. Vaqti-vaqti bilan eski keshni tozalash
# ==========================================
async def periodic_cache_cleaner():
    while True:
        try:
            clean_old_media_cache(max_age_hours=48)
        except Exception as e:
            logger.error(f"Kesh tozalash davriy xatosi: {e}")
        await asyncio.sleep(3600 * 12) # Har 12 soatda bir marta

# ==========================================
# 9. Asosiy ishga tushirish (Main)
# ==========================================
async def main():
    await client.start()
    me = await client.get_me()
    logger.info("=" * 60)
    logger.info("🚀 Telegram AI Userbot muvaffaqiyatli ishga tushdi!")
    logger.info(f"👤 Egasining akkaunti: {me.first_name} (@{me.username or 'yoq'}) [ID: {me.id}]")
    logger.info(f"🤖 AI rejimi: {'YOQILGAN (Google Gemini AI)' if USE_AI else 'OCHIRILGAN'}")
    logger.info("🛡 Anti-Delete tizimi: FAOL (Matn va Media keshlanadi)")
    logger.info("⏰ Aqlli eslatmalar (Reminders) tizimi: FAOL")
    logger.info("🎙 Voice-to-Text tizimi: FAOL (.text buyrug'i)")
    logger.info("📝 Chat Xulosalash tizimi: FAOL (.summary buyrug'i)")
    logger.info("=" * 60)
    logger.info("Barcha xabarlar va buyruqlar tinglanmoqda...")

    # Fon xizmatlarini ishga tushiramiz
    asyncio.create_task(reminder_worker_loop(client))
    asyncio.create_task(periodic_cache_cleaner())

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Dastur foydalanuvchi tomonidan to'xtatildi.")
