import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from telethon.tl.functions.messages import (
    GetMessageReadParticipantsRequest,
    GetMessageReactionsListRequest,
)
from telethon.tl.functions.channels import (
    GetParticipantsRequest,
    GetFullChannelRequest,
    GetAdminLogRequest,
    GetParticipantRequest,
)
from telethon.tl.types import (
    ChannelParticipantsSearch,
    ChannelAdminLogEventsFilter,
    User,
    Channel,
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
)
from telethon.errors import (
    ChatAdminRequiredError,
    MsgIdInvalidError,
    ChannelPrivateError,
    UserNotParticipantError,
)

logger = logging.getLogger(__name__)

# O'zbekiston vaqt zonasi (UTC+5)
UZ_TZ = timezone(timedelta(hours=5))

# Monitor holatini saqlash
_monitor_tasks: dict[int, asyncio.Task] = {}


def _format_user(user) -> str:
    """Foydalanuvchi ma'lumotlarini chiroyli formatlaydi."""
    if not user:
        return "Noma'lum profil"
    name = (getattr(user, "first_name", "") or "") + (" " + (getattr(user, "last_name", "") or "") if getattr(user, "last_name", None) else "")
    name = name.strip() or "Noma'lum"
    username = f"@{user.username}" if getattr(user, "username", None) else "username yo'q"
    bot_label = " 🤖" if getattr(user, "bot", False) else ""
    premium = " ⭐" if getattr(user, "premium", False) else ""
    scam = " ⚠️ SCAM" if getattr(user, "scam", False) else ""
    fake = " 🚫 FAKE" if getattr(user, "fake", False) else ""
    deleted = " 🗑 O'CHIRILGAN" if getattr(user, "deleted", False) else ""
    return f"👤 **{name}** ({username}) `[ID: {user.id}]`{bot_label}{premium}{scam}{fake}{deleted}"


def _format_user_status(status) -> str:
    """Foydalanuvchining onlayn holatini chiroyli formatlaydi."""
    if isinstance(status, UserStatusOnline):
        return "🟢 Hozir onlayn"
    elif isinstance(status, UserStatusOffline):
        dt = getattr(status, "was_online", None)
        return f"⚪ Oxirgi marta onlayn: {_format_time(dt)}"
    elif isinstance(status, UserStatusRecently):
        return "⚪ Yaqinda onlayn bo'lgan"
    elif isinstance(status, UserStatusLastWeek):
        return "⚪ Shu hafta onlayn bo'lgan"
    elif isinstance(status, UserStatusLastMonth):
        return "⚪ Shu oy onlayn bo'lgan"
    return "⚪ Noma'lum"


def _format_time(dt) -> str:
    """Vaqtni O'zbekiston vaqtida formatlaydi."""
    if dt is None:
        return "noma'lum"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    uz_time = dt.astimezone(UZ_TZ)
    return uz_time.strftime("%Y-%m-%d %H:%M:%S")


async def _get_channel_participants(client, channel) -> list:
    """Kanaldagi BARCHA rasmiy obunachillarni oladi."""
    all_participants = []
    offset = 0
    limit = 200

    while True:
        try:
            result = await client(GetParticipantsRequest(
                channel=channel,
                filter=ChannelParticipantsSearch(""),
                offset=offset,
                limit=limit,
                hash=0
            ))
            if not result.users:
                break
            all_participants.extend(result.users)
            offset += len(result.users)
            if len(result.users) < limit:
                break
        except Exception as e:
            logger.warning(f"Obunachillarni olishda xatolik: {e}")
            break

    return all_participants


async def _get_admin_log(client, channel, max_events=50) -> list:
    """Kanal admin logini oladi (kim qo'shilgan, chiqgan va h.k.)."""
    events_list = []
    try:
        result = await client(GetAdminLogRequest(
            channel=channel,
            q="",
            min_id=0,
            max_id=0,
            limit=max_events,
            events_filter=ChannelAdminLogEventsFilter(
                join=True,
                leave=True,
                invite=True,
                ban=True,
                kick=True,
            ),
            admins=[]
        ))
        events_list = result.events
    except ChatAdminRequiredError:
        logger.info("Admin log uchun admin huquqlari kerak.")
    except Exception as e:
        logger.warning(f"Admin logni olishda xatolik: {e}")

    return events_list


async def _get_message_viewers(client, channel, msg_id: int) -> list:
    """Bitta xabarni kim o'qiganini aniqlaydi (faqat kichik guruhlar uchun MTProto)."""
    try:
        result = await client(GetMessageReadParticipantsRequest(
            peer=channel,
            msg_id=msg_id
        ))
        return result
    except (MsgIdInvalidError, ChatAdminRequiredError):
        return []
    except Exception as e:
        logger.debug(f"Xabar #{msg_id} ko'ruvchilarini olishda: {e}")
        return []


async def _get_message_reactions(client, channel, msg_id: int) -> list:
    """
    Xabarga reaksiya qoldirgan barcha foydalanuvchilar ro'yxatini oladi.
    Kanalga a'zo bo'lmagan shaxslar ham bu yerda ko'rinadi!
    """
    try:
        res = await client(GetMessageReactionsListRequest(
            peer=channel,
            id=msg_id,
            limit=100
        ))
        users_map = {u.id: u for u in getattr(res, "users", []) if isinstance(u, User)}
        reactions_data = []
        for r in getattr(res, "reactions", []):
            uid = None
            if hasattr(r, "peer_id"):
                uid = getattr(r.peer_id, "user_id", None) or getattr(r.peer_id, "channel_id", None)
            user_obj = users_map.get(uid)
            emoji = "?"
            if hasattr(r, "reaction"):
                if hasattr(r.reaction, "emoticon"):
                    emoji = r.reaction.emoticon
                elif hasattr(r.reaction, "document_id"):
                    emoji = "⭐"
            date = getattr(r, "date", None)
            reactions_data.append({
                "user_id": uid,
                "user": user_obj,
                "emoji": emoji,
                "date": date,
            })
        return reactions_data
    except Exception as e:
        logger.debug(f"Reaksiyalarni olishda xatolik #{msg_id}: {e}")
        return []


async def _resolve_channel(client, event, arg: str):
    """Kanal manzilini aniqlaydi."""
    if arg and not arg.isdigit() and arg not in ("monitor", "stop", "trap", "tuzoq", "check"):
        try:
            entity = await client.get_entity(arg)
            if isinstance(entity, Channel):
                return entity
        except Exception:
            pass

    try:
        entity = await event.get_chat()
        if isinstance(entity, Channel):
            return entity
    except Exception:
        pass

    return None


async def handle_spy_command(event):
    """
    .spy buyrug'i — kanaldagi obunachilar va yashirin kuzatuvchilarni aniqlash moduli.

    Foydalanish:
      .spy                 — obunachilar, admin log va oxirgi postlar tahlili
      .spy <N>             — oxirgi N ta post va reaksiyalar tahlili (max 20)
      .spy check <user>    — gumondor shaxsning kanaldagi izlarini tekshirish
      .spy trap            — yashirin kuzatuvchilarni fosh qiluvchi tuzoq qo'llanmasi
      .spy monitor         — real-time kuzatuvni ishga tushirish (Saved Messages)
      .spy stop            — monitoringni to'xtatish
    """
    raw = (event.raw_text or "").strip()
    args = re.sub(r"^\.spy\s*", "", raw, flags=re.IGNORECASE).strip()

    # 1. Stop buyrug'i
    if args.lower() == "stop":
        await _stop_monitor(event)
        return

    # 2. Monitor buyrug'i
    if args.lower() == "monitor":
        await _start_monitor(event)
        return

    # 3. Tuzoq (Honeypot) yo'riqnomasi
    if args.lower() in ("trap", "tuzoq"):
        await _handle_spy_trap(event)
        return

    # 4. Maxsus shaxsni tekshirish (Check)
    if args.lower().startswith("check"):
        check_args = re.sub(r"^check\s*", "", args, flags=re.IGNORECASE).strip()
        await _handle_spy_check(event, check_args)
        return

    # 5. Umumiy tahlil
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
            "❌ **Kanal aniqlanmadi!**\n\n"
            "ℹ️ Ushbu buyruqni kanalingiz ichida yozing yoki kanal usernamesini ko'rsating:\n"
            "Masalan: `.spy @kanalingiz` yoki kanalda to'g'ridan-to'g'ri `.spy`\n\n"
            "Boshqa imkoniyatlar:\n"
            "• `.spy check @username` — Shubhali shaxsni tekshirish\n"
            "• `.spy trap` — Yashirin kuzatuvchilarni fosh qilish tuzog'i\n"
            "• `.spy monitor` — Real-time monitoring"
        )
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    # Yuklanmoqda xabari
    loading_msg = "🔍 **Kanal va kuzatuvchilar tahlil qilinmoqda...**"
    sent_msg = None
    if event.out:
        await event.edit(loading_msg)
    else:
        sent_msg = await event.reply(loading_msg)

    try:
        me = await event.client.get_me()

        # ========== 1. KANAL MA'LUMOTLARI ==========
        lines = [
            f"🕵️ **Kanal Tahlili — `{channel.title}`**",
            f"🆔 Kanal ID: `{channel.id}`",
        ]

        if channel.username:
            lines.append(f"🔗 Manzil: @{channel.username} (Ochiq / Public kanal)")
        else:
            lines.append("🔒 Manzil: Yopiq kanal (Private)")

        # To'liq ma'lumot
        try:
            full_channel = await event.client(GetFullChannelRequest(channel=channel))
            full = full_channel.full_chat
            lines.append(f"👥 Rasmiy a'zolar soni: **{full.participants_count or 0}**")
            if hasattr(full, "online_count") and full.online_count:
                lines.append(f"🟢 Hozir onlayn: **{full.online_count}**")
        except Exception as e:
            logger.warning(f"Kanal to'liq ma'lumotida xatolik: {e}")

        lines.append("")

        # ========== 2. BARCHA RASMIY OBUNACHILLAR ==========
        participants = await _get_channel_participants(event.client, channel)
        participants_ids = {u.id for u in participants}

        other_users = []
        bots = []
        for user in participants:
            if user.id == me.id:
                continue
            if isinstance(user, User):
                if user.bot:
                    bots.append(user)
                else:
                    other_users.append(user)

        lines.append(f"👥 **Rasmiy a'zolar ({len(other_users)} odam, {len(bots)} bot):**")
        if other_users:
            for user in other_users[:25]:
                user_line = f"  {_format_user(user)}"
                if hasattr(user, "phone") and user.phone:
                    user_line += f" | 📱 +{user.phone}"
                lines.append(user_line)
            if len(other_users) > 25:
                lines.append(f"  _...va yana {len(other_users) - 25} ta foydalanuvchi_")
        else:
            lines.append("  _Kanalda sizdan boshqa rasmiy obunachi yo'q._")

        if bots:
            lines.append(f"  🤖 Botlar: {', '.join(f'@{b.username}' for b in bots if b.username) or len(bots)}")

        lines.append("")

        # ========== 3. ADMIN LOG — KIRIB-CHIQGANLAR ==========
        lines.append("📋 **Admin Log — So'nggi harakatlar (Kirgan/Chiqganlar):**")
        admin_events = await _get_admin_log(event.client, channel, max_events=40)

        suspicious_lurkers = []
        if admin_events:
            for ev in admin_events[:12]:
                event_time = _format_time(ev.date)
                user_id = ev.user_id

                user_str = f"ID: `{user_id}`"
                try:
                    user = await event.client.get_entity(user_id)
                    if isinstance(user, User):
                        user_str = _format_user(user)
                except Exception:
                    pass

                action_class = type(ev.action).__name__

                if "Join" in action_class:
                    lines.append(f"  🟢 {event_time} — {user_str} **qo'shildi**")
                elif "Leave" in action_class:
                    lines.append(f"  🔴 {event_time} — {user_str} **chiqib ketdi**")
                    if user_id not in participants_ids and user_id != me.id:
                        suspicious_lurkers.append((user_str, event_time))
                elif "Invite" in action_class:
                    lines.append(f"  📩 {event_time} — {user_str} **taklif qilindi**")
                elif "Kick" in action_class or "Ban" in action_class:
                    lines.append(f"  🚫 {event_time} — {user_str} **chetlashtirildi**")
        else:
            lines.append("  _Admin log ma'lumotlari topilmadi (admin huquqlari kerak)._")

        lines.append("")

        # ========== 4. OXIRGI XABARLAR VA REAKSIYALAR ==========
        lines.append(f"📊 **Oxirgi {count} xabar tahlili va Reaksiyalar:**")
        lines.append("")

        messages = await event.client.get_messages(channel, limit=count)
        lurker_reactions_found = []

        for msg in messages:
            msg_text = (msg.text or "")[:35]
            if len(msg.text or "") > 35:
                msg_text += "..."
            msg_date = _format_time(msg.date)
            views = msg.views or 0
            forwards = msg.forwards or 0

            lines.append(f"📝 **#{msg.id}** | 👁 **{views}** ko'rish | 🔄 {forwards} forward | 📅 {msg_date}")
            if msg_text:
                lines.append(f"   💬 _{msg_text}_")

            # 4.1. Reaksiyalarni tekshirish (Kanalga a'zo bo'lmay reaksiya bosganlar!)
            reactions = await _get_message_reactions(event.client, channel, msg.id)
            if reactions:
                lines.append("   ❤️ **Reaksiya qoldirganlar:**")
                for r in reactions:
                    uid = r["user_id"]
                    user_obj = r["user"]
                    emoji = r["emoji"]
                    r_time = _format_time(r["date"]) if r["date"] else ""

                    if uid == me.id:
                        continue

                    # Profil matni
                    if user_obj:
                        user_desc = _format_user(user_obj)
                    else:
                        user_desc = f"👤 ID: `{uid}`"

                    # Obunachimi yoki obunasiz kuzatuvchimi?
                    if uid not in participants_ids:
                        lines.append(f"     🚨 **[OBUNASIZ KUZATUVCHI]** {emoji} {user_desc} ⏰ {r_time}")
                        lurker_reactions_found.append((user_desc, emoji, msg.id))
                    else:
                        lines.append(f"     ✅ {emoji} {user_desc} ⏰ {r_time}")

            # 4.2. Kichik guruh bo'lsa o'qiganlar
            viewers = await _get_message_viewers(event.client, channel, msg.id)
            real_viewers = [v for v in viewers if (v.user_id if hasattr(v, "user_id") else v) != me.id]
            if real_viewers:
                lines.append(f"   📖 O'qiganlar ({len(real_viewers)}):")
                for v in real_viewers:
                    uid = v.user_id if hasattr(v, "user_id") else v
                    lines.append(f"     👤 ID: `{uid}`")

            lines.append("")

        # ========== 5. PROFESSIONAL XULOSA VA TAVSIYA ==========
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 **PROFESSIONAL XULOSA VA TUSHUNTIRISH:**")

        if lurker_reactions_found:
            lines.append(f"🚨 **Diqqat! {len(lurker_reactions_found)} ta postda kanalga a'zo bo'lmagan kuzatuvchilar reaksiyasi aniqlandi!**")
            for udesc, em, mid in lurker_reactions_found:
                lines.append(f"  • Post #{mid}: {em} — {udesc}")
            lines.append("")

        if suspicious_lurkers:
            lines.append("⚠️ **Kanalga kirib, o'qib, yana chiqib ketganlar (Admin Log):**")
            for udesc, t in suspicious_lurkers[:5]:
                lines.append(f"  • {udesc} (Chiqgan vaqti: {t})")
            lines.append("")

        lines.append(
            "📌 **Nega Telegram oddiy ko'rishlar (`views`) bo'yicha shaxs nomini bermaydi?**\n"
            "Telegram MTProto arxitekturasida kanallar (Broadcast Channels) ommaviy axborot vositasi hisoblanadi. "
            "Ko'rishlar soni faqat serverdagi umumiy hisoblagich (`views: int`) bo'lib, xabarni kim shunchaki ochib ko'rganining "
            "profil ma'lumotlarini Telegram serverlari **MAXFIYLIK SIYOSATI** sababli umuman saqlamaydi va hechkashga taqdim etmaydi.\n\n"
            "🎯 **Kuzatuvchilarni aniqlashning 100% samarali usullari:**\n"
            "1️⃣ `.spy check @username` — Gumondor shaxsni to'liq skanerlash\n"
            "2️⃣ `.spy trap` — Postga bot/tuzoq havola qo'yib, kirganlarni 100% fosh qilish\n"
            "3️⃣ Kanalni **Private** qilib, faqat **Join Requests (ariza bilan kirish)** ga o'tkazish. "
            "Shunda obuna bo'lmagan hech kim xabarlarni o'qiy olmaydi!"
        )

        result = "\n".join(lines)

        # Telegram xabar uzunligi cheklovi (4096 belgi)
        if len(result) > 4096:
            parts = []
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > 3900:
                    parts.append(current)
                    current = line
                else:
                    current += "\n" + line if current else line
            if current:
                parts.append(current)

            if event.out:
                await event.edit(parts[0])
            else:
                await sent_msg.edit(parts[0])

            for part in parts[1:]:
                await event.client.send_message(channel, part)
        else:
            if event.out:
                await event.edit(result)
            else:
                await sent_msg.edit(result)

    except ChatAdminRequiredError:
        err = "❌ **Admin huquqlari yetarli emas!**\nAdmin log va a'zolar ro'yxatini olish uchun kanalda administrator huquqlari kerak."
        if event.out:
            await event.edit(err)
        else:
            await sent_msg.edit(err)
    except ChannelPrivateError:
        err = "❌ **Kanalga kirish imkoni yo'q (private yoki bloklangan).**"
        if event.out:
            await event.edit(err)
        else:
            await sent_msg.edit(err)
    except Exception as e:
        logger.error(f"Spy buyrug'ida xatolik: {e}", exc_info=True)
        err = f"❌ **Xatolik yuz berdi:** `{e}`"
        if event.out:
            await event.edit(err)
        else:
            await sent_msg.edit(err)


async def _handle_spy_check(event, target_arg: str):
    """
    Shubhali shaxsni kanal bo'yicha tekshiradi:
    - Obunachimi?
    - Admin logda (kirib chiqqanlar) bormi?
    - So'nggi postlarga reaksiya qoldirganmi?
    - Onlayn holati va profil tafsilotlari.
    """
    if not target_arg:
        msg = (
            "❌ **Tekshirilishi kerak bo'lgan profilni kiriting!**\n\n"
            "Foydalanish:\n"
            "• `.spy check @username`\n"
            "• `.spy check 123456789` (User ID)"
        )
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    channel = await _resolve_channel(event.client, event, "")
    if not channel:
        msg = "❌ **Kanal aniqlanmadi!**\nUshbu buyruqni kanalingiz ichida yozing: `.spy check @username`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    loading = f"🔍 `{target_arg}` profilining kanaldagi izlari tekshirilmoqda..."
    if event.out:
        await event.edit(loading)
    else:
        sent_msg = await event.reply(loading)

    try:
        # Foydalanuvchini topish
        target_entity = None
        try:
            if target_arg.isdigit():
                target_entity = await event.client.get_entity(int(target_arg))
            else:
                target_entity = await event.client.get_entity(target_arg)
        except Exception as e:
            err = f"❌ **Foydalanuvchi topilmadi:** `{target_arg}` (`{e}`)"
            if event.out:
                await event.edit(err)
            else:
                await sent_msg.edit(err)
            return

        if not isinstance(target_entity, User):
            err = "❌ Ko'rsatilgan manzil shaxsiy profil emas!"
            if event.out:
                await event.edit(err)
            else:
                await sent_msg.edit(err)
            return

        user_info = _format_user(target_entity)
        status_info = _format_user_status(target_entity.status) if hasattr(target_entity, "status") else "⚪ Noma'lum"

        lines = [
            "🕵️ **KUZATUVCHI AUDITI — NATIJA**",
            f"📡 Kanal: **{channel.title}**",
            f"🎯 Gumondor: {user_info}",
            f"📶 Holati: {status_info}",
            "",
        ]

        # 1. Obunachi ekanligini tekshirish
        is_subscriber = False
        sub_role = "A'zo emas"
        try:
            p_res = await event.client(GetParticipantRequest(channel=channel, participant=target_entity))
            is_subscriber = True
            part = p_res.participant
            part_class = type(part).__name__
            if "Admin" in part_class or "Creator" in part_class:
                sub_role = "⭐️ Administrator / Egasi"
            else:
                sub_role = "✅ Rasmiy a'zo (Obunachi)"
        except UserNotParticipantError:
            is_subscriber = False
            sub_role = "❌ Kanalga a'zo EMAS"
        except Exception as e:
            sub_role = f"Noma'lum (`{e}`)"

        lines.append(f"📌 **Kanalga a'zoligi:** {sub_role}")

        # 2. Admin Logda tekshirish (oxirgi 48 soat)
        admin_events = await _get_admin_log(event.client, channel, max_events=100)
        user_log_events = [ev for ev in admin_events if ev.user_id == target_entity.id]

        if user_log_events:
            lines.append(f"📋 **Admin Logdagi faoliyati ({len(user_log_events)} ta hodisa):**")
            for ev in user_log_events[:5]:
                act_name = type(ev.action).__name__
                dt_str = _format_time(ev.date)
                lines.append(f"  • {dt_str} — `{act_name}`")
        else:
            lines.append("📋 **Admin Log:** So'nggi 48 soatda kirish/chiqish qayd etilmagan.")

        lines.append("")

        # 3. Oxirgi 15 ta postdagi reaksiyalarini qidirish
        messages = await event.client.get_messages(channel, limit=15)
        found_reactions = []

        for msg in messages:
            reactions = await _get_message_reactions(event.client, channel, msg.id)
            for r in reactions:
                if r["user_id"] == target_entity.id:
                    found_reactions.append({
                        "msg_id": msg.id,
                        "emoji": r["emoji"],
                        "date": r["date"],
                    })

        if found_reactions:
            lines.append(f"❤️ **Reaksiyalardagi izlari ({len(found_reactions)} ta):**")
            for fr in found_reactions:
                dt_str = _format_time(fr["date"]) if fr["date"] else ""
                lines.append(f"  • Post #{fr['msg_id']}: {fr['emoji']} (⏰ {dt_str})")
        else:
            lines.append("❤️ **Reaksiyalar:** So'nggi 15 ta postga reaksiya qoldirmagan.")

        lines.append("")

        # 4. Xulosa
        lines.append("🔎 **Xulosa:**")
        if not is_subscriber and (found_reactions or user_log_events):
            lines.append(
                "🚨 **GUMONDOR ANIQ KUZATUVCHI!**\n"
                "Ushbu shaxs kanalga **a'zo bo'lmagan holda** postlarga reaksiya qoldirgan yoki kanalga kirib-chiqqan!"
            )
        elif not is_subscriber:
            lines.append(
                "ℹ️ Ushbu shaxs hozirda kanalga a'zo emas. Agar u postlarni o'qiyotgan bo'lsa, "
                "buni faqat ochiq kanal havolasi orqali yashirin ko'rmoqda yoki postlar unga forward qilinmoqda.\n"
                "Uni fosh qilish uchun `.spy trap` (tuzoq) usulidan foydalaning."
            )
        else:
            lines.append("✅ Ushbu shaxs rasmiy obunachilar safida mavjud.")

        final_msg = "\n".join(lines)
        if event.out:
            await event.edit(final_msg)
        else:
            await sent_msg.edit(final_msg)

    except Exception as e:
        logger.error(f"Spy check xatolik: {e}", exc_info=True)
        err = f"❌ **Tekshirishda xatolik:** `{e}`"
        if event.out:
            await event.edit(err)
        else:
            await sent_msg.edit(err)


async def _handle_spy_trap(event):
    """Kuzatuvchilarni fosh qilish bo'yicha Tuzoq (Honeypot) qo'llanmasi."""
    text = (
        "🪤 **OBUNASIZ KUZATUVCHILARNI 100% FOSH QILISH (TUZOOQ USULI)**\n\n"
        "Telegram serverlari shunchaki postni ko'rgan odamning profilini oshkor qilmaydi. "
        "Ammo professional xavfsizlik va OSINT'da quyidagi **2 ta tuzoq usuli** orqali kuzatuvchi 100% aniqlanadi:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ **Telegram Bot orqali Tuzoq (Eng oson va 100% aniq):**\n"
        "• `@BotFather` orqali kichik bot yarating (masalan, `@KanalBonusBot` yoki `@Fayllar_Bot`).\n"
        "• Kanalingizga qiziqarli post qo'ying va oxiriga tuzoq havola yozing:\n"
        "  _«Ushbu loyihaning to'liq kodini yuklab olish uchun bosing:»_\n"
        "  👉 `https://t.me/SizningBotingiz?start=track_post12`\n"
        "• Kuzatuvchi postni o'qib, qiziqib shu tugmaga bosishi bilanoq botga `/start track_post12` xabari boradi.\n"
        "• Bot darhol o'sha odamning: **Ismi, Familiyasi, Username, User ID va Hatto Telefonini** sizga yuboradi!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "2️⃣ **Veb-sayt / Tashqi havola orqali IP Tuzoq:**\n"
        "• Havola qisqartiruvchi servis (masalan, `grabify.link`) orqali tuzoq link yarating.\n"
        "• Postga havola sifatida joylashtiring.\n"
        "• Havolaga kirgan shaxsning: **IP manzili, Shahri, Internet provayderi (Ucell, Uztelecom...), Qurilmasi (iPhone/Android)** fosh bo'ladi.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "3️⃣ **Kanalni Himoyalash (Kuzatuvchilarni butunlay to'xtatish):**\n"
        "• Kanal sozlamalariga kiring: Kanal turi -> **Private (Yopiq)** qiling.\n"
        "• **«Tasdiqlash bilan qo'shilish» (Request to join)** rejimini yoqing.\n"
        "• Shunda obuna bo'lmagan hech kim postlarni o'qiy olmaydi!"
    )
    if event.out:
        await event.edit(text)
    else:
        await event.reply(text)


async def _start_monitor(event):
    """Kanalni real-time kuzatishni boshlaydi."""
    channel = await _resolve_channel(event.client, event, "")
    if not channel:
        msg = "❌ Ushbu buyruqni kanalingiz ichida yozing: `.spy monitor`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    chat_id = channel.id

    if chat_id in _monitor_tasks and not _monitor_tasks[chat_id].done():
        msg = "⚠️ **Ushbu kanal allaqachon kuzatilmoqda!**\nTo'xtatish uchun: `.spy stop`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    msg = (
        f"🟢 **Real-time monitoring ishga tushdi!**\n"
        f"📡 Kanal: **{channel.title}**\n\n"
        f"Kuzatiladigan hodisalar:\n"
        f"  📊 Yangi ko'rishlar (views o'zgarishi)\n"
        f"  🧑 Yangi obunachilar\n"
        f"  🔴 Obunadan chiqganlar\n"
        f"  🚨 Kanalga obunasiz reaksiya qoldirganlar\n\n"
        f"⏱ Har 45 soniyada tekshiriladi.\n"
        f"🔔 Signallar **Saved Messages (Saqlangan xabarlar)**ga keladi.\n\n"
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
        msg = "🔴 **Monitoring muvaffaqiyatli to'xtatildi.**"
    else:
        msg = "ℹ️ Ushbu kanalda faol monitoring topilmadi."

    if event.out:
        await event.edit(msg)
    else:
        await event.reply(msg)


async def _monitor_loop(client, channel):
    """Fon rejimida kanalni doimiy kuzatib turadi."""
    me = await client.get_me()

    known_participants: set = set()
    known_views: dict[int, int] = {}
    known_reaction_users: dict[int, set] = {}

    # Boshlang'ich obunachilarni olamiz
    try:
        initial_participants = await _get_channel_participants(client, channel)
        known_participants = {u.id for u in initial_participants}
    except Exception as e:
        logger.warning(f"Monitor: boshlang'ich obunachilarda xatolik: {e}")

    # Boshlang'ich ko'rishlar va reaksiyalarni olamiz
    try:
        messages = await client.get_messages(channel, limit=10)
        for msg in messages:
            known_views[msg.id] = msg.views or 0
            reactions = await _get_message_reactions(client, channel, msg.id)
            known_reaction_users[msg.id] = {r["user_id"] for r in reactions if r["user_id"]}
    except Exception:
        pass

    try:
        while True:
            try:
                # 1. Obunachilardagi o'zgarishlar
                current_participants_list = await _get_channel_participants(client, channel)
                current_ids = {u.id for u in current_participants_list}
                users_map = {u.id: u for u in current_participants_list if isinstance(u, User)}

                # Yangi obunachilar
                new_ids = current_ids - known_participants - {me.id}
                for uid in new_ids:
                    user_info = _format_user(users_map[uid]) if uid in users_map else f"ID: `{uid}`"
                    alert = (
                        f"🟢 **Yangi obunachi aniqlandi!**\n"
                        f"📡 Kanal: **{channel.title}**\n"
                        f"{user_info}\n"
                        f"⏰ {_format_time(datetime.now(UZ_TZ))}"
                    )
                    await client.send_message("me", alert)

                # Chiqib ketganlar
                left_ids = known_participants - current_ids - {me.id}
                for uid in left_ids:
                    alert = (
                        f"🔴 **Obunachi chiqib ketdi!**\n"
                        f"📡 Kanal: **{channel.title}**\n"
                        f"👤 `[ID: {uid}]`\n"
                        f"⏰ {_format_time(datetime.now(UZ_TZ))}"
                    )
                    await client.send_message("me", alert)

                known_participants = current_ids

                # 2. Xabarlardagi yangi ko'rishlar va reaksiyalar
                messages = await client.get_messages(channel, limit=10)
                for msg in messages:
                    # Views o'zgarishi
                    current_views = msg.views or 0
                    prev_views = known_views.get(msg.id, 0)
                    if current_views > prev_views and prev_views > 0:
                        diff = current_views - prev_views
                        msg_text = (msg.text or "")[:30]
                        alert = (
                            f"👁 **Yangi ko'rish aniqlandi!**\n"
                            f"📡 Kanal: **{channel.title}**\n"
                            f"📝 Xabar: #{msg.id} — _{msg_text}_\n"
                            f"📊 Ko'rishlar: {prev_views} ➡️ {current_views} (+{diff})\n"
                            f"⏰ {_format_time(datetime.now(UZ_TZ))}"
                        )
                        await client.send_message("me", alert)
                    known_views[msg.id] = current_views

                    # Yangi reaksiyalar tekshiruvi (Obunasizlarni tutish)
                    reactions = await _get_message_reactions(client, channel, msg.id)
                    prev_rx_users = known_reaction_users.get(msg.id, set())
                    current_rx_users = {r["user_id"] for r in reactions if r["user_id"]}

                    new_rx_users = current_rx_users - prev_rx_users - {me.id}
                    for r in reactions:
                        ruid = r["user_id"]
                        if ruid in new_rx_users:
                            u_obj = r["user"]
                            u_desc = _format_user(u_obj) if u_obj else f"ID: `{ruid}`"
                            is_sub = ruid in known_participants

                            status_tag = "✅ Obunachi" if is_sub else "🚨 **[OBUNASIZ KUZATUVCHI]**"
                            alert = (
                                f"❤️ **Yangi reaksiya qoldirildi!**\n"
                                f"📡 Kanal: **{channel.title}**\n"
                                f"📝 Xabar: #{msg.id}\n"
                                f"🎭 Reaksiya: {r['emoji']}\n"
                                f"👤 Profil: {u_desc}\n"
                                f"📌 Holati: {status_tag}\n"
                                f"⏰ {_format_time(datetime.now(UZ_TZ))}"
                            )
                            await client.send_message("me", alert)

                    known_reaction_users[msg.id] = current_rx_users

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Monitor xatolik: {e}")

            await asyncio.sleep(45)

    except asyncio.CancelledError:
        logger.info(f"Kanal {channel.title} monitoringi to'xtatildi.")
