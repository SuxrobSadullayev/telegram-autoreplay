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

def get_ai_disclaimer() -> str:
    disc = os.getenv("AI_DISCLAIMER", "— AI yordamchi 🤖").strip()
    if not disc or disc.lower() in ("none", "false", "0"):
        return ""
    return f"\n\n_{disc}_"

async def call_gemini(
    contents,
    system_instruction: str | None = None,
    max_output_tokens: int = 2048,
    temperature: float = 0.7
) -> str | None:
    """Gemini AI ga so'rov yuborish, kvota yoki xatolik bo'lsa zaxira modellarga avtomatik o'tish."""
    client = get_ai_client()
    if not client:
        return None

    configured_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
    candidate_models = [configured_model, "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    # Dublikatlarni tartibni saqlagan holda olib tashlaymiz
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    gen_config = types.GenerateContentConfig(**config_kwargs)

    for model_name in models_to_try:
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=gen_config
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Model '{model_name}' xatosi: {err_str[:120]}. Keyingi model sinab ko'riladi...")
            continue

    logger.error("Barcha Gemini modellari so'rovni bajara olmadi.")
    return None

async def generate_ai_reply(sender_name: str, message_text: str, is_first_time: bool = False) -> str | None:
    """Kelgan xabarga Gemini AI orqali aqlli javob matni tayyorlaydi."""
    use_ai = os.getenv("USE_AI", "True").lower() in ("true", "1", "yes")
    if not use_ai:
        return None

    system_instruction = os.getenv("AI_SYSTEM_INSTRUCTION", DEFAULT_SYSTEM_INSTRUCTION)
    clean_text = message_text.strip() if message_text else "(Suhbatdosh stiker, rasm yoki emotsiya yubordi)"

    if is_first_time:
        prompt = (
            f"Suhbatdosh ismi: {sender_name}\n"
            f"Suhbatdosh yuborgan birinchi xabar:\n\"\"\"\n{clean_text}\n\"\"\"\n\n"
            f"MUHIM VAZIFA: Ushbu inson sizga birinchi marta xabar yozmoqda. "
            f"Unga samimiy salom bering, foydalanuvchi hozirda offline (tarmoqda yo'q) ekanligini, "
            f"bo'sh vaqti bo'lishi bilan barcha xabarlariga albatta javob qaytarishini xushmuomala tushuntiring. "
            f"Javobni o'zbek tilida, tabiiy, qisqa va odobli qilib yozing."
        )
    else:
        prompt = (
            f"Suhbatdosh ismi: {sender_name}\n"
            f"Suhbatdosh yuborgan xabar:\n\"\"\"\n{clean_text}\n\"\"\"\n\n"
            f"Iltimos, ushbu xabarga mos, chiroyli va qisqa javob qaytaring."
        )

    ai_text = await call_gemini(contents=prompt, system_instruction=system_instruction)
    if ai_text:
        return ai_text + get_ai_disclaimer()

    return None
