import io
import logging
from PIL import Image
from telethon.tl.types import DocumentAttributeFilename

logger = logging.getLogger(__name__)

async def handle_sticker_command(event):
    """
    .sticker buyrug'i:
    Rasmga reply qilinsa, uni Telegram stiker formatiga (WebP) aylantiradi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Biror rasmga **javob (reply)** qilib `.sticker` deb yozing."
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
        status_msg = await event.edit("🖼 **Rasm stikerga aylantirilmoqda...**")
    else:
        status_msg = await event.reply("🖼 **Rasm stikerga aylantirilmoqda...**")

    try:
        image_bytes = await event.client.download_media(reply_msg, file=bytes)
        if not image_bytes:
            await status_msg.edit("❌ Rasmni yuklab olish imkoni bo'lmadi.")
            return

        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGBA")

        # Stiker uchun 512x512 ga moslashtirish (proporsiyani saqlagan holda)
        max_size = 512
        ratio = min(max_size / img.width, max_size / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=90)
        buffer.seek(0)
        buffer.name = "sticker.webp"

        await event.client.send_file(
            event.chat_id,
            buffer,
            attributes=[DocumentAttributeFilename("sticker.webp")],
            force_document=False
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f".sticker xatosi: {e}")
        await status_msg.edit(f"❌ Xatolik: {e}")

async def handle_unsticker_command(event):
    """
    .unsticker buyrug'i:
    Stikerga reply qilinsa, uni PNG rasmga aylantiradi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Biror stikerga **javob (reply)** qilib `.unsticker` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg or not reply_msg.sticker:
        msg = "⚠️ Siz javob bergan xabarda stiker topilmadi."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("📄 **Stiker rasmga aylantirilmoqda...**")
    else:
        status_msg = await event.reply("📄 **Stiker rasmga aylantirilmoqda...**")

    try:
        sticker_bytes = await event.client.download_media(reply_msg, file=bytes)
        if not sticker_bytes:
            await status_msg.edit("❌ Stikerni yuklab olish imkoni bo'lmadi.")
            return

        img = Image.open(io.BytesIO(sticker_bytes))
        img = img.convert("RGBA")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        buffer.name = "unsticker.png"

        await event.client.send_file(event.chat_id, buffer, force_document=True)
        await status_msg.delete()

    except Exception as e:
        logger.error(f".unsticker xatosi: {e}")
        await status_msg.edit(f"❌ Xatolik: {e}")
