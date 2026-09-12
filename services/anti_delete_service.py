import os
import time
import logging
import sqlite3
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    DocumentAttributeFilename,
    DocumentAttributeAudio,
    DocumentAttributeVideo
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "messages.db")
MEDIA_CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
MAX_MEDIA_SIZE_BYTES = 25 * 1024 * 1024  # Maksimal 25 MB gacha bo'lgan fayllar keshlanadi

os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

def init_anti_delete_db():
    """Anti-Delete uchun SQLite bazasini ishga tushiradi va kerakli ustunlarni qo'shadi."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_messages (
                    msg_id INTEGER,
                    chat_id INTEGER,
                    sender_id INTEGER,
                    sender_name TEXT,
                    text TEXT,
                    media_type TEXT,
                    media_path TEXT,
                    created_at TEXT,
                    PRIMARY KEY (msg_id, chat_id)
                )
            """)
            # Eskiroq bazalarga yangi ustunlarni xavfsiz qo'shish (migratsiya)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(saved_messages)")
            columns = [col[1] for col in cursor.fetchall()]
            if "media_type" not in columns:
                conn.execute("ALTER TABLE saved_messages ADD COLUMN media_type TEXT")
            if "media_path" not in columns:
                conn.execute("ALTER TABLE saved_messages ADD COLUMN media_path TEXT")
            conn.commit()
    except Exception as e:
        logger.error(f"Anti-Delete DB ni ishga tushirishda xatolik: {e}")

init_anti_delete_db()

def get_media_type_str(message) -> str | None:
    """Xabardagi media turini aniqlaydi."""
    if not message.media:
        return None
    if isinstance(message.media, MessageMediaPhoto):
        return "Rasm (Photo)"
    if getattr(message, "voice", False):
        return "Ovozli xabar (Voice)"
    if getattr(message, "video_note", False):
        return "Dumaloq video (Video note)"
    if getattr(message, "video", False):
        return "Video"
    if getattr(message, "audio", False):
        return "Audio fayl"
    if isinstance(message.media, MessageMediaDocument):
        return "Hujjat / Fayl (Document)"
    return "Media"

async def save_incoming_event(client: TelegramClient, event):
    """
    Kelgan har bir xabar (matn, rasm, ovoz, video) ni ma'lumotlar bazasiga va keshga saqlaydi.
    Agar suhbatdosh xabarni o'chirsa, to'liq tiklab beriladi.
    """
    try:
        sender = await event.get_sender()
        sender_name = "Foydalanuvchi"
        sender_id = event.sender_id or 0
        if sender:
            sender_name = getattr(sender, "first_name", "") or getattr(sender, "title", "Foydalanuvchi")
            if getattr(sender, "last_name", None):
                sender_name += f" {sender.last_name}"

        text = event.raw_text or ""
        media_type = get_media_type_str(event.message)
        media_path = None

        # Agar xabarda media bo'lsa va hajmi mos kelsa, yuklab olib keshlaymiz
        if media_type and event.message.media:
            try:
                # Fayl hajmini tekshiramiz
                file_size = getattr(event.message, "file", None)
                size_bytes = getattr(file_size, "size", 0) if file_size else 0

                if size_bytes <= MAX_MEDIA_SIZE_BYTES:
                    # Kesh fayl nomi
                    ext = getattr(event.message.file, "ext", "") or ""
                    file_name = f"cached_{event.chat_id}_{event.id}{ext}"
                    target_path = os.path.join(MEDIA_CACHE_DIR, file_name)

                    downloaded = await client.download_media(event.message, file=target_path)
                    if downloaded and os.path.exists(downloaded):
                        media_path = downloaded
            except Exception as dl_err:
                logger.warning(f"Media faylni keshga yuklashda xatolik: {dl_err}")

        # Agar matn ham, media ham bo'lmasa saqlash shart emas
        if not text and not media_path:
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO saved_messages 
                (msg_id, chat_id, sender_id, sender_name, text, media_type, media_path, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (event.id, event.chat_id, sender_id, sender_name, text, media_type, media_path, now_str))
            conn.commit()

    except Exception as e:
        logger.error(f"Anti-Delete xabarni saqlashda xatolik: {e}")

def get_saved_message(msg_id: int):
    """O'chirilgan xabarni bazadan qidiradi."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sender_name, sender_id, text, media_type, media_path, created_at, chat_id 
                FROM saved_messages WHERE msg_id = ?
            """, (msg_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "sender_name": row[0],
                    "sender_id": row[1],
                    "text": row[2],
                    "media_type": row[3],
                    "media_path": row[4],
                    "created_at": row[5],
                    "chat_id": row[6]
                }
    except Exception as e:
        logger.error(f"Xabarni DB dan olishda xatolik: {e}")
    return None

async def handle_deleted_message_event(client: TelegramClient, event):
    """O'chirilgan xabarlarni tutib, Saqlangan xabarlar (Saved Messages) ga forward qiladi."""
    for msg_id in event.deleted_ids:
        saved = get_saved_message(msg_id)
        if not saved:
            continue

        sender_name = saved["sender_name"]
        sender_id = saved["sender_id"]
        created_at = saved["created_at"]
        text = saved["text"] or ""
        media_type = saved["media_type"]
        media_path = saved["media_path"]

        logger.info(f"O'chirilgan xabar aniqlandi! Yuboruvchi: {sender_name}, Media: {media_type or 'Matn'}")

        # Agar keshda media mavjud bo'lsa
        if media_path and os.path.exists(media_path):
            caption = (
                f"🗑 **O'chirilgan media tiklandi!**\n\n"
                f"👤 **Yuboruvchi:** {sender_name} (ID: `{sender_id}`)\n"
                f"📁 **Media turi:** {media_type}\n"
                f"⏰ **Yuborilgan vaqti:** {created_at}\n"
            )
            if text:
                caption += f"💬 **Izoh (matn):**\n\"{text}\""

            try:
                await client.send_file("me", media_path, caption=caption)
            except Exception as e:
                logger.error(f"O'chirilgan mediani 'me' ga yuborishda xatolik: {e}")
        elif text:
            # Faqat matnli xabar
            alert_text = (
                f"🗑 **O'chirilgan xabar aniqlandi!**\n\n"
                f"👤 **Yuboruvchi:** {sender_name} (ID: `{sender_id}`)\n"
                f"⏰ **Yuborilgan vaqti:** {created_at}\n"
                f"💬 **O'chirilgan matn:**\n\"{text}\""
            )
            try:
                await client.send_message("me", alert_text)
            except Exception as e:
                logger.error(f"O'chirilgan matnni 'me' ga yuborishda xatolik: {e}")

def clean_old_media_cache(max_age_hours: int = 48):
    """48 soatdan eski kesh fayllarni tozalab disk joyini tejaydi."""
    try:
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        if not os.path.exists(MEDIA_CACHE_DIR):
            return

        for fname in os.listdir(MEDIA_CACHE_DIR):
            fpath = os.path.join(MEDIA_CACHE_DIR, fname)
            if os.path.isfile(fpath):
                if os.path.getmtime(fpath) < cutoff:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Keshni tozalashda xatolik: {e}")
