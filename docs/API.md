# UyAI REST API Reference (Phase 13)

Ushbu hujjat UyAI platformasining barcha tashqi va ichki API interfeyslari, autentifikatsiya mexanizmlari, xatolik semantikasi, tezlik chegaralari (Rate Limiting) va xavfsizlik talablarini tavsiflaydi.

Avtomatik interaktiv OpenAPI/Swagger hujjatlari:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Xom OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## 1. Global Xavfsizlik va Protokol Qoidalari

### 1.1. Korrelyatsiya ID (`X-Request-ID`)
Har bir kiruvchi HTTP so'rovga `CorrelationIdMiddleware` tomonidan noyob UUID4 identifikatori biriktiriladi va javob sarlavhasida `X-Request-ID` sifatida qaytariladi. Barcha loglar ushbu ID bilan tamg'alanadi.

### 1.2. HTTP Xavfsizlik Sarlavhalari
Barcha javoblarga quyidagi qat'iy sarlavhalar avtomatik biriktiriladi:
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Frame-Options: SAMEORIGIN`
- Production rejimida: `Strict-Transport-Security: max-age=31536000; includeSubDomains`

### 1.3. Rate Limiting (Tezlik chegarasi)
Sensitiv endpointlar (masalan `/api/admin/v1/auth/login`) `SlidingWindowRateLimiter` orqali himoyalangan:
- Standart limit: 1 ta IP manzil uchun 60 soniyada maksimal 10 ta so'rov.
- Chegara oshganda qaytariladigan kod: `429 Too Many Requests`
- Javob sarlavhasi: `Retry-After: <soniya>`

---

## 2. Autentifikatsiya Usullari

### 2.1. Telegram Mini App Autentifikatsiyasi
- **Header**: `Authorization: Bearer <telegram_init_data>` yoki `X-Telegram-Init-Data: <string>`
- **Tekshiruv**: Bot token orqali HMAC-SHA256 imzosi tekshiriladi (`app/api/deps.py`).
- **Muddati**: `auth_date` 24 soatdan (86400 soniya) oshmasligi shart (replay attack himoyasi).
- **Ruxsat**: `buyer` va `seller` mijoz rollari.

### 2.2. Admin & Manager Panel Autentifikatsiyasi
- **Cookie**: `uyai_admin_session` (HttpOnly, SameSite=Lax, Secure in production).
- **Muddati**: 8 soat (28800 soniya).
- **CSRF Himoyasi**: Barcha o'zgartiruvchi so'rovlar (`POST`, `PUT`, `PATCH`, `DELETE`) uchun majburiy `X-CSRF-Token` sarlavhasi talab qilinadi.
- **Ruxsat (RBAC)**: `superadmin`, `head_broker`, `sales_broker`, `rental_broker`, `moderator`.

---

## 3. Standart Xatolik Semantikasi

API barcha xatoliklarni yagona JSON formatda qaytaradi:

```json
{
  "detail": "Foydalanuvchi topilmadi yoki parol noto'g'ri."
}
```

Validation xatoliklarida (`422 Unprocessable Entity`):
```json
{
  "detail": [
    {
      "loc": ["body", "price"],
      "msg": "Input should be greater than 0",
      "type": "greater_than"
    }
  ]
}
```

| HTTP Kod | Holat | Sabab |
|----------|-------|-------|
| `200 OK` | Muvaffaqiyatli | So'rov to'liq bajarildi |
| `201 Created` | Yaratildi | Yangi obyekt bazada shakllandi |
| `400 Bad Request` | Noto'g'ri so'rov | Biznes qoidalari yoki holat mashinasi buzildi |
| `401 Unauthorized` | Autentifikatsiyasiz | Sessiya muddati tugagan yoki initData yaroqsiz |
| `403 Forbidden` | Ruxsat yo'q | Foydalanuvchi roli bu amalga ega emas (RBAC) |
| `404 Not Found` | Topilmadi | Berilgan ID bo'yicha obyekt mavjud emas |
| `422 Unprocessable Entity` | Pydantic validation | Request body yoki schema talabga mos emas |
| `429 Too Many Requests` | Limit oshdi | Qisqa vaqt ichida juda ko'p so'rov yuborildi |
| `500 Internal Error` | Server xatosi | Kutilmagan backend istisnosi |
| `503 Service Unavailable` | Xizmat band | Ma'lumotlar bazasi yoki tashqi CRM javob bermayapti |

---

## 4. Asosiy Endpointlar Katalogi

### 4.1. Tizim Salomatligi (Health Checks)
- `GET /health` — Pod/Container liveness probe (`{"status": "ok"}`).
- `GET /health/db` — Database readiness probe (`SELECT 1`).

### 4.2. Telegram Mini App API (`/api/miniapp/v1`)
- `GET /api/miniapp/v1/properties` — Tasdiqlangan e'lonlar katalogi (filtrlar: narx, tuman, xonalar).
- `GET /api/miniapp/v1/properties/{id}` — E'lon tafsilotlari.
- `GET /api/miniapp/v1/properties/media/{media_unique_id}` — Xavfsiz media oqimi (LocalMediaStorage).
- `GET /api/miniapp/v1/favorites` — Haridorning saqlangan e'lonlari.
- `POST /api/miniapp/v1/favorites/{property_id}` — Sevimlilarga qo'shish.
- `DELETE /api/miniapp/v1/favorites/{property_id}` — Sevimlilardan o'chirish.
- `POST /api/miniapp/v1/viewing-requests` — Ko'rish yoki broker bilan bog'lanish arizasi berish.

### 4.3. Admin Autentifikatsiya va Profil (`/api/admin/v1/auth`)
- `POST /api/admin/v1/auth/login` — Staff login (Rate limited: 10/min). Cookie va CSRF beradi.
- `POST /api/admin/v1/auth/logout` — Sessiyani bekor qilish va cookie'ni tozalash.
- `GET /api/admin/v1/auth/me` — Joriy xodim profili, ruxsatlari va rollari.
- `PATCH /api/admin/v1/auth/settings/username` — Username o'zgartirish (superadmin yoki o'zi).
- `PATCH /api/admin/v1/auth/settings/password` — Parol yangilash (eski parolni tasdiqlash bilan).

### 4.4. E'lonlar va Moderatsiya (`/api/admin/v1/properties`)
- `GET /api/admin/v1/properties` — E'lonlar ro'yxati (barcha statuslar bo'yicha filtr).
- `POST /api/admin/v1/properties` — To'g'ridan-to'g'ri yangi mulk yaratish (`auto_approve` imkoni).
- `POST /api/admin/v1/properties/{id}/approve` — E'lonni tasdiqlash va ommaga chiqarish.
- `POST /api/admin/v1/properties/{id}/reject` — Sabab ko'rsatgan holda rad etish.
- `POST /api/admin/v1/properties/{id}/archive` — Arxivga o'tkazish.
- `POST /api/admin/v1/properties/upload-media` — Mulk rasmini yuklash (MIME va magic bytes tekshiruvi bilan).

### 4.5. Lidlar va Quvurlar (`/api/admin/v1/leads`)
- `GET /api/admin/v1/leads` — Lidlar ro'yxati (broker izolyatsiyasi bilan).
- `GET /api/admin/v1/leads/{id}` — Lid profili, aloqa tarixi, eslatmalar va vazifalar.
- `POST /api/admin/v1/leads/{id}/stage` — Lid bosqichini yangilash (`new -> contacted -> qualified...`).
- `POST /api/admin/v1/leads/{id}/assign` — Mas'ul brokerni biriktirish / o'zgartirish.
- `POST /api/admin/v1/leads/{id}/notes` — Yangi izoh qo'shish.
- `POST /api/admin/v1/leads/{id}/followups` — Qo'ng'iroq/vazifa rejalashtirish.

### 4.6. Kaizen & PDCA Tizimi (`/api/admin/v1/kaizen`)
- `GET /api/admin/v1/kaizen/overview` — Boshqaruv paneli KPI metrikalari va konversiya funneli.
- `GET /api/admin/v1/kaizen/recommendations` — Hevristik intellektual optimallashtirish tavsiyalari.
- `POST /api/admin/v1/kaizen/pdca` — Yangi PDCA siklini boshlash (boshlang'ich metrikalarni fiksatsiyalash).
- `GET /api/admin/v1/kaizen/pdca/{id}` — PDCA siklining borishi va harakat rejalari.
- `PATCH /api/admin/v1/kaizen/pdca/{id}/status` — PDCA sikli statusini o'zgartirish.

### 4.7. Tashqi CRM Outbox va Audit (`/api/admin/v1`)
- `GET /api/admin/v1/crm/outbox` — amoCRM sinxronizatsiya navbati holati.
- `POST /api/admin/v1/crm/outbox/{id}/retry` — Muvaffaqiyatsiz bo'lgan hodisani qayta navbatga qo'yish.
- `GET /api/admin/v1/audit` — O'zgarmas tizim audit loglari ro'yxati (kim, qachon, qaysi IP'dan nima qildi).
