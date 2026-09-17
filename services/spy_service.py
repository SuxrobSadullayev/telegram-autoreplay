import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from telethon.tl.functions.messages import GetMessageReadParticipantsRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import (
    ChannelParticipantsRecent,
    User,
    Channel,
)
from telethon.errors import ChatAdminRequiredError, MsgIdInvalidError

logger = logging.getLogger(__name__)

# O'zbekiston vaqt zonasi (UTC+5)
UZ_TZ = timezone(timedelta(hours=5))

# Monitor holatini saqlash
_monitor_tasks: dict[int, asyncio.Task] = {}


def _format_user(user) -> str:
    """Foydalanuvchi ma'lumotlarini chiroyli formatlaydi."""
    name = (user.first_name or "") + (" " + (user.last_name or "") if user.last_name else "")
    name = name.strip() or "Noma'lum"
    username = f"@{user.username}" if user.username else "username yo'q"
    bot_label = " 🤖" if getattr(user, "bot", False) else ""
    return f"  👤 **{name}** ({username}) `[ID: {user.id}]`{bot_label}"


def _format_time(dt) -> str:
    """Vaqtni O'zbekiston vaqtida formatlaydi."""
    if dt is None:
        return "noma'lum"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    uz_time = dt.astimezone(UZ_TZ)
    return uz_time.strftime("%Y-%m-%d %H:%M:%S")


async def _get_message_viewers(client, channel, msg_id: int) -> list:
    """Bitta xabarni kim o'qiganini aniqlaydi."""
    try:
        result = await client(GetMessageReadParticipantsRequest(
            peer=channel,
            msg_id=msg_id
        ))
        return result
    except MsgIdInvalidError:
        return []
    except ChatAdminRequiredError:
        raise
    except Exception as e:
        logger.warning(f"Xabar #{msg_id} ko'ruvchilarini olishda xatolik: {e}")
        return []


async def _resolve_channel(client, event, arg: str):
    """Kanal manzilini aniqlaydi (argument yoki joriy chat)."""
    if arg and not arg.isdigit() and arg != "monitor" and arg != "stop":
        try:
            entity = await client.get_entity(arg)
            if isinstance(entity, Channel):
                return entity
        except Exception:
            pass

    # Joriy chatni ishlatamiz
    try:
        entity = await event.get_chat()
        if isinstance(entity, Channel):
            return entity
    except Exception:
        pass

    return None


async def handle_spy_command(event):
    """
    .spy buyrug'i — kanaldagi xabarlarni kim ko'rayotganini aniqlaydi.

    Foydalanish:
      .spy                — oxirgi 5 xabar ko'ruvchilarini ko'rsatadi
      .spy <N>            — oxirgi N ta xabar ko'ruvchilarini ko'rsatadi (max 20)
      .spy monitor        — real-time monitoring ishga tushiradi
      .spy stop           — monitoringni to'xtatadi
    """
    raw = (event.raw_text or "").strip()
    args = re.sub(r"^\.spy\s*", "", raw, flags=re.IGNORECASE).strip()

    # Monitor buyruqlari
    if args.lower() == "stop":
        await _stop_monitor(event)
        return

    if args.lower() == "monitor":
        await _start_monitor(event)
        return

    # Nechta xabarni tekshirish kerak
    count = 5
    channel_arg = ""
    if args:
        parts = args.split()
        for part in parts:
            if part.isdigit():
                count = min(int(part), 20)
            else:
                channel_arg = part

    channel = await _resolve_channel(event.client, event, channel_arg)
    if not channel:
        msg = (
            "❌ **Bu buyruq faqat kanallarda ishlaydi!**\n\n"
            "ℹ️ Kanalingizga kirib, shu yerda `.spy` deb yozing.\n"
            "Yoki: `.spy @kanal_username`"
        )
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    # Yuklanmoqda xabarini ko'rsatamiz
    loading_msg = "🔍 **Kuzatuvchilar aniqlanmoqda...**"
    if event.out:
        await event.edit(loading_msg)
    else:
        loading_msg_obj = await event.reply(loading_msg)

    try:
        # Oxirgi xabarlarni olamiz
        messages = await event.client.get_messages(channel, limit=count)
        if not messages:
            result = "📭 Kanalda xabarlar topilmadi."
            if event.out:
                await event.edit(result)
            else:
                await loading_msg_obj.edit(result)
            return

        # Barcha ko'ruvchilarni yig'amiz
        all_viewer_ids = set()
        message_details = []

        for msg in messages:
            viewers = await _get_message_viewers(event.client, channel, msg.id)
            viewer_ids = set()
            viewer_times = {}

            for v in viewers:
                uid = v.user_id if hasattr(v, "user_id") else v
                viewer_ids.add(uid)
                all_viewer_ids.add(uid)
                if hasattr(v, "date") and v.date:
                    viewer_times[uid] = v.date

            msg_text = (msg.text or "")[:40]
            if len(msg.text or "") > 40:
                msg_text += "..."
            msg_date = _format_time(msg.date)

            message_details.append({
                "id": msg.id,
                "text": msg_text,
                "date": msg_date,
                "views": msg.views or 0,
                "viewer_ids": viewer_ids,
                "viewer_times": viewer_times,
            })

        # Foydalanuvchi ma'lumotlarini yuklaymiz
        users_map = {}
        me = await event.client.get_me()
        for uid in all_viewer_ids:
            try:
                user = await event.client.get_entity(uid)
                if isinstance(user, User):
                    users_map[uid] = user
            except Exception:
                pass

        # Natijani shakllantiramiz
        lines = [
            f"🕵️ **Kanal kuzatuvchilari — `{channel.title}`**",
            f"📊 Tekshirilgan xabarlar soni: **{len(messages)}**",
            ""
        ]

        # Umumiy noyob kuzatuvchilar
        unique_viewers = all_viewer_ids - {me.id}
        if unique_viewers:
            lines.append(f"👥 **Noyob kuzatuvchilar ({len(unique_viewers)} ta):**")
            for uid in unique_viewers:
                if uid in users_map:
                    lines.append(_format_user(users_map[uid]))
                else:
                    lines.append(f"  👤 Noma'lum foydalanuvchi `[ID: {uid}]`")
            lines.append("")
        else:
            lines.append("👥 **Sizdan boshqa hech kim ko'rmagan.**")
            lines.append("")

        # Har bir xabar tafsiloti
        lines.append("📋 **Xabar tafsilotlari:**")
        lines.append("")

        for detail in message_details:
            viewers_excl_me = detail["viewer_ids"] - {me.id}
            lines.append(
                f"📝 **#{detail['id']}** | 👁 {detail['views']} ko'rish | "
                f"📖 {len(viewers_excl_me)} kuzatuvchi"
            )
            lines.append(f"   📅 {detail['date']}")
            if detail["text"]:
                lines.append(f"   💬 _{detail['text']}_")

            if viewers_excl_me:
                for uid in viewers_excl_me:
                    time_str = ""
                    if uid in detail["viewer_times"]:
                        time_str = f" — ⏰ {_format_time(detail['viewer_times'][uid])}"
                    if uid in users_map:
                        lines.append(f"   {_format_user(users_map[uid])}{time_str}")
                    else:
                        lines.append(f"   👤 `[ID: {uid}]`{time_str}")
            else:
                lines.append("   _Sizdan boshqa hech kim ko'rmagan_")
            lines.append("")

        result = "\n".join(lines)

        if event.out:
            await event.edit(result)
        else:
            await loading_msg_obj.edit(result)

    except ChatAdminRequiredError:
        err = (
            "❌ **Admin huquqlari kerak!**\n\n"
            "Bu buyruq faqat siz admin bo'lgan kanallarda ishlaydi."
        )
        if event.out:
            await event.edit(err)
        else:
            await loading_msg_obj.edit(err)
    except Exception as e:
        logger.error(f"Spy buyrug'ida xatolik: {e}", exc_info=True)
        err = f"❌ **Xatolik yuz berdi:** `{e}`"
        if event.out:
            await event.edit(err)
        else:
            await loading_msg_obj.edit(err)


async def _start_monitor(event):
    """Kanalni real-time kuzatishni boshlaydi."""
    channel = await _resolve_channel(event.client, event, "")
    if not channel:
        msg = "❌ Bu buyruq faqat kanallarda ishlaydi!"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    chat_id = channel.id

    if chat_id in _monitor_tasks and not _monitor_tasks[chat_id].done():
        msg = "⚠️ **Bu kanal allaqachon kuzatilmoqda!**\nTo'xtatish uchun `.spy stop` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    msg = (
        f"🟢 **Real-time monitoring ishga tushdi!**\n"
        f"📡 Kanal: **{channel.title}**\n"
        f"⏱ Har 60 soniyada yangi ko'ruvchilar tekshiriladi.\n\n"
        f"To'xtatish uchun: `.spy stop`"
    )
    if event.out:
        await event.edit(msg)
    else:
        await event.reply(msg)

    task = asyncio.create_task(_monitor_loop(event.client, channel))
    _monitor_tasks[chat_id] = task


async def _stop_monitor(event):
    """Monitoringni to'xtatadi."""
    channel = await _resolve_channel(event.client, event, "")
    chat_id = channel.id if channel else event.chat_id

    if chat_id in _monitor_tasks and not _monitor_tasks[chat_id].done():
        _monitor_tasks[chat_id].cancel()
        del _monitor_tasks[chat_id]
        msg = "🔴 **Monitoring to'xtatildi.**"
    else:
        msg = "ℹ️ Bu kanalda faol monitoring topilmadi."

    if event.out:
        await event.edit(msg)
    else:
        await event.reply(msg)


async def _monitor_loop(client, channel):
    """Fon rejimida kanalni doimiy kuzatib turadi."""
    me = await client.get_me()
    known_viewers: dict[int, set] = {}  # msg_id -> set of viewer user_ids

    try:
        while True:
            try:
                messages = await client.get_messages(channel, limit=5)
                for msg in messages:
                    viewers = await _get_message_viewers(client, channel, msg.id)
                    current_ids = set()

                    for v in viewers:
                        uid = v.user_id if hasattr(v, "user_id") else v
                        if uid != me.id:
                            current_ids.add(uid)

                    prev_ids = known_viewers.get(msg.id, set())
                    new_ids = current_ids - prev_ids

                    if new_ids:
                        # Yangi kuzatuvchi topildi!
                        for uid in new_ids:
                            try:
                                user = await client.get_entity(uid)
                                user_info = _format_user(user) if isinstance(user, User) else f"ID: {uid}"
                            except Exception:
                                user_info = f"ID: `{uid}`"

                            msg_text = (msg.text or "")[:30]
                            alert = (
                                f"🚨 **Yangi kuzatuvchi aniqlandi!**\n\n"
                                f"📝 Xabar: #{msg.id} — _{msg_text}_\n"
                                f"👁 Umumiy ko'rishlar: {msg.views or 0}\n"
                                f"{user_info}\n"
                                f"⏰ {_format_time(datetime.now(UZ_TZ))}"
                            )

                            # Saved Messages ga xabar yuboramiz
                            await client.send_message("me", alert)

                    known_viewers[msg.id] = current_ids

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Monitor xatolik: {e}")

            await asyncio.sleep(60)

    except asyncio.CancelledError:
        logger.info(f"Kanal {channel.title} monitoringi to'xtatildi.")
