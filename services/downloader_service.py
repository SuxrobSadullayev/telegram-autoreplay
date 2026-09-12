import os
import re
import glob
import time
import asyncio
import logging
import yt_dlp
from telethon import TelegramClient
from db import BASE_DIR

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_REGEX = r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&//=]*"

def _sync_download_media(url: str, output_template: str) -> dict | None:
    """yt-dlp orqali media yuklab olish (sinxron worker)."""
    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "max_filesize": 50 * 1024 * 1024,  # Maksimal 50 MB
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
            title = info.get("title", "Video")
            duration = info.get("duration", 0)
            return {
                "title": title,
                "duration": duration,
            }
    except Exception as e:
        logger.error(f"yt-dlp yuklash xatosi: {e}")
        return None

async def handle_download_command(event):
    """
    .dl [url] buyrug'i:
    Instagram Reels, TikTok, YouTube Shorts va boshqa platformalardan videolarni yuklab beradi.
    """
    raw = (event.raw_text or "").strip()
    url = None

    # Buyruq matnidan URL qidiramiz
    url_match = re.search(URL_REGEX, raw)
    if url_match:
        url = url_match.group(0)

    # Agar buyruq matnida bo'lmasa, reply qilingan xabardan qidiramiz
    if not url and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            url_match = re.search(URL_REGEX, reply_msg.raw_text)
            if url_match:
                url = url_match.group(0)

    if not url:
        usage = (
            "📥 **Media Yuklovchi (.dl) Qo'llanmasi:**\n\n"
            "• `.dl <havola>` (Instagram, TikTok, YouTube Shorts, Twitter va h.k.)\n"
            "• Yoki havolali xabarga **javob (reply)** qilib `.dl` deb yozing.\n\n"
            "Misol: `.dl https://www.instagram.com/reel/...`"
        )
        if event.out:
            await event.edit(usage)
        else:
            await event.reply(usage)
        return

    if event.out:
        status_msg = await event.edit("⏳ **Video yuklab olinmoqda, iltimos kuting...**")
    else:
        status_msg = await event.reply("⏳ **Video yuklab olinmoqda, iltimos kuting...**")

    timestamp = int(time.time() * 1000)
    out_prefix = os.path.join(DOWNLOAD_DIR, f"vid_{timestamp}")
    out_template = f"{out_prefix}.%(ext)s"

    try:
        info = await asyncio.to_thread(_sync_download_media, url, out_template)

        # Yuklangan faylni topamiz
        found_files = glob.glob(f"{out_prefix}.*")
        if not found_files or not os.path.exists(found_files[0]):
            await status_msg.edit("❌ Videoni yuklab bo'lmadi (havola yopiq, o'chirilgan yoki hajmi 50 MB dan katta).")
            return

        downloaded_file = found_files[0]
        file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)

        if file_size_mb > 50:
            await status_msg.edit(f"⚠️ Video hajmi juda katta ({file_size_mb:.1f} MB). Maksimal ruxsat etilgan hajm: 50 MB.")
            os.remove(downloaded_file)
            return

        await status_msg.edit("📤 **Video Telegramga yuklanmoqda...**")

        caption = f"🎬 **{info.get('title', 'Video')}**\n🔗 [Manba havolasi]({url})"
        await event.client.send_file(
            event.chat_id,
            downloaded_file,
            caption=caption,
            supports_streaming=True,
            reply_to=event.reply_to_msg_id if event.is_reply else None
        )

        # Holat xabarini tozalaymiz
        await status_msg.delete()

        # Vaqtinchalik faylni o'chiramiz
        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)

    except Exception as e:
        logger.error(f".dl komandasi xatosi: {e}")
        await status_msg.edit(f"❌ Xatolik yuz berdi: {e}")
        # Har ehtimolga qarshi tozalaymiz
        for f in glob.glob(f"{out_prefix}.*"):
            try:
                os.remove(f)
            except Exception:
                pass
