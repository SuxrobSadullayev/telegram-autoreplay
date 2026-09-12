import re
import json
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from telethon import TelegramClient
from ai_helper import call_gemini
from db import DB_FILE

logger = logging.getLogger(__name__)

def parse_time_with_regex(time_str: str) -> datetime | None:
    """Oddiy formatdagi vaqtlarni aniqlaydi (masalan: 10m, 2h, 30s, 15:30)."""
    now = datetime.now()
    time_str = time_str.strip().lower()

    # 10m, 2h, 30s kabi nisbiy vaqtlar
    rel_match = re.match(r"^(\d+)\s*(s|sec|soniya|m|min|daqiqa|h|soat|d|kun)$", time_str)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit in ("s", "sec", "soniya"):
            return now + timedelta(seconds=val)
        elif unit in ("m", "min", "daqiqa"):
            return now + timedelta(minutes=val)
        elif unit in ("h", "soat"):
            return now + timedelta(hours=val)
        elif unit in ("d", "kun"):
            return now + timedelta(days=val)

    # 15:30 kabi aniq soat formati
    clock_match = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if clock_match:
        hours = int(clock_match.group(1))
        minutes = int(clock_match.group(2))
        if 0 <= hours < 24 and 0 <= minutes < 60:
            target = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1) # Agar soat o'tib ketgan bo'lsa ertangi kunga qo'yamiz
            return target

    return None

async def parse_natural_reminder(raw_text: str) -> tuple[datetime | None, str | None]:
    """Gemini AI yordamida erkin o'zbek tilidagi eslatma matni va vaqtini aniqlaydi."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = (
        f"Hozirgi sana va vaqt: {now_str}\n"
        f"Foydalanuvchi eslatma so'rovi: \"{raw_text}\"\n\n"
        "VAZIFA: Ushbu so'rovdan eslatma matnini va qaysi sana/vaqtda eslatish kerakligini aniqlang.\n"
        "Javobni FAQAT quyidagi JSON formatida qaytaring, boshqa hech narsa yozmang:\n"
        "{\n"
        "  \"target_time\": \"YYYY-MM-DD HH:MM:SS\",\n"
        "  \"text\": \"eslatma matni\"\n"
        "}"
    )

    try:
        resp = await call_gemini(
            contents=prompt,
            temperature=0.1,
            max_output_tokens=500
        )
        if resp:
            # Har qanday markdown yoki matn ichidan JSON blokini ishonchli ajratib olamiz
            json_match = re.search(r"\{[\s\S]*\}", resp)
            if json_match:
                data = json.loads(json_match.group(0))
                target_str = data.get("target_time")
                text = data.get("text")
                if target_str and text:
                    target_dt = datetime.strptime(target_str, "%Y-%m-%d %H:%M:%S")
                    return target_dt, text
    except Exception as e:
        logger.warning(f"Natural reminder parsingda xatolik: {e}")

    return None, None

def _sync_add_reminder(chat_id: int, reminder_text: str, target_str: str, now_str: str) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reminders (chat_id, reminder_text, target_time, created_at, is_sent)
                VALUES (?, ?, ?, ?, 0)
            """, (chat_id, reminder_text, target_str, now_str))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Eslatmani saqlashda xatolik: {e}")
        return None

async def add_reminder(chat_id: int, reminder_text: str, target_dt: datetime) -> int | None:
    """Eslatmani bazaga qo'shadi."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_str = target_dt.strftime("%Y-%m-%d %H:%M:%S")
    return await asyncio.to_thread(_sync_add_reminder, chat_id, reminder_text, target_str, now_str)

def _sync_get_pending_reminders():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, chat_id, reminder_text, target_time 
                FROM reminders 
                WHERE is_sent = 0 AND target_time <= ?
            """, (now_str,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Eslatmalarni olishda xatolik: {e}")
        return []

async def get_pending_reminders():
    return await asyncio.to_thread(_sync_get_pending_reminders)

def _sync_mark_reminder_sent(reminder_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Eslatma holatini yangilashda xatolik: {e}")

async def mark_reminder_sent(reminder_id: int):
    await asyncio.to_thread(_sync_mark_reminder_sent, reminder_id)

def _sync_list_active_reminders(chat_id: int | None = None) -> list:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            if chat_id:
                cursor.execute("""
                    SELECT id, target_time, reminder_text 
                    FROM reminders 
                    WHERE is_sent = 0 AND target_time > ? AND chat_id = ?
                    ORDER BY target_time ASC
                """, (now_str, chat_id))
            else:
                cursor.execute("""
                    SELECT id, target_time, reminder_text 
                    FROM reminders 
                    WHERE is_sent = 0 AND target_time > ?
                    ORDER BY target_time ASC
                """, (now_str,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Faol eslatmalarni olishda xatolik: {e}")
        return []

async def list_active_reminders(chat_id: int | None = None) -> list:
    return await asyncio.to_thread(_sync_list_active_reminders, chat_id)

def _sync_delete_reminder(reminder_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Eslatmani o'chirishda xatolik: {e}")
        return False

async def delete_reminder(reminder_id: int) -> bool:
    return await asyncio.to_thread(_sync_delete_reminder, reminder_id)

async def handle_remind_command(event):
    """
    .remind buyrug'i:
    Misollar:
    .remind 10m dori ichish
    .remind 2h muhim uchrashuv
    .remind 18:30 kitob o'qish
    .remind ertaga soat 10 da hisobot tayyorlash
    """
    raw = (event.raw_text or "").strip()
    content = re.sub(r"^\.remind\s*", "", raw, flags=re.IGNORECASE).strip()

    if not content:
        usage = (
            "⏰ **Eslatma o'rnatish qo'llanmasi:**\n\n"
            "• `.remind 10m dori ichish` (10 daqiqadan so'ng)\n"
            "• `.remind 2h hisobot topshirish` (2 soatdan so'ng)\n"
            "• `.remind 18:00 uchrashuv` (bugun/ertaga 18:00 da)\n"
            "• `.remind ertaga soat 9:00 da suhbat` (erkin tilda)\n\n"
            "📋 Barcha eslatmalar ro'yxati: `.reminders`\n"
            "❌ O'chirish: `.delremind <ID>`"
        )
        if event.out:
            await event.edit(usage)
        else:
            await event.reply(usage)
        return

    # 1. Tezkor regex orqali tekshirish
    parts = content.split(maxsplit=1)
    target_dt = None
    rem_text = None

    if len(parts) >= 2:
        potential_time = parts[0]
        potential_text = parts[1]
        parsed = parse_time_with_regex(potential_time)
        if parsed:
            target_dt = parsed
            rem_text = potential_text

    # 2. Agar regex mos kelmasa, Gemini AI yordamida aniqlaymiz
    if not target_dt or not rem_text:
        target_dt, rem_text = await parse_natural_reminder(content)

    if not target_dt or not rem_text:
        msg = "⚠️ Eslatma vaqtini aniqlab bo'lmadi. Iltimos, `.remind 15m vazifa` ko'rinishida yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    rem_id = await add_reminder(event.chat_id, rem_text, target_dt)
    time_display = target_dt.strftime("%Y-%m-%d %H:%M:%S")

    success_text = (
        f"✅ **Eslatma muvaffaqiyatli saqlandi!** (ID: `#{rem_id}`)\n\n"
        f"📝 **Matn:** {rem_text}\n"
        f"⏰ **Vaqti:** `{time_display}`\n\n"
        f"Vaqti kelganda sizga eslatma yuboriladi."
    )
    if event.out:
        await event.edit(success_text)
    else:
        await event.reply(success_text)

async def handle_reminders_list_command(event):
    """Faol eslatmalar ro'yxatini ko'rsatish (.reminders)."""
    rows = await list_active_reminders()
    if not rows:
        text = "📭 Hozirda faol eslatmalar mavjud emas."
    else:
        text = "📋 **Faol Eslatmalar Ro'yxati:**\n\n"
        for row in rows:
            text += f"🔹 **ID #{row[0]}** | ⏰ `{row[1]}`\n   📝 {row[2]}\n\n"
        text += "Eslatmani bekor qilish uchun: `.delremind <ID>`"

    if event.out:
        await event.edit(text)
    else:
        await event.reply(text)

async def handle_delremind_command(event):
    """Eslatmani o'chirish (.delremind <ID>)."""
    raw = (event.raw_text or "").strip()
    match = re.search(r"^\.delremind\s+(\d+)", raw, re.IGNORECASE)
    if not match:
        msg = "⚠️ Eslatma ID raqamini kiriting. Masalan: `.delremind 3`"
    else:
        rem_id = int(match.group(1))
        if await delete_reminder(rem_id):
            msg = f"✅ Eslatma `#{rem_id}` muvaffaqiyatli o'chirildi."
        else:
            msg = f"❌ `#{rem_id}` raqamli eslatma topilmadi."

    if event.out:
        await event.edit(msg)
    else:
        await event.reply(msg)

async def reminder_worker_loop(client: TelegramClient):
    """Orqa fonda har 5 soniyada eslatmalarni tekshirib boruvchi doimiy jarayon."""
    logger.info("Eslatmalar fon xizmati (Reminder Worker) ishga tushdi.")
    while True:
        try:
            due_reminders = await get_pending_reminders()
            for rem in due_reminders:
                rem_id, chat_id, text, target_time = rem
                alert_text = (
                    f"🔔 **ESLATMA VAQTI KELDI!**\n\n"
                    f"📝 **Vazifa:** {text}\n"
                    f"⏰ **Rejalashtirilgan vaqt:** {target_time}\n"
                    f"📌 Eslatma ID: `#{rem_id}`"
                )
                try:
                    # Avval "Saqlangan xabarlar"ga (me) yuboramiz
                    await client.send_message("me", alert_text)
                    # Agar boshqa chatda belgilangan bo'lsa u yerga ham
                    if chat_id:
                        me = await client.get_me()
                        if chat_id != me.id:
                            await client.send_message(chat_id, alert_text)
                except Exception as send_err:
                    logger.error(f"Eslatmani yuborishda xatolik: {send_err}")
                finally:
                    await mark_reminder_sent(rem_id)
        except Exception as e:
            logger.error(f"Reminder worker loop xatosi: {e}")

        await asyncio.sleep(5)
