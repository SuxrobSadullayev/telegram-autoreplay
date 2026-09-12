import re
import logging
from telethon import TelegramClient
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = (
    "Siz professional tahlilchi va suhbatlarni xulosalovchi yordamchisiz. "
    "Sizga Telegram guruh yoki shaxsiy chatidagi xabarlar taqdim etiladi. "
    "Siz ushbu suhbatning eng muhim nuqtalarini, ko'tarilgan masalalarni va qabul qilingan qarorlarni "
    "aniq, lo'nda va chiroyli o'zbek tilida punktlar bilan xulosa qilib berishingiz kerak."
)

async def summarize_chat(client: TelegramClient, chat_id: int, limit: int = 50) -> str | None:
    """Chatdagi so'nggi xabarlarni olib, Gemini orqali qisqa tahlil va xulosa yaratadi."""
    try:
        messages = await client.get_messages(chat_id, limit=limit)
        if not messages or len(messages) < 3:
            return "⚠️ Xulosalash uchun chatda yetarli xabarlar topilmadi (kamida 3 ta xabar kerak)."

        # Xabarlarni xronologik tartibga solamiz (eski xabardan yangisiga)
        chronological_msgs = list(reversed(messages))
        lines = []

        for msg in chronological_msgs:
            sender = await msg.get_sender()
            sender_name = "Noma'lum"
            if msg.out:
                sender_name = "Men"
            elif sender:
                sender_name = getattr(sender, "first_name", "") or getattr(sender, "title", "Foydalanuvchi")

            content = msg.raw_text.strip() if msg.raw_text else ""
            if not content:
                if msg.photo:
                    content = "[Rasm yuborildi]"
                elif msg.voice:
                    content = "[Ovozli xabar yuborildi]"
                elif msg.video:
                    content = "[Video yuborildi]"
                elif msg.document:
                    content = "[Fayl / Hujjat yuborildi]"
                else:
                    content = "[Media]"

            lines.append(f"{sender_name}: {content}")

        transcript = "\n".join(lines)

        prompt = (
            f"Telegram chatidagi so'nggi {len(lines)} ta xabarning stenogrammasi:\n"
            f"\"\"\"\n{transcript}\n\"\"\"\n\n"
            f"VAZIFA: Ushbu suhbatni o'zbek tilida quyidagi formatda lo'nda va chiroyli xulosa qilib bering:\n\n"
            f"📌 **Asosiy mavzu:** (Suhbat nima haqida bo'ldi?)\n"
            f"💡 **Muhim fikrlar va kelishuvlar:** (Qisqa punktlar ko'rinishida)\n"
            f"✅ **Keyingi rejalar / Vazifalar:** (Agar bo'lsa, qisqa ko'rsating)"
        )

        summary = await call_gemini(
            contents=prompt,
            system_instruction=SUMMARY_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=2048
        )
        return summary
    except Exception as e:
        logger.error(f"Chatni xulosalashda xatolik: {e}")
        return None

async def handle_summary_command(event):
    """
    .summary yoki .summary <soni> buyrug'i:
    Chatdagi so'nggi N ta xabarni AI yordamida tahlil qilib beradi.
    """
    raw = (event.raw_text or "").strip()
    match = re.search(r"^\.summary(?:\s+(\d+))?", raw, re.IGNORECASE)

    limit = 50
    if match and match.group(1):
        try:
            limit = int(match.group(1))
            limit = max(5, min(limit, 100)) # 5 dan 100 gacha cheklov
        except ValueError:
            limit = 50

    # Holat xabari
    if event.out:
        status_msg = await event.edit(f"⏳ **Chatdagi so'nggi {limit} ta xabar tahlil qilinmoqda...**")
    else:
        status_msg = await event.reply(f"⏳ **Chatdagi so'nggi {limit} ta xabar tahlil qilinmoqda...**")

    summary = await summarize_chat(event.client, event.chat_id, limit=limit)

    if summary:
        response_text = f"📝 **Chat Xulosasi (So'nggi {limit} ta xabar):**\n\n{summary}"
        await status_msg.edit(response_text)
    else:
        await status_msg.edit("❌ Suhbatni tahlil qilishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
