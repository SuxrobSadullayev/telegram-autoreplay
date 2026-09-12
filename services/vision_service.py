import io
import re
import logging
from telethon import TelegramClient
from google.genai import types
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

async def handle_see_command(event):
    """
    .see <savol> buyrug'i:
    Rasm, fotosurat yoki skrinshotga javob qilib yozilganda Gemini Vision orqali tahlil qiladi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Biror rasmga **javob (reply)** qilib yozing.\nMisol: `.see Bu rasmda nima tasvirlangan?` yoki `.see Ushbu masalani yechib ber`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg or not (reply_msg.photo or (reply_msg.document and getattr(reply_msg.file, "mime_type", "").startswith("image/"))):
        msg = "⚠️ Siz javob bergan xabarda rasm yoki fotosurat topilmadi."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    raw = (event.raw_text or "").strip()
    query = re.sub(r"^\.see\s*", "", raw, flags=re.IGNORECASE).strip()
    if not query:
        query = "Ushbu rasmda nima tasvirlangan? Rasm mazmunini, ob'ektlarni va tafsilotlarni o'zbek tilida batafsil tushuntirib bering."

    if event.out:
        status_msg = await event.edit("👁 **Rasm Gemini AI orqali tahlil qilinmoqda...**")
    else:
        status_msg = await event.reply("👁 **Rasm Gemini AI orqali tahlil qilinmoqda...**")

    try:
        image_bytes = await event.client.download_media(reply_msg, file=bytes)
        if not image_bytes:
            await status_msg.edit("❌ Rasmni yuklab olish imkoni bo'lmadi.")
            return

        mime_type = "image/jpeg"
        if reply_msg.document and getattr(reply_msg.file, "mime_type", ""):
            mime_type = reply_msg.file.mime_type

        img_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        prompt = (
            f"Foydalanuvchi so'rovi: {query}\n\n"
            f"VAZIFA: Yuqoridagi rasmni sinchiklab o'rganing va foydalanuvchi so'roviga o'zbek tilida aniq, tushunarli va to'liq javob bering."
        )

        ai_res = await call_gemini(
            contents=[img_part, prompt],
            temperature=0.4,
            max_output_tokens=2048
        )

        if ai_res:
            res_text = f"👁 **Rasm Tahlili:**\n\n{ai_res}"
            await status_msg.edit(res_text)
        else:
            await status_msg.edit("❌ Rasm tahlil qilinmadi yoki javob olinmadi.")

    except Exception as e:
        logger.error(f".see buyrug'ida xatolik: {e}")
        await status_msg.edit(f"❌ Xatolik yuz berdi: {e}")

async def handle_ocr_command(event):
    """
    .ocr buyrug'i:
    Rasm yoki skrinshotdagi barcha matnlarni matn ko'rinishida ajratib beradi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Matnli rasm yoki hujjatga **javob (reply)** qilib `.ocr` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg or not (reply_msg.photo or (reply_msg.document and getattr(reply_msg.file, "mime_type", "").startswith("image/"))):
        msg = "⚠️ Siz javob bergan xabarda rasm topilmadi."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("📄 **Rasmdagi matnlar o'qilmoqda (OCR)...**")
    else:
        status_msg = await event.reply("📄 **Rasmdagi matnlar o'qilmoqda (OCR)...**")

    try:
        image_bytes = await event.client.download_media(reply_msg, file=bytes)
        if not image_bytes:
            await status_msg.edit("❌ Rasmni yuklab olish imkoni bo'lmadi.")
            return

        mime_type = "image/jpeg"
        if reply_msg.document and getattr(reply_msg.file, "mime_type", ""):
            mime_type = reply_msg.file.mime_type

        img_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        prompt = (
            "VAZIFA: Ushbu rasmdagi barcha yozuvlar, matnlar va jadvallarni aniq va to'liq ko'chirib yozing (OCR).\n"
            "Hech qanday qo'shimcha kirish yoki xulosa yozmang, faqat rasmdagi matnni o'zini bering."
        )

        ai_res = await call_gemini(
            contents=[img_part, prompt],
            temperature=0.1,
            max_output_tokens=2048
        )

        if ai_res:
            res_text = f"📄 **Rasmdan olingan matn (OCR):**\n\n{ai_res}"
            await status_msg.edit(res_text)
        else:
            await status_msg.edit("❌ Rasmdan matn ajratib olinmadi.")

    except Exception as e:
        logger.error(f".ocr buyrug'ida xatolik: {e}")
        await status_msg.edit(f"❌ Xatolik yuz berdi: {e}")
