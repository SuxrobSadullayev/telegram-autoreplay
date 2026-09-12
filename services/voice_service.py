import io
import logging
from telethon import TelegramClient
from google.genai import types
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = (
    "Siz professional transkripsiya mutaxassisisiz. "
    "Ushbu audio/ovozli xabarda aytilgan gaplarni tinglang va to'liq, aniq matnga aylantiring (transkripsiya qiling).\n\n"
    "QAT'IY QOIDALAR:\n"
    "1. Faqat eshitilgan gap va so'zlarni to'g'ri orfografiya bilan yozing.\n"
    "2. Hech qanday kirish, xulosa yoki qo'shimcha izohlar qo'shmang (masalan: 'Audioda shunday deyilgan:' kabi so'zlar yozilmasin).\n"
    "3. Agar audioda inson ovozi bo'lmasa, faqat musiqa yoki shovqin bo'lsa, '[Ovoz aniqlanmadi yoki jimlik]' deb yozing."
)

async def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """Audio baytlarini Gemini AI orqali matnga aylantiradi."""
    if not audio_bytes or len(audio_bytes) == 0:
        return None

    try:
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        result = await call_gemini(
            contents=[audio_part, TRANSCRIPTION_PROMPT],
            temperature=0.2,
            max_output_tokens=2048
        )
        return result.strip() if result else None
    except Exception as e:
        logger.error(f"Ovozni matnga o'girishda xatolik: {e}")
        return None

async def transcribe_message(client: TelegramClient, message) -> str | None:
    """Telethon xabaridagi ovoz yoki audioni yuklab olib matnga o'giradi."""
    if not message or not message.media:
        return None

    is_voice = getattr(message, "voice", False)
    is_audio = getattr(message, "audio", False)
    is_video_note = getattr(message, "video_note", False)

    if not (is_voice or is_audio or is_video_note):
        return None

    try:
        # MIME typeni aniqlaymiz
        mime_type = "audio/ogg"
        if hasattr(message.media, "document") and message.media.document:
            mime_type = getattr(message.media.document, "mime_type", "audio/ogg")

        audio_bytes = await client.download_media(message, file=bytes)
        if not audio_bytes:
            return None

        return await transcribe_audio_bytes(audio_bytes, mime_type=mime_type)
    except Exception as e:
        logger.error(f"Xabardan audioni yuklab olishda xatolik: {e}")
        return None

async def handle_text_command(event):
    """
    .text yoki .transcribe buyrug'i:
    Ovozli xabarga reply qilib yozilganda, uni matnga aylantirib beradi.
    """
    if not event.is_reply:
        await event.reply(
            "ℹ️ **Qo'llanishi:** Ushbu buyruqni biror ovozli xabar (voice) yoki audio faylga **javob (reply)** qilib yozing.\n"
            "Misol: `.text`"
        )
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg or not (reply_msg.voice or reply_msg.audio or reply_msg.video_note):
        await event.reply("⚠️ Siz javob bergan xabarda hech qanday ovozli xabar yoki audio fayl topilmadi.")
        return

    status_msg = await event.reply("⏳ **Ovozli xabar tinglanmoqda va matnga o'girilmoqda...**")

    transcript = await transcribe_message(event.client, reply_msg)
    if transcript:
        result_text = (
            f"🎙 **Ovozli xabar matni:**\n\n"
            f"« {transcript} »"
        )
        await status_msg.edit(result_text)
    else:
        await status_msg.edit("❌ Ovozli xabarni matnga aylantirib bo'lmadi yoki audio tushunarsiz.")
