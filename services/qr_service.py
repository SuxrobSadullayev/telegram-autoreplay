import io
import re
import logging
import qrcode
from google.genai import types
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

async def handle_qr_command(event):
    """
    .qr buyrug'i:
    - .qr <matn yoki havola> — QR-kod rasm hosil qilib yuboradi.
    - .qr (rasmga reply) — Rasmdagi QR-kodni o'qib beradi.
    """
    raw = (event.raw_text or "").strip()
    text_input = re.sub(r"^\.qr\s*", "", raw, flags=re.IGNORECASE).strip()

    # 1. Rasmga reply qilingan bo'lsa — QR-kodni o'qish
    if not text_input and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and (reply_msg.photo or (reply_msg.document and getattr(reply_msg.file, "mime_type", "").startswith("image/"))):
            if event.out:
                status_msg = await event.edit("🔍 **QR-kod o'qilmoqda...**")
            else:
                status_msg = await event.reply("🔍 **QR-kod o'qilmoqda...**")

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
                    "Ushbu rasmdagi QR-kod ichidagi matnni yoki havolani aniqlab bering. "
                    "Faqat QR-kod ichidagi ma'lumotni qaytaring, ortiqcha kirish yozmang."
                )

                result = await call_gemini(contents=[img_part, prompt], temperature=0.1, max_output_tokens=1024)
                if result:
                    await status_msg.edit(f"📱 **QR-kod ma'lumoti:**\n\n`{result}`")
                else:
                    await status_msg.edit("❌ QR-kodni o'qib bo'lmadi.")
            except Exception as e:
                logger.error(f".qr o'qish xatosi: {e}")
                await status_msg.edit(f"❌ Xatolik: {e}")
            return

    # 2. Matn yoki havola berilgan bo'lsa — QR-kod yaratish
    if not text_input:
        msg = (
            "ℹ️ **QR-Kod Qo'llanmasi:**\n\n"
            "• `.qr <matn yoki havola>` — QR-kod rasm yaratadi\n"
            "• `.qr` (rasmga reply) — Rasmdagi QR-kodni o'qiydi"
        )
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("⏳ **QR-kod yaratilmoqda...**")
    else:
        status_msg = await event.reply("⏳ **QR-kod yaratilmoqda...**")

    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(text_input)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        buffer.name = "qrcode.png"

        await event.client.send_file(
            event.chat_id,
            buffer,
            caption=f"📱 **QR-Kod:**\n`{text_input[:100]}`"
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f".qr yaratish xatosi: {e}")
        await status_msg.edit(f"❌ QR-kod yaratishda xatolik: {e}")
