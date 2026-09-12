import io
import os
import re
import time
import asyncio
import logging
import subprocess
from PIL import Image
from db import BASE_DIR

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def handle_topdf_command(event):
    """
    .topdf buyrug'i:
    Rasmga reply qilinganda uni PDF hujjatga aylantiradi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Rasmga **javob (reply)** qilib `.topdf` deb yozing."
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
        status_msg = await event.edit("📄 **Rasm PDF ga aylantirilmoqda...**")
    else:
        status_msg = await event.reply("📄 **Rasm PDF ga aylantirilmoqda...**")

    try:
        img_bytes = await event.client.download_media(reply_msg, file=bytes)
        if not img_bytes:
            await status_msg.edit("❌ Rasmni yuklab olish imkoni bo'lmadi.")
            return

        img = Image.open(io.BytesIO(img_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        pdf_buffer = io.BytesIO()
        img.save(pdf_buffer, "PDF", resolution=100.0)
        pdf_buffer.seek(0)
        pdf_buffer.name = "converted.pdf"

        await event.client.send_file(event.chat_id, pdf_buffer, file_name="converted.pdf")
        await status_msg.delete()

    except Exception as e:
        logger.error(f".topdf xatosi: {e}")
        await status_msg.edit(f"❌ PDF ga aylantirishda xatolik: {e}")

async def handle_tomp3_command(event):
    """
    .tomp3 buyrug'i:
    Videoga reply qilinganda undan audioni MP3 formatida ajratib beradi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Videoga **javob (reply)** qilib `.tomp3` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg or not (reply_msg.video or reply_msg.video_note or (reply_msg.document and getattr(reply_msg.file, "mime_type", "").startswith("video/"))):
        msg = "⚠️ Siz javob bergan xabarda video topilmadi."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("🎵 **Videodan audio ajratilmoqda (MP3)...**")
    else:
        status_msg = await event.reply("🎵 **Videodan audio ajratilmoqda (MP3)...**")

    timestamp = int(time.time() * 1000)
    input_path = os.path.join(DOWNLOAD_DIR, f"input_{timestamp}.mp4")
    output_path = os.path.join(DOWNLOAD_DIR, f"output_{timestamp}.mp3")

    try:
        await event.client.download_media(reply_msg, file=input_path)
        if not os.path.exists(input_path):
            await status_msg.edit("❌ Videoni yuklab bo'lmadi.")
            return

        await asyncio.to_thread(
            subprocess.run,
            ["ffmpeg", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_path, "-y"],
            capture_output=True
        )

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            await status_msg.edit("❌ Videodan audio ajratib bo'lmadi.")
            return

        await event.client.send_file(event.chat_id, output_path, file_name="converted.mp3")
        await status_msg.delete()

    except Exception as e:
        logger.error(f".tomp3 xatosi: {e}")
        await status_msg.edit(f"❌ Xatolik: {e}")
    finally:
        for fpath in (input_path, output_path):
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
