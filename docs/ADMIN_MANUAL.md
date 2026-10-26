# UyAI Admin & Boshqaruv Paneli Bo'yicha Qo'llanma (Phase 13)

Ushbu qo'llanma UyAI platformasi administratorlari, bosh brokerlar va moderatsiya xodimlari uchun tizimning barcha imkoniyatlaridan to'liq va samarali foydalanish bo'yicha batafsil ko'rsatmalarni o'z ichiga oladi.

---

## 1. Kirish va Xavfsizlik

1. **Kirish manzili**: `http://<domain_yoki_ip>:5174` (ishlab chiqishda) yoki `https://admin.uyai.uz` (production).
2. **Kirish ma'lumotlari**:
   - Tizimga kirish uchun username va parolingizni kiriting.
   - Parol kamida 8 ta belgidan iborat bo'lishi shart.
   - 5 marta ketma-ket xato kiritilsa, hisob 15 daqiqaga bloklanadi (Brute-force himoyasi).
3. **Chiqish (Logout)**:
   - O'ng yuqori burchakdagi profilingiz tugmasini bosing va **Chiqish** tugmasini tanlang.
   - Bu amal barcha sessiya cookie'larini xavfsiz tarzda bekor qiladi.

---

## 2. Asosiy Bo'limlar va Funksiyalar

### 2.1. 📊 Bosh sahifa (Dashboard)
- Tizimdagi umumiy aktiv e'lonlar, yangi lidlar, rejalashtirilgan ko'rishlar soni.
- Brokerlar bo'yicha tezkor yuklama va haftalik faollik ko'rsatkichlari.

### 2.2. 🏠 E'lonlar va Moderatsiya
- **Ro'yxat va Filtrlar**: Barcha e'lonlarni statusi bo'yicha saralash (`Kutilmoqda`, `Tasdiqlangan`, `Rad etilgan`, `Qoralama`).
- **Yangi E'lon Qo'shish**:
  - `+ Yangi e'lon qo'shish` tugmasini bosing.
  - Sarlavha, narx, valyuta (USD/UZS), tuman, xonalar soni, maydon va kadastr holatini to'ldiring.
  - Rasm yuklash: `Fayl tanlash` orqali JPEG/PNG/WebP formatdagi suratlarni yuklang (tizim rasmlarning yaxlitligi va xavfsizligini avtomat tekshiradi).
  - Agar siz `superadmin` bo'lsangiz, `Darhol tasdiqlash (Auto-approve)` belgisini yoqishingiz mumkin.
- **Moderatsiya Amallari**:
  - Har bir e'lon kartasida `Tasdiqlash` yoki `Rad etish` tugmalari mavjud.
  - Rad etilganda, sabab (kamida 5 ta belgi) kiritilishi shart. Ushbu sabab e'lon egasiga Telegram orqali yuboriladi.

### 2.3. 🎯 Lidlar Pipeline (Quvur)
- Lidlar bosqichlari: `Yangi` -> `Bog'lanildi` -> `Malakalandi` -> `Ko'rish belgilandi` -> `Muzokara` -> `Muvaffaqiyatli (Won)` / `Bekor qilindi (Lost)`.
- **Brokеr biriktirish**: Boshqaruvchi har bir lidga mas'ul brokerni biriktirishi mumkin.
- **Eslatma va Vazifalar**: Mijoz bilan bo'lgan har bir muloqot bo'yicha izoh qoldirish va qayta qo'ng'iroq qilish sanasini belgilash mumkin.

### 2.4. 📅 Ko'rishlar (Viewings)
- Xaridorlar tomonidan tanlangan mulklarni ko'rish bo'yicha kelib tushgan arizalar.
- Broker arizani qabul qilishi, rad etishi yoki ko'rish yakunlanganidan so'ng natijani (`Qiziqdi`, `Qiziqmadi`, `Qayta belgilandi`) belgilashi lozim.

### 2.5. 📈 Kaizen / PDCA Intellektual Tizimi
- **KPI Funnel**: Savdo voronkasining har bir qadamidagi konversiya foizlari va brokerlarning birinchi javob berish tezligi (Median va 90-persentil).
- **Avtomatik Tavsiyalar**: Agar konversiya pasaysa yoki kechikishlar yuzaga kelsa, Kaizen mexanizmi tizimli yechimlarni tavsiya qiladi.
- **PDCA Sikllari**: Boshqaruvchi sifatni yaxshilash loyihasini ochishi (`Plan`), vazifalarni taqsimlashi (`Do`), natijalarni tekshirishi (`Check`) va standartlashtirishi (`Act`) mumkin.

### 2.6. 🔄 amoCRM Outbox Monitoring
- CRM tizimiga yuborilishi kutilayotgan yoki xatolik bergan voqealar navbati.
- Tarmoq uzilishi sababli to'xtab qolgan voqealarni `Qayta urinish (Retry)` tugmasi orqali qayta yuborish mumkin.

### 2.7. 🛡️ Audit Log
- Tizimdagi har bir muhim o'zgarish (e'lonni tasdiqlash, rolni o'zgartirish, narxni tahrirlash) o'zgarmas audit jurnaliga yoziladi.
- Kim bajarganligi, qachon, qaysi IP manzildan va avvalgi/yangi parametrlar ko'rsatiladi.

### 2.8. ⚙️ Sozlamalar (Settings)
- Superadmin yoki xodim o'z login username'ini xavfsiz o'zgartirishi.
- Parolni yangilash (eski parolni to'g'ri kiritish talab etiladi). Parol yangilansa, boshqa barcha qurilmalardagi sessiyalar darhol bekor qilinadi.
