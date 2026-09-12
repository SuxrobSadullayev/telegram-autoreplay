import re
import logging
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

logger = logging.getLogger(__name__)

async def handle_bio_command(event):
    """
    .bio <yangi bio matn> buyrug'i:
    Telegram profilining bio (tarjimayi hol) matnini yangilaydi.
    Bo'sh .bio bo'lsa joriy bioni ko'rsatadi.
    """
    raw = (event.raw_text or "").strip()
    new_bio = re.sub(r"^\.bio\s*", "", raw, flags=re.IGNORECASE).strip()

    if not new_bio and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            new_bio = reply_msg.raw_text.strip()

    if not new_bio:
        try:
            full = await event.client(
                __import__('telethon.tl.functions.users', fromlist=['GetFullUserRequest']).GetFullUserRequest(await event.client.get_me())
            )
            current_bio = getattr(full.full_user, "about", "") or ""
            if current_bio:
                msg = f"ℹ️ **Joriy bio:**\n\n`{current_bio}`"
            else:
                msg = "ℹ️ **Profilingizda bio o'rnatilmagan.**\nO'rnatish uchun: `.bio <matn>`"
        except Exception:
            msg = "ℹ️ **Qo'llanishi:** `.bio <yangi bio matn>`\nMisol: `.bio Dasturchi | O'zbekiston 🇺🇿`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("🔄 **Profil bio yangilanmoqda...**")
    else:
        status_msg = await event.reply("🔄 **Profil bio yangilanmoqda...**")

    try:
        await event.client(UpdateProfileRequest(about=new_bio))
        await status_msg.edit(f"✅ **Profil bio muvaffaqiyatli yangilandi:**\n\n`{new_bio}`")
    except Exception as e:
        logger.error(f".bio xatosi: {e}")
        await status_msg.edit(f"❌ Bio yangilashda xatolik: {e}")

async def handle_name_command(event):
    """
    .name <yangi ism> buyrug'i:
    Telegram profilining ism va familiyasini yangilaydi.
    """
    raw = (event.raw_text or "").strip()
    new_name = re.sub(r"^\.name\s*", "", raw, flags=re.IGNORECASE).strip()

    if not new_name:
        msg = "ℹ️ **Qo'llanishi:** `.name <Ism>` yoki `.name <Ism Familiya>`\nMisol: `.name Ali Valiyev`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    parts = new_name.split(maxsplit=1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""

    if event.out:
        status_msg = await event.edit("🔄 **Profil ismi yangilanmoqda...**")
    else:
        status_msg = await event.reply("🔄 **Profil ismi yangilanmoqda...**")

    try:
        await event.client(UpdateProfileRequest(first_name=first, last_name=last))
        full_display = f"{first} {last}".strip()
        await status_msg.edit(f"✅ **Profil ismi yangilandi:** `{full_display}`")
    except Exception as e:
        logger.error(f".name xatosi: {e}")
        await status_msg.edit(f"❌ Ism yangilashda xatolik: {e}")

async def handle_photo_command(event):
    """
    .photo buyrug'i (rasmga reply):
    Profil rasmini o'zgartiradi.
    """
    if not event.is_reply:
        msg = "ℹ️ **Qo'llanishi:** Rasmga **javob (reply)** qilib `.photo` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg or not (reply_msg.photo or (reply_msg.document and getattr(reply_msg.file, "mime_type", "").startswith("image/"))):
        msg = "⚠️ Javob berilgan xabarda rasm topilmadi."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("🔄 **Profil rasmi yangilanmoqda...**")
    else:
        status_msg = await event.reply("🔄 **Profil rasmi yangilanmoqda...**")

    try:
        photo_bytes = await event.client.download_media(reply_msg, file=bytes)
        if not photo_bytes:
            await status_msg.edit("❌ Rasmni yuklab olish imkoni bo'lmadi.")
            return

        uploaded_file = await event.client.upload_file(photo_bytes)
        await event.client(UploadProfilePhotoRequest(file=uploaded_file))
        await status_msg.edit("✅ **Profil rasmi muvaffaqiyatli o'zgartirildi!**")
    except Exception as e:
        logger.error(f".photo xatosi: {e}")
        await status_msg.edit(f"❌ Profil rasmini o'zgartirishda xatolik: {e}")
