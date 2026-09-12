import re
import logging
from datetime import timezone, timedelta
from telethon.tl.types import (
    User,
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth
)

logger = logging.getLogger(__name__)

async def handle_seen_command(event):
    """
    .seen <username yoki ID> buyrug'i:
    Foydalanuvchining oxirgi marta onlayn bo'lgan vaqtini va holatini ko'rsatadi.
    """
    raw = (event.raw_text or "").strip()
    arg = re.sub(r"^\.seen\s*", "", raw, flags=re.IGNORECASE).strip()

    target = None
    if arg:
        if arg.isdigit() or (arg.startswith("-") and arg[1:].isdigit()):
            target = int(arg)
        else:
            target = arg
    elif event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg:
            target = reply_msg.sender_id

    if not target:
        msg = (
            "ℹ️ **Qo'llanishi:**\n"
            "• `.seen <username yoki ID>` (masalan: `.seen @durov`)\n"
            "• Yoki xabarga **javob (reply)** qilib `.seen` deb yozing."
        )
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    try:
        entity = await event.client.get_entity(target)
    except Exception as e:
        logger.error(f"Foydalanuvchi topilmadi ({target}): {e}")
        err_msg = f"❌ Foydalanuvchi topilmadi: `{target}`"
        if event.out:
            await event.edit(err_msg)
        else:
            await event.reply(err_msg)
        return

    if not isinstance(entity, User):
        msg = "⚠️ Ko'rsatilgan manzil shaxsiy profil emas (kanal yoki guruh)."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    first_name = entity.first_name or ""
    last_name = entity.last_name or ""
    full_name = f"{first_name} {last_name}".strip() or "Noma'lum"
    username = f"@{entity.username}" if entity.username else "Mavjud emas"
    user_id = entity.id

    status = entity.status
    status_text = "⚫ Holat aniqlanmadi (maxfiy sozlama)"

    if isinstance(status, UserStatusOnline):
        status_text = "🟢 Hozir onlayn!"
    elif isinstance(status, UserStatusOffline):
        if status.was_online:
            if status.was_online.tzinfo is None:
                uz_time = status.was_online.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=5)))
            else:
                uz_time = status.was_online.astimezone(timezone(timedelta(hours=5)))
            status_text = f"⚪ Oxirgi marta onlayn: `{uz_time.strftime('%Y-%m-%d %H:%M:%S')}`"
        else:
            status_text = "⚪ Oflayn"
    elif isinstance(status, UserStatusRecently):
        status_text = "🔵 Yaqinda onlayn bo'lgan"
    elif isinstance(status, UserStatusLastWeek):
        status_text = "🟡 Shu hafta ichida onlayn bo'lgan"
    elif isinstance(status, UserStatusLastMonth):
        status_text = "🟠 Shu oy ichida onlayn bo'lgan"

    response = (
        f"👤 **Foydalanuvchi:** {full_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"🔗 **Username:** {username}\n"
        f"📶 **Holat:** {status_text}"
    )

    if event.out:
        await event.edit(response)
    else:
        await event.reply(response)
