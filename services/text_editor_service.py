import re
import logging
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

async def handle_fix_command(event):
    """
    .fix buyrug'i:
    Matnga javob (reply) qilib yozilganda, undagi barcha orfografik, grammatik va punktuatsion xatolarni to'g'rilaydi.
    """
    raw = (event.raw_text or "").strip()
    text_to_fix = re.sub(r"^\.fix\s*", "", raw, flags=re.IGNORECASE).strip()

    if not text_to_fix and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            text_to_fix = reply_msg.raw_text.strip()

    if not text_to_fix:
        msg = "ℹ️ **Qo'llanishi:** Xatolik bor matnga **javob (reply)** qilib `.fix` deb yozing yoki `.fix <matn>` ko'rinishida yuboring."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("✍️ **Matn tekshirilmoqda va tuzatilmoqda...**")
    else:
        status_msg = await event.reply("✍️ **Matn tekshirilmoqda va tuzatilmoqda...**")

    prompt = (
        f"Asl matn:\n\"\"\"\n{text_to_fix}\n\"\"\"\n\n"
        "VAZIFA: Ushbu matndagi barcha imlo, grammatika va tinish belgisi (punktuatsiya) xatolarini to'g'rilang.\n"
        "QAT'IY QOIDALAR:\n"
        "1. Matnning asl ma'nosini va uslubini saqlang.\n"
        "2. Faqat to'g'rilangan yakuniy matnni qaytaring, ortiqcha kirish yoki izoh yozmang."
    )

    fixed_text = await call_gemini(contents=prompt, temperature=0.2, max_output_tokens=2048)
    if fixed_text:
        res = f"✍️ **Tuzatilgan matn:**\n\n{fixed_text}"
        await status_msg.edit(res)
    else:
        await status_msg.edit("❌ Matnni tuzatishda xatolik yuz berdi.")

async def handle_formal_command(event):
    """
    .formal buyrug'i:
    Matnni rasmiy, professional ish yozishmasi (biznes) uslubiga aylantiradi.
    """
    raw = (event.raw_text or "").strip()
    text_to_format = re.sub(r"^\.formal\s*", "", raw, flags=re.IGNORECASE).strip()

    if not text_to_format and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            text_to_format = reply_msg.raw_text.strip()

    if not text_to_format:
        msg = "ℹ️ **Qo'llanishi:** Matnga **javob (reply)** qilib `.formal` deb yozing yoki `.formal <matn>` ko'rinishida yuboring."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("💼 **Rasmiy uslubga o'girilmoqda...**")
    else:
        status_msg = await event.reply("💼 **Rasmiy uslubga o'girilmoqda...**")

    prompt = (
        f"Asl matn:\n\"\"\"\n{text_to_format}\n\"\"\"\n\n"
        "VAZIFA: Ushbu matnni o'zbek tilidagi chiroyli, muloyim va rasmiy ish yozishmasi (biznes/professional) uslubiga aylantiring.\n"
        "QAT'IY QOIDALAR:\n"
        "1. Xushmuomala va hurmat ohangida bo'lsin.\n"
        "2. Faqat qayta ishlangan tayyor rasmiy matnni qaytaring."
    )

    formal_text = await call_gemini(contents=prompt, temperature=0.3, max_output_tokens=2048)
    if formal_text:
        res = f"💼 **Rasmiy variant:**\n\n{formal_text}"
        await status_msg.edit(res)
    else:
        await status_msg.edit("❌ Matnni rasmiylashtirishda xatolik yuz berdi.")

async def handle_informal_command(event):
    """
    .informal (yoki .shaxsiy) buyrug'i:
    Matnni do'stona, samimiy va jonli suhbat uslubiga o'giradi.
    """
    raw = (event.raw_text or "").strip()
    text_to_format = re.sub(r"^\.(?:informal|shaxsiy)\s*", "", raw, flags=re.IGNORECASE).strip()

    if not text_to_format and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            text_to_format = reply_msg.raw_text.strip()

    if not text_to_format:
        msg = "ℹ️ **Qo'llanishi:** Matnga reply qilib `.informal` yoki `.shaxsiy` deb yozing."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("💬 **Samimiy/do'stona uslubga o'girilmoqda...**")
    else:
        status_msg = await event.reply("💬 **Samimiy/do'stona uslubga o'girilmoqda...**")

    prompt = (
        f"Asl matn:\n\"\"\"\n{text_to_format}\n\"\"\"\n\n"
        "VAZIFA: Ushbu matnni samimiy, do'stona va jonli og'zaki suhbat uslubiga o'giring.\n"
        "Faqat tayyor matnni qaytaring."
    )

    informal_text = await call_gemini(contents=prompt, temperature=0.4, max_output_tokens=2048)
    if informal_text:
        res = f"💬 **Do'stona variant:**\n\n{informal_text}"
        await status_msg.edit(res)
    else:
        await status_msg.edit("❌ Matnni o'zgartirishda xatolik yuz berdi.")
