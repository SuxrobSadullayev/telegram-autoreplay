import os
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Har ehtimolga qarshi .env ni yuklaymiz
load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_INSTRUCTION = (
    "Siz foydalanuvchining shaxsiy sun'iy intellekt yordamchisisiz. "
    "Telegram orqali kelgan har qanday xabarga foydalanuvchi nomidan samimiy, do'stona, "
    "xushmuomala va tabiiy javob qaytaring. Suhbatdosh bilan odobli muloqot qiling, "
    "savollarga aniq va lo'nda javob bering. Javoblarni o'zbek tilida, ortiqcha cho'zmasdan, "
    "jonli insondek tabiiy tilda yozing."
)

_client = None

def get_ai_client():
    global _client
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if _client is None and api_key:
        try:
            _client = genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Gemini klientini ishga tushirishda xatolik: {e}")
    return _client

async def generate_ai_reply(sender_name: str, message_text: str) -> str | None:
    """Kelgan xabarga Gemini AI orqali aqlli javob matni tayyorlaydi."""
    use_ai = os.getenv("USE_AI", "True").lower() in ("true", "1", "yes")
    if not use_ai:
        return None

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("USE_AI=True lekin GEMINI_API_KEY kiritilmagan. Oddiy matn yuboriladi.")
        return None

    client = get_ai_client()
    if not client:
        return None

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
    system_instruction = os.getenv("AI_SYSTEM_INSTRUCTION", DEFAULT_SYSTEM_INSTRUCTION)

    clean_text = message_text.strip() if message_text else "(Suhbatdosh stiker, rasm yoki emotsiya yubordi)"

    prompt = (
        f"Suhbatdosh ismi: {sender_name}\n"
        f"Suhbatdosh yuborgan xabar:\n\"\"\"\n{clean_text}\n\"\"\"\n\n"
        f"Iltimos, ushbu xabarga mos, chiroyli va qisqa javob qaytaring."
    )

    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=1000,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini AI javob yaratishda xatolik yuz berdi: {e}")

    return None
