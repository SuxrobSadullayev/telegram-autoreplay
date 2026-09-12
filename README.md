# 🚀 Professional Telegram AI Userbot (Google Gemini & Telethon)

Ushbu loyiha shaxsiy Telegram akkauntingizni kuchli, aqlli va to'liq avtonom sun'iy intellekt assistentiga aylantiruvchi professional **Telegram Userbot** hisoblanadi.

Dastur **Telethon** asinxron kutubxonasi, Google'ning eng so'nggi **Gemini Multimodal AI** modellari hamda asinxron SQLite ma'lumotlar bazasi asosida ishlaydi.

---

## 🌟 Asosiy Imkoniyatlar va Modullar

### 1. 🤖 Aqlli AI Avto-Javob (Google Gemini)
- **Kontekstual tushunish:** Kelgan har qanday xabarning ma'nosini tushunib, egasi nomidan xushmuomala, lo'nda va tabiiy o'zbek tilida javob qaytaradi.
- **Dinamik model zaxirasi (Fallback):** Kvota tugasa yoki xatolik bo'lsa, avtomatik ravishda `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash` modellariga ulanadi. Bot hech qachon to'xtab qolmaydi!
- **Birinchi marta yozganlarni aniqlash:** Birinchi marta yozgan suhbatdoshlarga samimiy salomlashish va hozirda egasi offline ekanligi haqida maxsus xabar beriladi.
- **Jonli suhbat filtri:** Xabar kelganda bir oz tanaffus qilib, agar egasi o'zi javob yozsa, AI aralashmaydi (xotiradagi kesh orqali ortiqcha tarmoq so'rovisiz ishlaydi).
- **Ovozli xabarlarni tushunish:** Suhbatdosh ovozli xabar (voice note) yuborsa, bot uni avtomatik tinglab, ovoz mazmuniga qarab to'g'ridan-to'g'ri javob beradi!

---

### 2. 👁 Multimodal Rasm Tahlili (Vision AI — `.see` / `.ocr`)
- **`.see <savol>`** — Biror rasm, skrinshot yoki diagrammaga javob (reply) qilib yozilganda, Gemini Vision orqali tasvirni tahlil qilib, savollarga javob beradi yoki undagi masalalarni yechib beradi.
- **`.ocr`** — Rasm yoki hujjatdagi barcha matn va yozuvlarni bir zumda to'liq matn shaklida ajratib beradi.

---

### 3. 📥 Instagram, TikTok va YouTube Yuklovchi (`.dl`)
- **`.dl <havola>`** yoki havolali xabarga **reply `.dl`**:
  - Instagram Reels, TikTok (suv belgisiz), YouTube Shorts va Twitter/X videolarini eng yuqori sifatda Telegramga video qilib yuklab beradi.
  - Hech qanday tashqi reklama botlarisiz to'g'ridan-to'g'ri ishlaydi.

---

### 4. ✍️ Grammatika va Matn Tahrirchisi (`.fix` / `.formal` / `.informal`)
- **`.fix`** — Xabarga reply qilinsa, undagi barcha imlo, grammatika va punktuatsiya xatolarini to'g'rilab beradi.
- **`.formal`** — Oddiy tilda yozilgan matnni rasmiy ish yozishmasi (biznes muloqot) uslubiga aylantiradi.
- **`.informal`** (yoki **`.shaxsiy`**) — Rasmiy yoki quruq matnni samimiy, do'stona suhbat uslubiga o'giradi.

---

### 5. 🧹 Chatni Tezkor Tozalash (`.purge` / `.del`)
- **`.del`** — Reply qilingan xabarni va buyruq xabarini bir zumda o'chiradi.
- **`.purge <soni>`** — Chatdagi o'zingiz yozgan so'nggi N ta xabarni tozalaydi (masalan: `.purge 20`).
- Reply qilingan xabardan keyingi xabarlarni tozalash imkoniyati mavjud.

---

### 6. 💵 Valyuta Kurslari va Ob-havo (`.kurs` / `.weather`)
- **`.kurs`** (yoki **`.valyuta`**) — O‘zbekiston Markaziy Banki (CBU) ning rasmiy bugungi Dollar, Yevro, Rubl kurslari va o'zgarish farqini ko'rsatadi.
- **`.weather [shahar]`** (yoki **`.obhavo`**) — Toshkent yoki istalgan shahar bo'yicha jonli harorat, sezilishi, namlik va shamol ma'lumotlarini taqdim etadi.

---

### 7. 🗣 Ovozli Xabar Qilib Yuborish (Text-to-Speech — `.voice`)
- **`.voice <matn>`** yoki matnga **reply `.voice`**:
  - Yozilgan matnni inson ovozidagi Telegram audio xabari (Voice Note) ga aylantirib yuboradi.

---

### 8. 🛡 Kengaytirilgan Media Anti-Delete (O'chirilgan xabarlarni tiklash)
- Suhbatdosh sizga yuborgan xabarini o'chirib yuborsa (faqat sizdan yoki ikkalangizdan ham), userbot uni darhol tutib oladi!
- **Matnli xabarlar:** O'chirilgan xabar matni, yuboruvchi ismi, Telegram ID raqami va yuborilgan vaqti bilan **"Saqlangan xabarlar" (Saved Messages)**ingizga yuboriladi.
- **Media xabarlar:** Rasmlar, videolar, ovozli xabarlar, dumaloq videolar va hujjatlar avtomatik keshlanadi. Suhbatdosh o'chirsa, media o'z holicha Saqlangan xabarlarga yetkaziladi.
- **LRU Kesh Himoyasi:** Disk to'lib qolmasligi uchun 300 MB hajmiy chegara va avtomatik davriy tozalash tizimi o'rnatilgan.

---

### 9. 📝 Chat va Guruh Xulosasi (Chat Summarizer)
- **`.summary`** — Guruh yoki shaxsiy chatdagi so'nggi 50 ta xabarni bir zumda o'qib, AI orqali asosiy mavzular, muhim qarorlar va keyingi vazifalarni o'zbek tilida xulosa qilib beradi.
- **`.summary <soni>`** — Masalan `.summary 100` deb istalgan sondagi xabarlarni tahlil qilish mumkin.

---

### 10. ⏰ Aqlli Eslatmalar Tizimi (Smart Reminders)
- SQLite ma'lumotlar bazasida saqlanuvchi va orqa fonda asinxron ishlovchi eslatmalar tizimi:
  - `.remind 15m dori ichish` — 15 daqiqadan so'ng
  - `.remind 2h hisobot topshirish` — 2 soatdan so'ng
  - `.remind 18:30 kechki ovqat` — bugun/ertaga aniq soatda
  - `.remind ertaga soat 9 da suhbat` — erkin o'zbek tilida yozilgan eslatmalarni AI orqali aniqlash
  - `.reminders` — Faol eslatmalar ro'yxati
  - `.delremind <ID>` — Eslatmani bekor qilish
- Vaqti kelganda eslatma "Saqlangan xabarlar"ingizga ovozli bildirishnoma bilan yuboriladi.

---

### 11. 🔗 QR-Kod va Stiker Xizmati
- **`.qr <matn/havola>`** — Istalgan matn yoki havolani yozib QR-kod rasm yaratadi.
- **`.qr`** — Rasmga reply qilganda (Gemini AI yordamida) rasmdagi QR-kodni o'qib beradi.
- **`.sticker`** — Rasmga reply qilib uni darhol sifatli Telegram stiker formatiga aylantiradi.
- **`.unsticker`** — Stikerga reply qilib uni oddiy rasmga o'girib beradi.

---

### 12. 🔍 Google va Wikipedia Qidiruv
- **`.google <so'rov>`** — DuckDuckGo orqali tezkor qidiruv, natija yo'q bo'lsa AI orqali.
- **`.wiki <so'rov>`** — Wikipedia'dan kerakli ma'lumotni to'g'ridan-to'g'ri o'qish (o'zbek va ingliz).

---

### 13. 👤 Profil va Xavfsizlik
- **`.bio <matn>`** — Profil tarjimayi holini tezda o'zgartirish.
- **`.name <ism>`** — Telegram ismingizni darhol yangilash.
- **`.photo`** — Rasmga reply qilib uni darhol profilingiz rasmi qilib qo'yish.
- **`.seen <ID>`** — Foydalanuvchining oxirgi marotaba qachon onlayn bo'lganini bilish.

---

### 14. 📂 Fayl va Media Konvertori
- **`.topdf`** — Rasmga reply qilib uni PDF hujjatga aylantirish.
- **`.tomp3`** — Videoga reply qilib undan faqat audioni (MP3) ajratib olish.

---

### 15. 🌐 Boshqa Foydali Buyruqlar
- **`.tr <matn>`** — Har qanday tildagi xabarni o'zbek yoki ko'rsatilgan tilga tarjima qilish.
- **`.ai <savol>`** — Gemini AI ga xohlagan chatdan turib to'g'ridan-to'g'ri savol berish.
- **`.calc <ifoda>`** — Xavfsiz AST kalkulyatori (`.calc 25 * 4 + 180 / 3`).
- **`.info`** — Tizim ma'lumotlari: Uptime, OS, AI modeli, baza statistikasi.
- **`.stop`** / **`.start`** — AI avto-javobni vaqtincha to'xtatish va qayta yoqish.
- **`.help`** — Barcha buyruqlar va imkoniyatlarning to'liq menyusi.

---

## 📋 Buyruqlar Jadvali

| Buyruq | Qo'llanilishi / Vazifasi |
| :--- | :--- |
| `.help` | Barcha buyruqlar bo'yicha to'liq qo'llanma menyusi |
| `.info` | Userbot tizim holati (Uptime, AI modeli, DB statistikasi) |
| `.stop` / `.pause` | AI avto-javob tizimini vaqtincha to'xtatish |
| `.start` / `.resume` | AI avto-javob tizimini qayta yoqish |
| `.see <savol>` | Rasmga reply qilib rasm mazmunini tahlil qilish yoki masalani yechish |
| `.ocr` | Rasmga reply qilib undagi barcha matnlarni ko'chirib olish |
| `.dl [havola]` | Instagram, TikTok, YouTube Shorts videolarini yuklash |
| `.fix` | Matnga reply qilib grammatik va imlo xatolarini tuzatish |
| `.formal` | Matnga reply qilib rasmiy ish uslubiga o'girish |
| `.informal` | Matnga reply qilib samimiy, do'stona uslubga o'girish |
| `.del` | Javob berilgan xabarni va buyruqni bir zumda o'chirish |
| `.purge [soni]` | Chatdagi so'nggi xabarlarni tozalash (masalan: `.purge 20`) |
| `.kurs` / `.valyuta` | Markaziy Bankning bugungi rasmiy valyuta kurslari |
| `.weather [shahar]` | Shahar bo'yicha jonli ob-havo ma'lumotlari |
| `.voice <matn>` | Matnni inson ovozidagi audio (Voice Note) ga aylantirish |
| `.text` | Ovozli xabarga reply qilinsa, uni matnga o'giradi |
| `.summary [soni]` | Chatdagi so'nggi xabarlarni tahlil qilib xulosalaydi |
| `.remind <vaqt> <matn>` | Aqlli eslatma o'rnatish (`.remind 10m dars`) |
| `.reminders` | Kutilayotgan faol eslatmalar ro'yxati |
| `.delremind <ID>` | Belgilangan eslatmani o'chirish |
| `.qr <matn>` / `.qr` | QR kod yaratish yoki o'qish |
| `.sticker` / `.unsticker` | Stikerga va rasmga aylantirish |
| `.google` / `.wiki` | Google yoki Wikipedia dan ma'lumot qidirish |
| `.bio` / `.name` / `.photo` | Profil tarjimayi holi, ismi va rasmini yangilash |
| `.topdf` / `.tomp3` | Rasm -> PDF, Video -> MP3 konvertatsiya |
| `.seen <user>` | Foydalanuvchi online statusini tekshirish |
| `.tr [til]` | Xabarni tarjima qilish |
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
GEMINI_MODEL=gemini-2.5-flash
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

---

## 🔒 Xavfsizlik va Maxfiylik
- `.env` fayli va `.session` ma'lumotlari `.gitignore` ga kiritilgan bo'lib, ular hech qachon GitHub repozitoriyasiga chiqmaydi.
- Ma'lumotlar bazasi (`messages.db`) va kesh fayllari faqat sizning mahalliy tizimingizda xavfsiz saqlanadi.

---

## 👤 Muallif
**Suxrob Sadullayev**
- GitHub: [@SuxrobSadullayev](https://github.com/SuxrobSadullayev)
- Loyiha bilan bog'liq taklif yoki muammolar bo'yicha Issues bo'limida qoldiring.
