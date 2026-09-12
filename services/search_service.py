import re
import logging
import httpx
import urllib.parse
from ai_helper import call_gemini

logger = logging.getLogger(__name__)

async def handle_google_command(event):
    """
    .google <so'rov> buyrug'i:
    DuckDuckGo API orqali qidiruv natijalari yoki Gemini AI javob beradi.
    """
    raw = (event.raw_text or "").strip()
    query = re.sub(r"^\.google\s*", "", raw, flags=re.IGNORECASE).strip()

    if not query and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            query = reply_msg.raw_text.strip()

    if not query:
        msg = "ℹ️ **Qo'llanishi:** `.google <qidiruv so'rovi>`\nMisol: `.google Python asyncio nima?`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit(f"🔍 **\"{query[:30]}...\" qidirilmoqda...**")
    else:
        status_msg = await event.reply(f"🔍 **\"{query[:30]}...\" qidirilmoqda...**")

    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json() if resp.status_code == 200 else {}

        abstract = data.get("AbstractText", "")
        abstract_url = data.get("AbstractURL", "")
        related = data.get("RelatedTopics", [])

        if abstract:
            text = f"🔍 **Qidiruv natijasi:** `{query}`\n\n📄 {abstract}\n"
            if abstract_url:
                text += f"\n🔗 [Batafsil o'qish]({abstract_url})"
            await status_msg.edit(text)
            return

        if related:
            text = f"🔍 **Qidiruv natijasi:** `{query}`\n\n"
            count = 0
            for item in related:
                if "Text" in item and "FirstURL" in item and count < 5:
                    text += f"🔹 [{item['Text'][:80]}]({item['FirstURL']})\n\n"
                    count += 1
            if count > 0:
                await status_msg.edit(text)
                return

        # Natija topilmasa Gemini AI ga uzatamiz
        await status_msg.edit("🧠 **DDG natija bermadi, Gemini AI orqali javob tayyorlanmoqda...**")
        prompt = f"Foydalanuvchi savoli: {query}\n\nIltimos, ushbu savolga o'zbek tilida aniq va tushunarli javob bering."
        ai_res = await call_gemini(contents=prompt, temperature=0.7, max_output_tokens=2048)
        if ai_res:
            await status_msg.edit(f"🔍 **Qidiruv natijasi (AI):** `{query}`\n\n{ai_res}")
        else:
            await status_msg.edit("❌ Qidiruv natijasi topilmadi.")

    except Exception as e:
        logger.error(f".google xatosi: {e}")
        await status_msg.edit(f"❌ Qidiruvda xatolik: {e}")

async def handle_wiki_command(event):
    """
    .wiki <so'rov> buyrug'i:
    Wikipedia'dan qisqa ma'lumot olish.
    """
    raw = (event.raw_text or "").strip()
    query = re.sub(r"^\.wiki\s*", "", raw, flags=re.IGNORECASE).strip()

    if not query and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.raw_text:
            query = reply_msg.raw_text.strip()

    if not query:
        msg = "ℹ️ **Qo'llanishi:** `.wiki <so'rov>`\nMisol: `.wiki Amir Temur`"
        if event.out:
            await event.edit(msg)
        else:
            await event.reply(msg)
        return

    if event.out:
        status_msg = await event.edit(f"📚 **Wikipedia'da \"{query[:30]}\" qidirilmoqda...**")
    else:
        status_msg = await event.reply(f"📚 **Wikipedia'da \"{query[:30]}\" qidirilmoqda...**")

    try:
        encoded = urllib.parse.quote(query)
        result = None

        # Avval o'zbek Vikipediyasidan sinab ko'ramiz
        for lang in ["uz", "en", "ru"]:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("extract"):
                            result = data
                            break
            except Exception:
                continue

        if result:
            title = result.get("title", query)
            extract = result.get("extract", "")
            page_url = result.get("content_urls", {}).get("desktop", {}).get("page", "")

            text = f"📚 **Wikipedia: {title}**\n\n{extract}\n"
            if page_url:
                text += f"\n🔗 [To'liq maqola]({page_url})"
            await status_msg.edit(text)
        else:
            await status_msg.edit(f"❌ \"{query}\" haqida Wikipedia'da ma'lumot topilmadi.")

    except Exception as e:
        logger.error(f".wiki xatosi: {e}")
        await status_msg.edit(f"❌ Wikipedia qidiruvida xatolik: {e}")
