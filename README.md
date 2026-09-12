# 🚀 Professional Telegram AI Userbot (Google Gemini & Telethon)

Ushbu loyiha shaxsiy Telegram akkauntingizni kuchli, aqlli va to'liq avtonom sun'iy intellekt assistentiga aylantiruvchi professional **Telegram Userbot** hisoblanadi.

Dastur **Telethon** asinxron kutubxonasi va Google'ning eng so'nggi **Gemini AI (gemini-3.5-flash)** multimodal modeli asosida ishlaydi.

---

## 🌟 Asosiy Imkoniyatlar va Modullar

### 1. 🤖 Aqlli AI Avto-Javob (Google Gemini)
- **Kontekstual tushunish:** Kelgan har qanday xabarning ma'nosini tushunib, egasi nomidan xushmuomala, lo'nda va tabiiy o'zbek tilida javob qaytaradi.
- **Dinamik model zaxirasi (Fallback):** Agar asosiy modelda kvota tugasa yoki xatolik bo'lsa, avtomatik ravishda `gemini-3.5-flash-lite` va `gemini-3.6-flash` modellariga ulanadi. Bot hech qachon to'xtab qolmaydi!
- **Birinchi marta yozganlarni aniqlash:** Birinchi marta yozgan suhbatdoshlarga samimiy salomlashish va hozirda egasi offline ekanligi haqida maxsus xabar beriladi.
- **Jonli suhbat filtri:** Xabar kelganda bir necha soniya tanaffus qilib, agar egasi o'zi javob yozsa, AI aralashmaydi.
- **Ovozli xabarlarni tushunish:** Suhbatdosh ovozli xabar (voice note) yuborsa, bot uni avtomatik tinglab, ovoz mazmuniga qarab matnli javob beradi!

---

### 2. 🎙 Ovozli Xabarlarni Matnga O'girish (Voice-to-Text)
- **`.text`** yoki **`.transcribe`** — Biror ovozli xabar (voice note), audio fayl yoki dumaloq video xabarga javob (reply) qilib yozilganda, uni Google Gemini AI multimodal eshitish tizimi orqali to'liq va aniq matnga aylantirib beradi.

---

### 3. 🛡 Kengaytirilgan Media Anti-Delete (O'chirilgan xabarlarni tiklash)
- Suhbatdosh sizga yuborgan xabarini o'chirib yuborsa (faqat sizdan yoki ikkalangizdan ham), userbot uni darhol tutib oladi!
- **Matnli xabarlar:** O'chirilgan xabar matni, yuboruvchi ismi, Telegram ID raqami va yuborilgan vaqti bilan **"Saqlangan xabarlar" (Saved Messages)**ingizga yuboriladi.
- **Media xabarlar:** Rasmlar (photo), videolar (video), ovozli xabarlar (voice note), dumaloq videolar (video note) va hujjatlar oldindan keshga saqlanadi. Suhbatdosh o'chirgan zahoti o'sha fayl o'z holicha Saqlangan xabarlarga yetkaziladi.

---

### 4. 📝 Chat va Guruh Xulosasi (Chat Summarizer)
- **`.summary`** — Guruh yoki shaxsiy chatdagi so'nggi 50 ta xabarni bir zumda o'qib, AI orqali quyidagi tartibda qisqa xulosa tayyorlaydi:
  - 📌 **Asosiy mavzular:** Nimalar muhokama qilindi?
  - 💡 **Muhim fikrlar va qarorlar:** Kim nimaga kelishdi?
  - ✅ **Keyingi vazifalar:** Belgilangan ishlar.
- **`.summary <soni>`** — Masalan `.summary 100` deb yozib, istalgan sondagi xabarlarni tahlil qilish mumkin.

---

### 5. ⏰ Aqlli Eslatmalar Tizimi (Smart Reminders)
- SQLite ma'lumotlar bazasida saqlanuvchi va orqa fonda asinxron ishlovchi eslatmalar tizimi:
  - `.remind 15m dori ichish` — 15 daqiqadan so'ng
  - `.remind 2h hisobot topshirish` — 2 soatdan so'ng
  - `.remind 18:30 kechki ovqat` — bugun/ertaga aniq soatda
  - `.remind ertaga soat 9 da suhbat` — erkin o'zbek tilida yozilgan eslatmalarni AI orqali aniqlash
  - `.reminders` — Faol eslatmalar ro'yxati
  - `.delremind <ID>` — Eslatmani bekor qilish
- Vaqti kelganda eslatma "Saqlangan xabarlar"ingizga ovozli bildirishnoma bilan yuboriladi.

---

### 6. 🌐 AI Tarjimon (.tr / .translate)
- Har qanday tildagi xabarga reply qilib `.tr` yozilsa, xabarni o'zbek tiliga chiroyli va mukammal tarjima qilib beradi.
- Maqsadli tilni ko'rsatish: `.tr ingliz`, `.tr rus`, `.tr turk`
- To'g'ridan-to'g'ri tarjima: `.tr How was your weekend?`

---

### 7. 💡 Boshqa Foydali Buyruqlar
- **`.ai <savol>`** — Gemini AI ga xohlagan chatdan turib to'g'ridan-to'g'ri savol berish va javob olish.
- **`.calc <ifoda>`** — Xavfsiz kalkulyator (masalan: `.calc 25 * 4 + 180 / 3`, `.calc sqrt(144)`).
- **`.info`** — Tizim ma'lumotlari: Uptime, OS, Python/Telethon versiyalari, saqlangan xabarlar va faol eslatmalar soni.
- **`.stop`** / **`.start`** — AI avto-javobni vaqtincha to'xtatish va qayta yoqish (Saqlangan xabarlardan yoki istalgan chatdan).
- **`.help`** — Barcha buyruqlar va imkoniyatlarning to'liq menyusi.

---

## 📋 Buyruqlar Jadvali

| Buyruq | Izoh |
| :--- | :--- |
| `.help` | Barcha buyruqlar bo'yicha to'liq qo'llanma |
| `.info` | Userbot va server holati (Uptime, RAM, DB statistika) |
| `.stop` / `.pause` | AI avto-javob tizimini vaqtincha to'xtatish |
| `.start` / `.resume` | AI avto-javob tizimini qayta yoqish |
| `.text` | Ovozli xabarga reply qilinsa, uni matnga o'giradi |
| `.summary [soni]` | Chatdagi so'nggi xabarlarni xulosalaydi (standart: 50 ta) |
| `.remind <vaqt> <matn>` | Aqlli eslatma o'rnatish (`.remind 10m dars`) |
| `.reminders` | Kutilayotgan eslatmalar ro'yxati |
| `.delremind <ID>` | Belgilangan eslatmani o'chirish |
| `.tr [til]` | Xabarni o'zbek yoki ko'rsatilgan tilga tarjima qilish |
| `.ai <savol>` | Gemini AI ga tezkor savol berish |
| `.calc <ifoda>` | Matematik ifodalarni hisoblash |

---

## ⚙️ O'rnatish va Sozlash

### 1. Talablar
- Python 3.10 yoki undan yuqori (tavsiya etiladi: Python 3.11 - 3.14)
- Telegram API ID va API HASH ([my.telegram.org](https://my.telegram.org))
- Google Gemini API Key ([aistudio.google.com](https://aistudio.google.com/app/apikey))

### 2. O'rnatish qadamlari
```bash
# Repozitoriyani klonlash
git clone https://github.com/SuxrobSadullayev/telegram-autoreplay.git
cd telegram-autoreplay

# Virtual muhit yaratish va faollashtirish
python3 -m venv venv
source venv/bin/activate

# Kerakli kutubxonalarni o'rnatish
pip install -r requirements.txt
```

### 3. `.env` faylini sozlash
`.env.example` faylidan nusxa oling va o'z ma'lumotlaringizni kiriting:
```bash
cp .env.example .env
nano .env
```

Quyidagi parametrlarni to'ldiring:
```env
API_ID=12345678
API_HASH=sizning_api_hash_kodingiz
GEMINI_API_KEY=sizning_gemini_api_kalitingiz
GEMINI_MODEL=gemini-3.5-flash
```

### 4. Ishga tushirish
```bash
source venv/bin/activate
python main.py
```
Birinchi ishga tushirishda Telegram raqamingiz va tasdiqlash kodini kiritasiz. Tizim seansni saqlab oladi va kelgusida parolsiz ishlaydi.

---

## ☁️ Server yoki Bulutda Ishga Tushirish (Railway / VPS)

### StringSession yaratish:
Bulutli xostinglarda (`.session` faylini yuklash imkoni bo'lmaganda) seansni bitta matnli satr ko'rinishida olish uchun:
```bash
python export_session.py
```
Chiqarilgan qatorni `.env` faylidagi `TELETHON_SESSION=` qatoriga yoki Railway muhit o'zgaruvchilariga qo'shing.

### Linux systemd xizmati sifatida ishga tushirish (VPS uchun):
`/etc/systemd/system/telegram-userbot.service`:
```ini
[Unit]
Description=Telegram AI Userbot Service
After=network.target

[Service]
Type=simple
User=sadullaef-arch
WorkingDirectory=/home/sadullaef-arch/telegram-autoreply
ExecStart=/home/sadullaef-arch/telegram-autoreply/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 🔒 Xavfsizlik va Maxfiylik
- `.env` fayli va `.session` ma'lumotlari `.gitignore` ga kiritilgan bo'lib, ular hech qachon GitHub repozitoriyasiga chiqmaydi.
- Ma'lumotlar bazasi (`messages.db`) va kesh fayllari faqat sizning mahalliy tizimingizda xavfsiz saqlanadi.

---

## 👨‍💻 Muallif
Ushbu loyiha maxsus buyurtma asosida professional standartlarda tayyorlandi.
