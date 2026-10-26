# UyAI Xavfsizlik Arxitekturasi va Tahdidlar Modeli (Security Architecture - Phase 13)

Ushbu hujjat UyAI platformasining axborot xavfsizligi arxitekturasi, tahdidlar tahlili (STRIDE), himoya chegaralari va amalga oshirilgan xavfsizlik mexanizmlarini to'liq yoritadi.

---

## 1. Xavfsizlik Prinsiplari va Chegaralari

### 1.1. Autentifikatsiya va Parollar Himoyasi
- **Parol xeshlash**: Barcha xodimlar parollari zamonaviy **scrypt** algoritmi orqali (`hashlib.scrypt`, n=16384, r=8, p=1, salt=16 bytes) xeshlanadi. Hech qanday ochiq matn (plain-text) yoki oddiy MD5/SHA saqlanmaydi.
- **Sessiyalar boshqaruvi**: `AdminSession` jadvali orqali server-side sessiya boshqaruvi. Sessiya cookie'si:
  - `HttpOnly`: JavaScript orqali o'qib bo'lmaydi (XSS himoyasi).
  - `SameSite=Lax`: Tashqi saytlardan avtomat yuborilmaydi (CSRF boshlang'ich to'sig'i).
  - `Secure`: Faqat HTTPS orqali uzatiladi (Production rejimida majburiy).
  - Muddati: Maksimal 8 soat (28800 soniya).
- **Brute-Force Himoyasi**: 5 ta ketma-ket muvaffaqiyatsiz login urinishidan so'ng hisob 15 daqiqaga bloklanadi (`failed_login_attempts` va `locked_until`).

### 1.2. CSRF Himoyasi
- Barcha holatni o'zgartiruvchi HTTP so'rovlar (`POST`, `PUT`, `PATCH`, `DELETE`) `verify_csrf_token` dependency orqali tekshiriladi.
- Kriptografik `secrets.token_urlsafe(32)` orqali yaratilgan CSRF tokeni va `hmac.compare_digest` yordamida timing-attack'lardan himoyalangan tekshiruv.

### 1.3. Rolga Asoslangan Kirish Nazorati (RBAC)
- 7 ta alohida rol: `superadmin`, `head_broker`, `sales_broker`, `rental_broker`, `moderator`, `buyer`, `seller`.
- Vertikal eskalatsiya himoyasi: Oddiy mijoz yoki brokerlar ma'muriy endpointlarga kira olmaydi (`403 Forbidden`).
- Gorizontal izolyatsiya: Broker faqat o'ziga biriktirilgan lidlar va o'z toifasidagi mulklarni ko'ra oladi.
- Oxirgi superadminni himoyalash: Tizimdagi yagona superadmin rolini o'chirib yoki o'zgartirib bo'lmaydi.

### 1.4. Mijozlar Maxfiyligi (PII Boundary)
- Haridorlarning telefon raqamlari barcha umumiy ro'yxatlarda niqoblanadi (`+998 90 *** ** 33`).
- Faqatgina lidni o'ziga qabul qilgan mas'ul broker yoki superadmin to'liq raqamni ko'rish huquqiga ega.

### 1.5. Media Fayllar Xavfsizligi (`LocalMediaStorage`)
- **Hajm chegarasi**: Maksimal 10 MB.
- **MIME va Magic Bytes**: Fayl kengaytmasiga ishonilmaydi. Faylning boshlang'ich baytlari tekshiriladi (`image/jpeg`, `image/png`, `image/webp`).
- **Path Traversal Himoyasi**: UUID4 asosidagi fayl nomlari va `os.path.commonpath` orqali saqlash papkasidan tashqariga chiqib ketish urinishlari to'liq to'siladi.
- **Orphan Cleanup**: Har qanday e'longa bog'lanmagan qoldiq fayllar avtomat tozalanadi.

---

## 2. STRIDE Tahdidlar Tahlili

| Tahdid toifasi (STRIDE) | Ehtimoliy xavf | Ko'rilgan muhandislik chorasi |
|-------------------------|----------------|-------------------------------|
| **S - Spoofing** (Soxtalashtirish) | Birovning nomidan kirish yoki Telegram initData'ni soxtalashtirish | Bot token HMAC-SHA256 imzosi, scrypt parollar, 24 soatlik initData muddati. |
| **T - Tampering** (O'zgartirish) | Tranzitdagi ma'lumotlarni yoki narxlarni o'zgartirish | Majburiy HTTPS/HSTS, Pydantic qat'iy validation, double-submit CSRF. |
| **R - Repudiation** (Rad etish) | Xodim o'z bajargan amalini inkor qilishi | `AdminAuditEvent` o'zgarmas audit loglari (Actor ID, Action, IP, Timestamp, Changes). |
| **I - Information Disclosure** (Ma'lumot sizishi) | Xaridor telefon raqamlari yoki API kalitlari sizib chiqishi | Gorizontal PII niqoblash, `scripts/check_secrets.py` CI darajasidagi audit. |
| **D - Denial of Service** (Xizmatdan to'xtatish) | Login yoki media yuklash orqali serverni to'ldirish | `SlidingWindowRateLimiter` (10 req/min), maksimal yuklama o'lchami cheklovlari. |
| **E - Elevation of Privilege** (Huquq oshirish) | Brokerning o'zini superadmin qilishga urinishi | RBAC `require_permission` tekshiruvlari, superadmin rollarini himoyalovchi triggerlar. |

---

## 3. Ishlab Chiqarish Muhiti Xavfsizlik Kafolatlari (Fail-Fast)

`app/config.py` tizimi ishlab chiqarish rejimida (`APP_ENV=production`) quyidagi xavfli holatlar aniqlansa, darhol serverni ishga tushirishdan bosh tortadi:
1. `APP_DEBUG=true` bo'lsa.
2. `DATABASE_URL` SQLite bo'lsa (PostgreSQL talab qilinadi).
3. `MINIAPP_DEV_AUTH_ENABLED=true` bo'lsa.
4. `ADMIN_SESSION_COOKIE_SECURE=false` bo'lsa.
5. `ADMIN_SESSION_SECRET` 32 belgidan kam bo'lsa.
6. CORS ruxsatlarida `*` belgisi mavjud bo'lsa.
7. `BOT_TOKEN` bo'sh bo'lsa.
8. `DATABASE_PASSWORD` standart qiymatda qolgan bo'lsa.
9. `AI_BROKER_ENABLED=true` holatida `GEMINI_API_KEY` kiritilmagan bo'lsa.
