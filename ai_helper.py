import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

USE_AI = os.getenv("USE_AI", "True").lower() in ("true", "1", "yes")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

DEFAULT_SYSTEM_INSTRUCTION = (
    "Siz foydalanuvchining shaxsiy sun'iy intellekt yordamchisisiz. "
    "Telegram orqali kelgan har qanday xabarga foydalanuvchi nomidan samimiy, do'stona, "
    "xushmuomala va tabiiy javob qaytaring. Suhbatdosh bilan odobli muloqot qiling, "
    "savollarga aniq va lo'nda javob bering. Javoblarni o'zbek tilida, ortiqcha cho'zmasdan, "
    "jonli insondek tabiiy tilda yozing."
)

SYSTEM_INSTRUCTION = os.getenv("AI_SYSTEM_INSTRUCTION", DEFAULT_SYSTEM_INSTRUCTION)

_client = None

def get_ai_client():
    global _client
    if _client is None and GEMINI_API_KEY:
        try:
            _client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Gemini klientini ishga tushirishda xatolik: {e}")
    return _client

async def generate_ai_reply(sender_name: str, message_text: str) -> str | None:
    """Kelgan xabarga Gemini AI orqali aqlli javob matni tayyorlaydi."""
    if not USE_AI:
        return None

    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
        logger.warning("USE_AI=True lekin GEMINI_API_KEY kiritilmagan. Oddiy matn yuboriladi.")
        return None

    client = get_ai_client()
    if not client:
        return None

    prompt = (
        f"Suhbatdosh ismi: {sender_name}\n"
        f"Suhbatdosh yuborgan xabar:\n\"\"\"\n{message_text}\n\"\"\"\n\n"
        f"Iltimos, ushbu xabarga mos, chiroyli va qisqa javob qaytaring."
    )

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
                max_output_tokens=300,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini AI javob yaratishda xatolik yuz berdi: {e}")

    return None
