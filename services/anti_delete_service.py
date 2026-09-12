import os
import time
import asyncio
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
from db import DB_FILE, BASE_DIR

logger = logging.getLogger(__name__)

MEDIA_CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
MAX_MEDIA_SIZE_BYTES = 25 * 1024 * 1024  # Maksimal 25 MB gacha bo'lgan fayllar keshlanadi
MAX_CACHE_TOTAL_MB = 300                 # Jami kesh papkasi hajmi 300 MB dan oshmasligi kerak

os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

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

def _sync_save_incoming_msg(msg_id: int, chat_id: int, sender_id: int, sender_name: str, text: str, media_type: str | None, media_path: str | None):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO saved_messages 
                (msg_id, chat_id, sender_id, sender_name, text, media_type, media_path, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, chat_id, sender_id, sender_name, text, media_type, media_path, now_str))
            conn.commit()
    except Exception as e:
        logger.error(f"Anti-Delete xabarni DB ga saqlashda xatolik: {e}")

async def save_incoming_event(client: TelegramClient, event):
    """
    Faqat shaxsiy (PM) xabarlarni (matn, rasm, ovoz, video) ma'lumotlar bazasiga va keshga saqlaydi.
    Guruhlar va kanallardagi xabarlar saqlanmaydi.
    Agar suhbatdosh xabarni o'chirsa, to'liq tiklab beriladi.
    """
    try:
        # Faqat shaxsiy (private) xabarlarni saqlaymiz: guruh va kanallar inkor qilinadi
        if not getattr(event, "is_private", False):
            return

        # Kanal yoki guruh bo'lsa (yoki chat_id manfiy bo'lsa) saqlanmaydi
        if getattr(event, "is_channel", False) or getattr(event, "is_group", False):
            return

        if event.chat_id and event.chat_id < 0:
            return

        # Saqlangan xabarlar (Saved Messages) yoki o'zimizning chatimiz bo'lsa saqlanmaydi
        me = await client.get_me()
        if event.chat_id == me.id:
            return

        sender = await event.get_sender()
        if not sender:
            return

        # Botlardan kelgan xabarlarni saqlamaslik
        if getattr(sender, "bot", False) or getattr(sender, "id", 0) in (777000, 42777):
            return

        sender_name = getattr(sender, "first_name", "") or getattr(sender, "title", "Foydalanuvchi")
        sender_id = event.sender_id or getattr(sender, "id", 0)
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

        # Asinxron ravishda DB ga yozamiz
        await asyncio.to_thread(
            _sync_save_incoming_msg,
            event.id, event.chat_id, sender_id, sender_name, text, media_type, media_path
        )

    except Exception as e:
        logger.error(f"Anti-Delete xabarni saqlashda xatolik: {e}")

def _sync_get_saved_message(msg_id: int):
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

def _sync_delete_saved_message(msg_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM saved_messages WHERE msg_id = ?", (msg_id,))
            conn.commit()
    except Exception as e:
        logger.warning(f"O'chirilgan xabarni DB dan tozalashda xatolik: {e}")

async def handle_deleted_message_event(client: TelegramClient, event):
    """O'chirilgan xabarlarni tutib, Saqlangan xabarlar (Saved Messages) ga forward qiladi."""
    # Faqat shaxsiy yozishmalardagi o'chirilgan xabarlar ko'riladi: guruh va kanallar inkor qilinadi
    if getattr(event, "is_channel", False) or getattr(event, "is_group", False):
        return

    if event.chat_id and event.chat_id < 0:
        return

    for msg_id in event.deleted_ids:
        saved = await asyncio.to_thread(_sync_get_saved_message, msg_id)
        if not saved:
            continue

        # Agar bazadagi xabar guruh yoki kanalga tegishli bo'lsa (chat_id manfiy bo'lsa), inkor qilamiz
        saved_chat_id = saved.get("chat_id")
        if saved_chat_id and saved_chat_id < 0:
            continue

        sender_name = saved["sender_name"]
        sender_id = saved["sender_id"]
        created_at = saved["created_at"]
        text = saved["text"] or ""
        media_type = saved["media_type"]
        media_path = saved["media_path"]

        logger.info(f"O'chirilgan shaxsiy xabar aniqlandi! Yuboruvchi: {sender_name}, Media: {media_type or 'Matn'}")

        # Agar keshda media mavjud bo'lsa
        if media_path and os.path.exists(media_path):
            caption = (
                f"🗑 **O'chirilgan shaxsiy media tiklandi!**\n\n"
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
                f"🗑 **O'chirilgan shaxsiy xabar aniqlandi!**\n\n"
                f"👤 **Yuboruvchi:** {sender_name} (ID: `{sender_id}`)\n"
                f"⏰ **Yuborilgan vaqti:** {created_at}\n"
                f"💬 **O'chirilgan matn:**\n\"{text}\""
            )
            try:
                await client.send_message("me", alert_text)
            except Exception as e:
                logger.error(f"O'chirilgan matnni 'me' ga yuborishda xatolik: {e}")

        # Qayta ogohlantirmaslik uchun bazadan o'chirib tashlaymiz
        await asyncio.to_thread(_sync_delete_saved_message, msg_id)

def clean_old_media_cache(max_age_hours: int = 12, max_total_mb: int = MAX_CACHE_TOTAL_MB):
    """
    Kesh fayllarini tozalash (Vaqt va hajm kvotasi bo'yicha LRU tozalash):
    1. Belgilangan soatdan eski fayllar o'chiriladi.
    2. Agar jami kesh hajmi max_total_mb dan oshsa, eng eski fayllar birma-bir o'chiriladi.
    """
    try:
        if not os.path.exists(MEDIA_CACHE_DIR):
            return

        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        files = []

        for fname in os.listdir(MEDIA_CACHE_DIR):
            fpath = os.path.join(MEDIA_CACHE_DIR, fname)
            if os.path.isfile(fpath):
                try:
                    stat = os.stat(fpath)
                    # Agar muddati o'tgan bo'lsa darhol o'chiramiz
                    if stat.st_mtime < cutoff:
                        os.remove(fpath)
                        continue
                    files.append((fpath, stat.st_size, stat.st_mtime))
                except Exception:
                    pass

        # Hajm bo'yicha LRU tozalash
        total_bytes = sum(f[1] for f in files)
        max_bytes = max_total_mb * 1024 * 1024

        if total_bytes > max_bytes:
            # Eng eski o'zgartirilgan fayllar bo'yicha saralaymiz
            files.sort(key=lambda x: x[2])
            for fpath, fsize, _ in files:
                try:
                    os.remove(fpath)
                    total_bytes -= fsize
                    if total_bytes <= max_bytes:
                        break
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Keshni tozalashda xatolik: {e}")
