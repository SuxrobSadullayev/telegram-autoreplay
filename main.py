import os
import json
import time
import asyncio
import sqlite3
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

USE_AI = os.getenv("USE_AI", "True").lower() in ("true", "1", "yes")

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Jonli muloqot sozlamalari (Foydalanuvchiga xalaqit bermaslik uchun)
ACTIVE_CHAT_MINUTES = int(os.getenv("ACTIVE_CHAT_MINUTES", "15"))
ACTIVE_CHAT_TIMEOUT = ACTIVE_CHAT_MINUTES * 60  # soniyalarda
REPLY_DELAY_SECONDS = int(os.getenv("REPLY_DELAY_SECONDS", "5")) # AI javob berishdan oldin kutadigan vaqt
active_chats = {} # chat_id -> oxirgi yozgan vaqtimiz
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
DB_FILE = os.path.join(os.path.dirname(__file__), "messages.db")
SESSION_NAME = os.path.join(os.path.dirname(__file__), "autoreply_session")

# ==========================================
# 1. SQLite Ma'lumotlar Bazasi (Anti-Delete)
# ==========================================
def init_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_messages (
                    msg_id INTEGER,
                    chat_id INTEGER,
                    sender_id INTEGER,
                    sender_name TEXT,
                    text TEXT,
                    created_at TEXT,
                    PRIMARY KEY (msg_id, chat_id)
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Ma'lumotlar bazasini yaratishda xatolik: {e}")

init_db()

def save_incoming_message(msg_id: int, chat_id: int, sender_id: int, sender_name: str, text: str):
    """Kelgan har bir xabarni bazaga saqlab boradi (agar o'chirilsa tiklash uchun)."""
    if not text or text.strip() == "":
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO saved_messages (msg_id, chat_id, sender_id, sender_name, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, chat_id, sender_id, sender_name, text, now_str)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Xabarni DB ga saqlashda xatolik: {e}")

def get_saved_message(msg_id: int):
    """O'chirilgan xabarni bazadan qidiradi."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sender_name, sender_id, text, created_at FROM saved_messages WHERE msg_id = ?", (msg_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "sender_name": row[0],
                    "sender_id": row[1],
                    "text": row[2],
                    "created_at": row[3]
                }
    except Exception as e:
        logger.error(f"Xabarni DB dan olishda xatolik: {e}")
    return None

# ==========================================
# 2. Birinchi marta yozganlarni aniqlash
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
# 3. Cooldown va Kesh boshqaruvi
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
# 4. Validatsiya va TelegramClient
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
# 5. O'chirilgan xabarlarni tutish (Anti-Delete)
# ==========================================
@client.on(events.MessageDeleted)
async def deleted_message_handler(event):
    """Suhbatdosh biror xabarini o'chirsa, uni 'Saqlangan xabarlar'ga yuboradi."""
    for msg_id in event.deleted_ids:
        saved = get_saved_message(msg_id)
        if saved and saved.get("text"):
            logger.info(f"O'chirilgan xabar tutildi! Yuboruvchi: {saved['sender_name']} (Msg ID: {msg_id})")
            alert_text = (
                f"🗑 **O'chirilgan xabar aniqlandi!**\n\n"
                f"👤 **Yuboruvchi:** {saved['sender_name']} (ID: `{saved['sender_id']}`)\n"
                f"⏰ **Yozilgan vaqti:** {saved['created_at']}\n"
                f"💬 **O'chirilgan matn:**\n\"{saved['text']}\""
            )
            try:
                await client.send_message("me", alert_text)
            except Exception as e:
                logger.error(f"Saqlangan xabarlarga o'chirilgan xabarni yuborishda xatolik: {e}")

# ==========================================
# 6. O'zingiz yozgan xabarlarni kuzatish (Jonli suhbat)
# ==========================================
@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    global BOT_PAUSED
    if not event.is_private:
        return

    me = await client.get_me()
    # O'zingizning "Saqlangan xabarlar"ingizda botni boshqarish
    if event.chat_id == me.id:
        cmd = (event.raw_text or "").strip().lower()
        if cmd in (".stop", ".pause", "/stop", "/pause"):
            BOT_PAUSED = True
            await event.reply("⏸ **AI Avto-javob vaqtincha to'xtatildi.**\nQayta yoqish uchun `.start` deb yozing.")
            return
        elif cmd in (".start", ".resume", "/start", "/resume"):
            BOT_PAUSED = False
            await event.reply("▶️ **AI Avto-javob qayta yoqildi!**")
            return

    # Agar boshqa bir insonga o'zingiz xabar yozsangiz:
    active_chats[event.chat_id] = time.time()
    logger.info(f"Siz {event.chat_id} bilan o'zingiz yozishmoqdasiz. AI bu chatda {ACTIVE_CHAT_MINUTES} daqiqa xalaqit bermaydi.")

# ==========================================
# 7. Yangi xabarlarga avto-javob
# ==========================================
@client.on(events.NewMessage(incoming=True))
async def auto_reply_handler(event):
    if event.out:
        return

    if BOT_PAUSED:
        return

    # Guruhlarni tekshirish (agar yoqilgan bo'lsa)
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

    # Botlar va Telegram rasmiy servislarini inkor qilish
    if sender.bot or sender.id in (777000, 42777):
        return

    me = await client.get_me()
    if sender.id == me.id:
        return

    incoming_text = event.raw_text or ""
    sender_name = sender.first_name or "Foydalanuvchi"

    # Xabarni ma'lumotlar bazasiga saqlaymiz (Anti-Delete uchun)
    save_incoming_message(event.id, event.chat_id, sender.id, sender_name, incoming_text)

    # Jonli muloqot tekshiruvi: Agar siz bu suhbatdoshga oxirgi vaqtda o'zingiz yozgan bo'lsangiz:
    last_my_msg = active_chats.get(event.chat_id, 0)
    if (time.time() - last_my_msg) < ACTIVE_CHAT_TIMEOUT:
        logger.info(f"Siz {sender_name} bilan o'zingiz jonli yozishmoqdasiz. AI aralashmaydi.")
        return

    # Kontaktda mavjud bo'lganlarni inkor qilish tekshiruvi (agar sozlamada yoqilgan bo'lsa)
    if REPLY_ONLY_NON_CONTACTS and sender.contact:
        logger.info(f"Foydalanuvchi {sender_name} ({sender.id}) kontaktlarda mavjud, javob o'tkazib yuborildi.")
        return

    # Cooldown (qayta yuborish vaqti) tekshiruvi (agar > 0 bo'lsa)
    if not should_reply(sender.id):
        logger.info(f"Foydalanuvchi {sender_name} ({sender.id}) yaqinda javob olgan (cooldown faol).")
        return

    # Qisqa tanaffus (5 soniya) - o'zingiz o'qib, javob yozishingizga imkon beradi
    if REPLY_DELAY_SECONDS > 0:
        await asyncio.sleep(REPLY_DELAY_SECONDS)

    # 5 soniyadan so'ng qayta tekshiramiz: balki siz shu vaqt ichida o'zingiz javob yozgandirsiz?
    recent_msgs = await client.get_messages(event.chat_id, limit=2)
    if any(m.out for m in recent_msgs):
        logger.info(f"Siz {sender_name} ga o'zingiz javob yozdingiz, AI to'xtatildi.")
        active_chats[event.chat_id] = time.time()
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

async def main():
    await client.start()
    me = await client.get_me()
    logger.info("=" * 50)
    logger.info("Telegram Auto-Reply Userbot muvaffaqiyatli ishga tushdi!")
    logger.info(f"Akkaunt: {me.first_name} (@{me.username or 'username yoq'}) [ID: {me.id}]")
    logger.info(f"AI rejimi: {'YOQILGAN (Gemini AI)' if USE_AI else 'OCHIRILGAN'}")
    logger.info("Anti-Delete tizimi: FAOL (O'chirilgan xabarlar 'Saqlangan xabarlar'ga yuboriladi)")
    logger.info(f"Kutish oralig'i (cooldown): {COOLDOWN_MINUTES} daqiqa")
    logger.info("=" * 50)
    logger.info("Xabarlar tinglanmoqda... (To'xtatish uchun Ctrl+C bosing)")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Dastur foydalanuvchi tomonidan to'xtatildi.")
