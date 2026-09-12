import re
import os
import ast
import math
import time
import platform
import logging
import sqlite3
import operator
from datetime import datetime
from telethon import TelegramClient
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

START_TIME = time.time()
DB_FILE = "messages.db"

# AST-based xavfsiz matematik hisoblagich
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}

def safe_eval_expr(node):
    if isinstance(node, ast.Expression):
        return safe_eval_expr(node.body)
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            left = safe_eval_expr(node.left)
            right = safe_eval_expr(node.right)
            return SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            operand = safe_eval_expr(node.operand)
            return SAFE_OPERATORS[op_type](operand)
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCTIONS:
            func = SAFE_FUNCTIONS[node.func.id]
            args = [safe_eval_expr(arg) for arg in node.args]
            return func(*args)
    elif isinstance(node, ast.Name) and node.id in SAFE_FUNCTIONS:
        return SAFE_FUNCTIONS[node.id]

    raise ValueError("Ruxsat berilmagan ifoda")

def calculate_expression(expr_str: str):
    """Matematik ifodani xavfsiz hisoblaydi."""
    expr_clean = expr_str.strip().replace("^", "**")
    try:
        tree = ast.parse(expr_clean, mode="eval")
        return safe_eval_expr(tree)
    except Exception:
        return None

# ==========================================
# 1. Tarjima buyrug'i (.tr / .translate)
# ==========================================
async def handle_translate_command(event):
    """
    .tr yoki .translate buyrug'i:
    Xabarga reply qilinganda yoki matn kiritilganda uni o'zbek tiliga (yoki ko'rsatilgan tilga) tarjima qiladi.
    """
    raw = (event.raw_text or "").strip()
    # Buyruqdan keyingi matnni olamiz
    args = re.sub(r"^\.(?:tr|translate)\s*", "", raw, flags=re.IGNORECASE).strip()

    source_text = ""
    target_lang = "o'zbek"

    # Agar reply bo'lsa
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            source_text = reply_msg.raw_text.strip()
            if args:
                target_lang = args
    else:
        # Reply bo'lmasa, matn buyruqning o'zida yozilgan bo'ladi
        if not args:
            usage = (
                "🌐 **Tarjimon qo'llanmasi:**\n\n"
                "• Biror xabarga reply qilib `.tr` yozing (avtomatik o'zbekchaga o'giradi)\n"
                "• Biror xabarga reply qilib `.tr ingliz` yoki `.tr rus` deb yozing\n"
                "• To'g'ridan-to'g'ri: `.tr Hello, how are you?`"
            )
            if event.out:
                await event.edit(usage)
            else:
                await event.reply(usage)
            return
        source_text = args

    if event.out:
        status_msg = await event.edit("⏳ **Tarjima qilinmoqda...**")
    else:
        status_msg = await event.reply("⏳ **Tarjima qilinmoqda...**")

    prompt = (
        f"Quyidagi matnni aniq, mazmunli va tabiiy tarzda {target_lang} tiliga tarjima qiling.\n"
        f"Hech qanday qo'shimcha tushuntirish yoki kirish so'zlarsiz, faqat tarjimaning o'zini qaytaring:\n\n"
        f"\"\"\"\n{source_text}\n\"\"\""
    )

    translated = await call_gemini(contents=prompt, temperature=0.3, max_output_tokens=2048)
    if translated:
        res = (
            f"🌐 **Tarjima ({target_lang}):**\n\n"
            f"{translated}"
        )
        await status_msg.edit(res)
    else:
        await status_msg.edit("❌ Tarjima qilishda xatolik yuz berdi.")

# ==========================================
# 2. To'g'ridan-to'g'ri AI so'rovi (.ai)
# ==========================================
async def handle_ai_command(event):
    """
    .ai <savol> buyrug'i:
    Gemini AI ga to'g'ridan-to'g'ri savol berish va tezkor javob olish.
    """
    raw = (event.raw_text or "").strip()
    query = re.sub(r"^\.ai\s*", "", raw, flags=re.IGNORECASE).strip()

    # Agar reply bo'lsa va query bo'sh bo'lsa, reply qilingan xabarni olamiz
    if not query and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            query = reply_msg.raw_text.strip()

    if not query:
        msg = "ℹ️ **Qo'llanishi:** `.ai <savolingiz>`\nMisol: `.ai Python da generatorlar nima va nima uchun kerak?`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit("🧠 **Gemini AI javob tayyorlamoqda...**")
    else:
        status_msg = await event.reply("🧠 **Gemini AI javob tayyorlamoqda...**")

    prompt = (
        f"Savol:\n{query}\n\n"
        f"Iltimos, ushbu savolga o'zbek tilida aniq, tushunarli va professional javob qaytaring."
    )

    ai_answer = await call_gemini(contents=prompt, temperature=0.7, max_output_tokens=2048)
    if ai_answer:
        res = f"🤖 **AI Javobi:**\n\n{ai_answer}"
        await status_msg.edit(res)
    else:
        await status_msg.edit("❌ AI javob bera olmadi. Iltimos qayta urinib ko'ring.")

# ==========================================
# 3. Hisoblagich (.calc)
# ==========================================
async def handle_calc_command(event):
    """
    .calc <ifoda> buyrug'i:
    Matematik ifodalarni tezkor va xavfsiz hisoblaydi.
    """
    raw = (event.raw_text or "").strip()
    expr = re.sub(r"^\.calc\s*", "", raw, flags=re.IGNORECASE).strip()

    if not expr:
        msg = "ℹ️ **Qo'llanishi:** `.calc <matematik ifoda>`\nMisol: `.calc 150 * 12 + (450 / 3)`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    # Avval xavfsiz matematik tahlil orqali sinaymiz
    result = calculate_expression(expr)
    if result is not None:
        text = f"🔢 **Natija:**\n`{expr}` = **{result}**"
        if event.out:
            await event.edit(text)
        else:
            await event.reply(text)
        return

    # Agar murakkab matnli hisob-kitob bo'lsa, Gemini AI ga yuboramiz
    prompt = (
        f"Quyidagi matematik yoki hisob-kitob masalasini yeching va qisqa, aniq natijani ko'rsating:\n\n{expr}"
    )
    ai_calc = await call_gemini(contents=prompt, temperature=0.1, max_output_tokens=500)
    if ai_calc:
        res = f"🔢 **Hisob-kitob natijasi:**\n\n{ai_calc}"
        if event.out:
            await event.edit(res)
        else:
            await event.reply(res)
    else:
        msg = "❌ Matematik ifodani hisoblab bo'lmadi."
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)

# ==========================================
# 4. Tizim holati (.info)
# ==========================================
async def handle_info_command(event, bot_paused: bool):
    """Userbot tizim ma'lumotlari, ishlash vaqti va holatini ko'rsatadi."""
    uptime_sec = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}s {minutes}m {seconds}soniya"

    # Ma'lumotlar bazasi statistikasi
    db_saved_count = 0
    reminders_count = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM saved_messages")
            db_saved_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM reminders WHERE is_sent = 0")
            reminders_count = c.fetchone()[0]
    except Exception:
        pass

    me = await event.client.get_me()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    status_str = "⏸ Vaqtincha to'xtatilgan" if bot_paused else "▶️ Faol (Ishlamoqda)"

    info_text = (
        "⚡ **Telegram AI Userbot Tizim Ma'lumotlari** ⚡\n\n"
        f"👤 **Egasining ismi:** {me.first_name}\n"
        f"🆔 **Telegram ID:** `{me.id}`\n"
        f"🤖 **Holat:** {status_str}\n"
        f"⏱ **Uptime:** {uptime_str}\n"
        f"🧠 **AI Modeli:** `{model}`\n"
        f"💾 **Anti-Delete bazasi:** {db_saved_count} ta xabar saqlangan\n"
        f"⏰ **Kutilayotgan eslatmalar:** {reminders_count} ta\n"
        f"💻 **OT:** {platform.system()} ({platform.release()})\n"
        f"🐍 **Python:** {platform.python_version()}"
    )

    if event.out:
        await event.edit(info_text)
    else:
        await event.reply(info_text)

# ==========================================
# 5. Yordam menyusi (.help)
# ==========================================
async def handle_help_command(event):
    """Barcha buyruqlar va imkoniyatlar ro'yxatini ko'rsatadi."""
    help_text = (
        "📖 **Telegram AI Userbot — To'liq Buyruqlar Qo'llanmasi**\n\n"
        "🤖 **Avto-javob & Boshqaruv:**\n"
        "• `.stop` / `.pause` — AI avto-javobni vaqtincha to'xtatish\n"
        "• `.start` / `.resume` — AI avto-javobni qayta yoqish\n\n"
        "🎙 **Ovozli xabarlar (Voice-to-Text):**\n"
        "• `.text` (ovozga reply) — Ovozli xabarni matnga o'girib beradi\n\n"
        "🗑 **Anti-Delete (O'chirilgan xabarlar):**\n"
        "• Suhbatdosh xabar, rasm yoki ovozni o'chirsa, u avtomatik 'Saqlangan xabarlar'ga tiklab beriladi\n\n"
        "📝 **Chat Xulosasi:**\n"
        "• `.summary` — Chatdagi so'nggi 50 ta xabarni AI orqali xulosa qilish\n"
        "• `.summary 100` — So'nggi 100 ta xabarni tahlil qilish\n\n"
        "⏰ **Aqlli Eslatmalar:**\n"
        "• `.remind 15m vazifa` — 15 daqiqadan so'ng eslatish\n"
        "• `.remind 18:00 uchrashuv` — Aniq soatda eslatish\n"
        "• `.reminders` — Faol eslatmalar ro'yxati\n"
        "• `.delremind <ID>` — Eslatmani bekor qilish\n\n"
        "🌐 **Qo'shimcha Imkoniyatlar:**\n"
        "• `.tr <matn>` yoki reply `.tr` — O'zbek tiliga tarjima qilish\n"
        "• `.ai <savol>` — Gemini AI dan to'g'ridan-to'g'ri javob olish\n"
        "• `.calc <ifoda>` — Matematik ifodalarni hisoblash\n"
        "• `.info` — Bot tizim holati va statistikasini ko'rish\n"
        "• `.help` — Ushbu yordam oynasi"
    )

    if event.out:
        await event.edit(help_text)
    else:
        await event.reply(help_text)
