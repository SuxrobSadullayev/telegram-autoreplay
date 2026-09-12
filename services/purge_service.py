import re
import asyncio
import logging
from telethon import TelegramClient

logger = logging.getLogger(__name__)

async def handle_del_command(event):
    """
    .del buyrug'i:
    Javob berilgan (reply qilingan) xabarni va buyruq xabarini o'chiradi.
    """
    if not event.is_reply:
        if event.out:
            await event.edit("⚠️ O'chirish uchun biror xabarga javob (reply) qiling.")
        else:
            await event.reply("⚠️ O'chirish uchun biror xabarga javob (reply) qiling.")
        return

    reply_msg = await event.get_reply_message()
    try:
        # Ikkala xabarni ham o'chiramiz
        await event.client.delete_messages(event.chat_id, [event.id, reply_msg.id])
    except Exception as e:
        logger.error(f".del xatosi: {e}")
        if event.out:
            await event.edit(f"❌ Xabarni o'chirib bo'lmadi: {e}")

async def handle_purge_command(event):
    """
    .purge <soni> buyrug'i:
    Chatdagi oxirgi N ta xabarni tozalaydi.
    Agar reply qilingan bo'lsa, o'sha xabargacha bo'lgan barcha xabarlarni o'chiradi.
    """
    raw = (event.raw_text or "").strip()
    match = re.search(r"^\.purge(?:\s+(\d+))?", raw, re.IGNORECASE)

    limit = 10
    if match and match.group(1):
        limit = int(match.group(1))
        limit = max(1, min(limit, 100))  # 1 tadan 100 tagacha cheklov

    try:
        messages_to_delete = []

        if event.is_reply:
            reply_msg = await event.get_reply_message()
            # Reply qilingan xabargacha bo'lgan barcha xabarlarni olamiz
            async for msg in event.client.iter_messages(
                event.chat_id,
                min_id=reply_msg.id - 1,
                max_id=event.id + 1
            ):
                messages_to_delete.append(msg.id)
                if len(messages_to_delete) >= limit:
                    break
        else:
            # So'nggi xabarlarni olamiz
            async for msg in event.client.iter_messages(event.chat_id, limit=limit + 1):
                messages_to_delete.append(msg.id)

        if messages_to_delete:
            await event.client.delete_messages(event.chat_id, messages_to_delete)
            notify = await event.client.send_message(
                event.chat_id,
                f"🧹 **{len(messages_to_delete)} ta xabar muvaffaqiyatli tozalandi.**"
            )
            # 3 soniyadan keyin ogohlantirish xabarini ham o'chiramiz
            await asyncio.sleep(3)
            await notify.delete()

    except Exception as e:
        logger.error(f".purge xatosi: {e}")
        try:
            await event.reply(f"❌ Xabarlarni tozalashda xatolik: {e}")
        except Exception:
            pass
