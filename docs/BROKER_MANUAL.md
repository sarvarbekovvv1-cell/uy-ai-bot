# UyAI Brokerlar Uchun Amaliy Qo'llanma (Phase 13)

Ushbu hujjat UyAI platformasida faoliyat yurituvchi rieltorlar, sotuv va ijara brokerlari uchun mo'ljallangan.

---

## 1. Broker Rollari va Vakolatlari

Tizimda 3 toifadagi broker rollari mavjud:
1. **Head Broker (Bosh broker)**: Barcha lidlar va ko'rishlarni ko'ra oladi, brokerlar o'rtasida lidlarni taqsimlaydi va KPI ko'rsatkichlarini nazorat qiladi.
2. **Sales Broker (Sotuv brokeri)**: Faqat sotuv (`sale`) toifasidagi mulklar va o'ziga biriktirilgan mijozlar bilan ishlaydi.
3. **Rental Broker (Ijara brokeri)**: Faqat ijara (`rent`) toifasidagi mulklar va o'ziga biriktirilgan arizalar bilan ishlaydi.

---

## 2. Mijozlar Maxfiyligi (PII Boundary) Qoidasi

> [!IMPORTANT]
> **Telefon raqamlari himoyasi**: Yangi tushgan lidlarning telefon raqami dastlab yopiq (niqoblangan) bo'ladi (`+998 90 *** ** 33`).
> Broker lidni o'ziga biriktirib olganidan (`Claim`) yoki Bosh broker tomonidan biriktirilganidan so'nggina to'liq telefon raqami ko'rinadi.
> Boshqa brokerga tegishli lidning mijoz ma'lumotlarini ko'rish qat'iyan taqiqlangan (Gorizontal izolyatsiya).

---

## 3. Ish Jarayoni va Qadamlar

### 3.1. Yangi Lidni Qabul Qilish
1. Admin panelda yoki Telegram bot orqali yangi lid haqida bildirishnoma keladi.
2. **Tezkor javob berish (SLA)**: Birinchi aloqa 15 daqiqa ichida amalga oshirilishi shart. Bu ko'rsatkich to'g'ridan-to'g'ri kompaniyaning Kaizen KPI reytingiga ta'sir qiladi.
3. Lidni oching va mijoz bilan bog'laning.

### 3.2. Bosqichlarni O'tkazish (Stage Progression)
Mijoz bilan muloqotga qarab, lid statusini quyidagi tartibda yangilab boring:
- **`contacted` (Bog'lanildi)**: Mijozga birinchi qo'ng'iroq qilindi yoki xabar yozildi.
- **`qualified` (Malakalandi)**: Mijozning ehtiyoji, budjeti va xarid muddati aniqlandi.
- **`viewing_scheduled` (Ko'rish belgilandi)**: Obyektni borib ko'rish vaqti kelishildi.
- **`negotiation` (Muzokara)**: Narx va to'lov shartlari bo'yicha muzokaralar boshlandi.
- **`won` (Yutildi)**: Shartnoma imzolandi, bitim muvaffaqiyatli yakunlandi.
- **`lost` (Yo'qotildi)**: Mijoz xarid qilishdan bosh tortdi (sababi kiritilishi shart).

### 3.3. Eslatmalar va Vazifalar
- Har bir qo'ng'iroqdan keyin `Eslatma qo'shish` bo'limiga qisqacha muloqot xulosasini yozing.
- Keyingi aloqa uchun albatta sana va vaqtni belgilab `Vazifa (Follow-up)` yarating. Tizim belgilangan vaqtda eslatma yuboradi.

### 3.4. Ko'rishlarni Boshqarish
1. Haridor Mini App orqali e'lonni ko'rish arizasini yuborganida, u `Ko'rishlar` ro'yxatida paydo bo'ladi.
2. Arizani **Qabul qilish (Accept)** tugmasi orqali tasdiqlang.
3. Obyekt ko'rilgandan so'ng natijani belgilang:
   - `Qiziqdi (Interested)` — mijoz obyektni ma'qulladi, muzokara bosqichiga o'ting.
   - `Qiziqmadi (Not interested)` — mijozga ma'qul kelmadi.
   - `Qayta rejalashtirish (Reschedule)` — boshqa vaqtga ko'chirildi.
