import re
import logging
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
WTTR_API_URL = "https://wttr.in/{city}?format=j1"

# Valyuta bayroqlari va nomlari
CURRENCY_ICONS = {
    "USD": "🇺🇸 AQSH Dollari",
    "EUR": "🇪🇺 Yevro",
    "RUB": "🇷🇺 Rossiya Rubli",
    "GBP": "🇬🇧 Angliya Funt Sterlingi",
    "KZT": "🇰🇿 Qozog'iston Tengesi",
    "TRY": "🇹🇷 Turkiya Lirasi",
    "CNY": "🇨🇳 Xitoy Yuani",
    "AED": "🇦🇪 BAA Dirhami"
}

# Ob-havo holati tarjimalari
WEATHER_TRANSLATIONS = {
    "sunny": "☀️ Quyoshli",
    "clear": "☀️ Ochiq havo",
    "partly cloudy": "⛅️ Qisman bulutli",
    "cloudy": "☁️ Bulutli",
    "overcast": "☁️ Qalin bulutli",
    "mist": "🌫 Tuman",
    "fog": "🌫 Qalin tuman",
    "patchy rain possible": "🌦 Qisqa yomg'ir ehtimoli",
    "light rain": "🌧 Mayda yomg'ir",
    "moderate rain": "🌧 O'rtacha yomg'ir",
    "heavy rain": "⛈ Kuchli yomg'ir",
    "thunderstorm": "⛈ Chaqmoqli yomg'ir",
    "patchy snow possible": "🌨 Qor yog'ish ehtimoli",
    "light snow": "🌨 Mayda qor",
    "moderate snow": "❄️ Qor",
    "heavy snow": "❄️ Kuchli qor"
}

async def handle_currency_command(event):
    """
    .kurs / .valyuta buyrug'i:
    O'zbekiston Respublikasi Markaziy Bankining rasmiy valyuta kurslarini ko'rsatadi.
    """
    if event.out:
        status_msg = await event.edit("🔄 **Markaziy Bankdan valyuta kurslari olinmoqda...**")
    else:
        status_msg = await event.reply("🔄 **Markaziy Bankdan valyuta kurslari olinmoqda...**")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(CBU_API_URL)
            if resp.status_code != 200:
                await status_msg.edit("❌ Markaziy Bank serveriga ulanishda xatolik.")
                return

            data = resp.json()
            currency_dict = {item["Ccy"]: item for item in data}

            date_str = data[0].get("Date", datetime.now().strftime("%d.%m.%Y"))

            text = f"🏦 **O‘zbekiston Markaziy Banki Valyuta Kurslari**\n📅 Sana: `{date_str}`\n\n"

            for ccy, name in CURRENCY_ICONS.items():
                if ccy in currency_dict:
                    item = currency_dict[ccy]
                    rate = float(item.get("Rate", 0))
                    diff = float(item.get("Diff", 0))

                    if diff > 0:
                        diff_str = f"⬆️ +{diff:g}"
                    elif diff < 0:
                        diff_str = f"⬇️ {diff:g}"
                    else:
                        diff_str = "➖ 0"

                    text += f"{name} (`{ccy}`):\n💰 **{rate:,.2f} so'm** ({diff_str})\n\n"

            text += "💡 *Kurslar har ish kunida yangilanadi.*"
            await status_msg.edit(text)

    except Exception as e:
        logger.error(f".kurs buyrug'ida xatolik: {e}")
        await status_msg.edit(f"❌ Kurslarni olishda xatolik yuz berdi: {e}")

async def handle_weather_command(event):
    """
    .weather [shahar] / .obhavo buyrug'i:
    Belgilangan shahar yoki Toshkent bo'yicha jonli ob-havo ma'lumotlarini taqdim etadi.
    """
    raw = (event.raw_text or "").strip()
    city = re.sub(r"^\.(?:weather|obhavo)\s*", "", raw, flags=re.IGNORECASE).strip()
    if not city:
        city = "Tashkent"

    city_display = city.capitalize()
    if city.lower() in ("toshkent", "tashkent"):
        city_query = "Tashkent"
        city_display = "Toshkent"
    elif city.lower() in ("samarqand", "samarkand"):
        city_query = "Samarkand"
        city_display = "Samarqand"
    elif city.lower() in ("buxoro", "bukhara"):
        city_query = "Bukhara"
        city_display = "Buxoro"
    else:
        city_query = city

    if event.out:
        status_msg = await event.edit(f"⛅️ **{city_display} ob-havo ma'lumotlari olinmoqda...**")
    else:
        status_msg = await event.reply(f"⛅️ **{city_display} ob-havo ma'lumotlari olinmoqda...**")

    try:
        url = WTTR_API_URL.format(city=city_query)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Accept-Language": "uz"})
            if resp.status_code != 200:
                await status_msg.edit(f"❌ '{city_display}' shahri bo'yicha ob-havo topilmadi.")
                return

            data = resp.json()
            current = data.get("current_condition", [{}])[0]
            if not current:
                await status_msg.edit("❌ Ob-havo ma'lumotlarini o'qib bo'lmadi.")
                return

            temp_c = current.get("temp_C", "N/A")
            feels_like = current.get("FeelsLikeC", "N/A")
            humidity = current.get("humidity", "N/A")
            wind_speed = current.get("windspeedKmph", "N/A")
            desc_raw = (current.get("weatherDesc", [{}])[0].get("value", "")).lower().strip()
            desc = WEATHER_TRANSLATIONS.get(desc_raw, desc_raw.capitalize())

            # Bugungi prognoz (min/max)
            today_forecast = data.get("weather", [{}])[0]
            max_temp = today_forecast.get("maxtempC", "")
            min_temp = today_forecast.get("mintempC", "")

            result_text = (
                f"📍 **{city_display} shahrida ob-havo:**\n\n"
                f"🌡 **Harorat:** {temp_c}°C (sezilishi: {feels_like}°C)\n"
                f"📝 **Holat:** {desc}\n"
                f"💧 **Namlik:** {humidity}%\n"
                f"💨 **Shamol tezligi:** {wind_speed} km/soat\n"
            )
            if max_temp and min_temp:
                result_text += f"📊 **Bugun:** min {min_temp}°C / max {max_temp}°C\n"

            await status_msg.edit(result_text)

    except Exception as e:
        logger.error(f".weather xatosi: {e}")
        await status_msg.edit(f"❌ Ob-havo ma'lumotini olishda xatolik: {e}")
