# UyAI Qo'llab-Quvvatlash va Kafolat Shartlari (Support & SLA - Phase 13)

Ushbu hujjat UyAI platformasini topshirgandan so'ng kafolatli xizmat ko'rsatish, texnik qo'llab-quvvatlash darajalari (SLA) va muammolarni bartaraf etish tartibini belgilaydi.

---

## 1. Kafolat Qamrovi

**Kafolat muddati**: `[AGREED_WARRANTY_PERIOD]` (Shartnomada kelishilgan muddat).

### 1.1. Kafolat Ichiga Kiruvchi Holatlar
- Phase 1–13 texnik topshiriqlarida belgilangan funksiyalardagi dasturiy xatolar (bug fix).
- Ma'lumotlar bazasi yaxlitligi va migratsiyalardagi nuqsonlar.
- Arxitekturaviy xavfsizlik kamchiliklari (kod darajasidagi zaifliklar).

### 1.2. Kafolatdan Tashqari Holatlar
- Yangi biznes funksiyalar va dizayn o'zgarishlari talabi.
- Telegram, Google Gemini yoki amoCRM tashqi API spetsifikatsiyalari o'zgarishi natijasidagi nosozliklar.
- Server hosting provayderi (DNS, tarmoq, apparat ta'minoti) sababli yuzaga kelgan uzilishlar.
- Ruxsatsiz uchinchi shaxslar tomonidan server konfiguratsiyasi yoki ma'lumotlar bazasiga to'g'ridan-to'g'ri kiritilgan o'zgartirishlar.

---

## 2. Hodisalar Darajasi va Javob Berish Vaqti (SLA)

| Daraja | Tavsif | Birinchi javob vaqti | Tuzatish / Vaqtinchalik yechim (Workaround) |
|--------|--------|----------------------|---------------------------------------------|
| **Sev-1 (Favqulodda)** | Tizim to'liq to'xtagan: API ishlamayapti, bot xabarlarga javob bermayapti yoki ma'lumotlar bazasi uzilgan. | **15 daqiqa** | **2 soat ichida** |
| **Sev-2 (Jiddiy)** | Asosiy funksiyalardan biri ishlamayapti (masalan, amoCRM sinxronizatsiyasi to'xtagan yoki rasmlar yuklanmayapti), lekin tizimning qolgan qismi faol. | **1 soat** | **8 soat ichida** |
| **Sev-3 (Kichik)** | Kosmetik nuqsonlar, matnlardagi xatolar yoki kam uchraydigan interfeys noqulayliklari. | **4 soat** | **24-48 soat ichida** |

---

## 3. Aloqa va Eskalatsiya Tartibi

Nosozlik yuz berganda xabar berish tartibi:
1. **1-bosqich**: Navbatchi DevOps / Administrator orqali server holatini tekshirish (`docker compose ps`).
2. **2-bosqich**: Texnik yordam guruhiga nosozlik haqida to'liq hisobot yuborish (Xatolik skrinshoti, vaqti, `X-Request-ID` va tegishli log parchalari).
3. **Eskalatsiya kanallari**:
   - Telegram Texnik Guruhi: `@uyai_support_bot` / Jamoaviy chat.
   - Favqulodda qo'ng'iroq (faqat Sev-1 darajasi uchun).
