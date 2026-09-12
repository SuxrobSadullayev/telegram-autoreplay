import os
import io
import re
import time
import asyncio
import logging
from gtts import gTTS
from telethon import TelegramClient
from db import BASE_DIR

logger = logging.getLogger(__name__)

TTS_CACHE_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

def _sync_generate_tts(text: str, file_path: str, lang: str = "uz"):
    """gTTS orqali ovoz hosil qilish (sinxron worker)."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(file_path)
        return True
    except Exception as e:
        logger.error(f"gTTS xatosi: {e}")
        # Agar ko'rsatilgan tilda xato bersa, standart 'ru' yoki 'en' bilan sinab ko'ramiz
        try:
            tts = gTTS(text=text, lang="ru", slow=False)
            tts.save(file_path)
            return True
        except Exception as e2:
            logger.error(f"Zaxira gTTS xatosi: {e2}")
            return False

def detect_language_simple(text: str) -> str:
    """Matn tilini sodda usulda aniqlash (o'zbek, rus, ingliz)."""
    cyrillic_chars = len(re.findall(r"[\u0400-\u04FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))

    if cyrillic_chars > latin_chars:
        return "ru"
    # O'zbek tiliga xos harflar yoki standart uz
    return "uz"

async def handle_voice_command(event):
    """
    .voice <matn> buyrug'i:
    Matnni inson ovozidagi audio (Voice Note) ga aylantirib yuboradi.
    Xabarga javob (reply) qilib yozilsa ham ishlaydi.
    """
    raw = (event.raw_text or "").strip()
    text = re.sub(r"^\.voice\s*", "", raw, flags=re.IGNORECASE).strip()

    if not text and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            text = reply_msg.raw_text.strip()

    if not text:
        msg = (
            "ℹ️ **Qo'llanishi:**\n"
            "• `.voice <matningiz>` — Matnni ovozli xabar qilib yuboradi.\n"
            "• Yoki biror matnli xabarga **javob (reply)** qilib `.voice` deb yozing."
        )
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("🎙 **Matn ovozli xabarga aylantirilmoqda...**")
    else:
        status_msg = await event.reply("🎙 **Matn ovozli xabarga aylantirilmoqda...**")

    lang = detect_language_simple(text)
    timestamp = int(time.time() * 1000)
    audio_path = os.path.join(TTS_CACHE_DIR, f"tts_{timestamp}.mp3")

    try:
        success = await asyncio.to_thread(_sync_generate_tts, text, audio_path, lang)
        if not success or not os.path.exists(audio_path):
            await status_msg.edit("❌ Ovoz hosil qilishda xatolik yuz berdi.")
            return

        # Telegram ovozli xabar (Voice Note) sifatida yuboramiz
        await event.client.send_file(
            event.chat_id,
            audio_path,
            voice_note=True,
            reply_to=event.reply_to_msg_id if event.is_reply else None
        )

        # Holat xabarini o'chiramiz
        await status_msg.delete()

    except Exception as e:
        logger.error(f".voice buyrug'ida xatolik: {e}")
        await status_msg.edit(f"❌ Xatolik: {e}")
    finally:
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass
