# Telegram Shaxsiy Xabarlar Uchun AI Avto-Javob Dasturi (Userbot)

Ushbu dastur sizning shaxsiy Telegram akkauntingiz nomidan ishlaydi va shaxsiy (DM) xabar yozgan foydalanuvchilarga **Google Gemini AI** orqali ularning xabarlarini tahlil qilib, aqlli va tabiiy javob qaytaradi.

## Imkoniyatlari

- 🤖 **Google Gemini AI integratsiyasi:** Kelgan har bir xabarning ma'nosini tushunib, do'stona va xushmuomala javob matni generatsiya qiladi.
- 🎯 **Moslashuvchan ko'rsatma (System Instruction):** AI qanday uslubda javob berishini (ohang, cheklovlar, shaxsiy ko'rsatmalar) o'zingiz belgilashingiz mumkin.
- 🛡️ **Zaxira (Fallback) mexanizmi:** Agar internet uzilsa yoki API kalitda xatolik bo'lsa, avtomatik ravishda tayyor andoza matn yuboriladi.
- ⏱️ **Spamdan himoya (Cooldown):** Bitta odam ketma-ket bir nechta xabar yozsa, AI qayta-qayta javob yozib behuda xarajat va noqulaylik keltirib chiqarmaydi (masalan, 60 daqiqada 1 marta javob beradi). Kesh saqlanadi (`replied_users.json`).
- 👥 **Kontaktlar filtri:** Faqat kontaktlaringizda bo'lmagan yangi shaxslarga javob qaytarish imkoniyati.

---

## O'rnatish va Ishga Tushirish

### 1-qadam: Telegram API ma'lumotlarini olish
1. [my.telegram.org](https://my.telegram.org) saytiga kiring.
2. Raqamingizni kiritib tasdiqlang.
3. **API development tools** bo'limida ilova ochib, `api_id` va `api_hash` ni oling.

### 2-qadam: Google Gemini API kalitini olish (Mutlaqo bepul)
1. **[Google AI Studio (aistudio.google.com/app/apikey)](https://aistudio.google.com/app/apikey)** sahifasiga kiring.
2. Google hisobingiz orqali kiring va **"Create API key"** tugmasini bosing.
3. Tayyor bo'lgan API kalitni nusxalang.

### 3-qadam: `.env` faylini to'ldirish
`/home/sadullaef-arch/telegram-autoreply/.env` faylini oching va qiymatlarni kiriting:
```env
# Telegram API
API_ID=12345678
API_HASH=sizning_api_hash_qiymatingiz

# Sun'iy intellekt sozlamalari
USE_AI=True
GEMINI_API_KEY=AIzaSy...sizning_gemini_api_kalitingiz
GEMINI_MODEL=gemini-2.5-flash

# AI ga yo'riqnoma:
AI_SYSTEM_INSTRUCTION="Siz foydalanuvchining shaxsiy sun'iy intellekt yordamchisisiz. Telegram shaxsiy xabarlariga foydalanuvchi nomidan xushmuomala, samimiy va lo'nda javob qaytaring. Foydalanuvchi hozirda bandligini va xabarni ko'rishi bilan o'zi ham yozishini eslatib o'ting. Agar suhbatdosh aniq bir savol bergan bo'lsa, qisqa va foydali ma'lumot berishga harakat qiling. Javobni o'zbek tilida, tabiiy va do'stona ohangda yozing."

# Zaxira xabar (AI ishlamay qolganda):
AUTO_REPLY_MESSAGE="Assalomu alaykum! Hozirda bandman. Xabaringizni ko'rishim bilan javob qaytaraman. Rahmat!"

# Qayta yuborish oralig'i (daqiqada):
COOLDOWN_MINUTES=60
REPLY_ONLY_NON_CONTACTS=False
```

---

### 4-qadam: Dasturni ishga tushirish
Terminalda dasturni ishga tushiring:
```bash
cd /home/sadullaef-arch/telegram-autoreply
./venv/bin/python main.py
```
> Birinchi ishga tushishda telefon raqamingiz va Telegram ilovangizga kelgan kodni kiritasiz. So'ngra dastur avtomatik tarzda xabarlarni qabul qilib, AI orqali javob berishni boshlaydi.

---

### 5-qadam: Doimiy fonda (background) qoldirish
```bash
cd /home/sadullaef-arch/telegram-autoreply
nohup ./venv/bin/python main.py > autoreply.log 2>&1 &
```

- Loglarni jonli ko'rish: `tail -f /home/sadullaef-arch/telegram-autoreply/autoreply.log`
- To'xtatish: `pkill -f "main.py"`
