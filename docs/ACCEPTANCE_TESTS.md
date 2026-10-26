# UyAI Acceptance Test Suite (Phase 13)

Ushbu hujjat UyAI platformasining Phase 13 doirasida yaratilgan va tekshirilgan End-to-End (E2E) qabul sinovlari (Acceptance Tests) ssenariylari, ularning arxitekturaviy bog'lanishi va real natijalarini tavsiflaydi.

Test fayli: [`tests/test_acceptance_e2e.py`](file:///Users/a0000/Desktop/uy%20ai%20bot/tests/test_acceptance_e2e.py)

---

## 1. Test Ssenariylari va Qamrovi

| Ssenariy ID | Nomlanishi | Qamrab olingan komponentlar | Kutilgan natija | Haqiqiy status |
|-------------|------------|----------------------------|-----------------|----------------|
| **ACC-01** | **Customer -> Search -> Favorite -> Viewing -> Lead -> Won -> Kaizen** | `Property`, `Favorite`, `ViewingRequest`, `LeadService`, `LeadNote`, `LeadFollowUp`, `CRMSyncEvent`, `KaizenAnalyticsService` | Haridor e'lonni tanlaydi, ko'rish buyurtmasi beradi, avtomat lead yaratiladi, broker bosqichlarni `won` gacha siljitadi, amoCRM outbox eventi navbatga qo'yiladi, Kaizen KPI funneli g'alabani qayd etadi. | **PASS** (0.42s) |
| **ACC-02** | **Property Owner -> Listing Submission -> Admin Moderation -> Approved** | `Property`, `/api/admin/v1/properties`, Admin Auth Cookie, CSRF Token, `AdminAuditEvent` | Mulk egasi e'lon topshiradi (`submitted`), admin moderatsiya ro'yxatida ko'radi, tasdiqlaydi (`approved`), audit logda o'zgarish qayd etiladi. | **PASS** (0.18s) |
| **ACC-03** | **Admin Property Creation -> RBAC -> Kaizen PDCA Lifecycle** | `/api/admin/v1/properties`, `KaizenService`, `PDCACycle`, `PDCAActionItem`, RBAC `require_permission` | Admin to'g'ridan-to'g'ri e'lon yaratadi (`auto_approve`), brokerlarga bu huquq taqiqlanadi (403), Kaizen PDCA sikli `draft -> planned -> in_progress -> review -> completed` bosqichlaridan o'tadi, baseline snapshot immutability saqlanadi. | **PASS** (0.28s) |

---

## 2. Batafsil Qadamlar

### ACC-01: Haridordan Kaizen KPI gacha to'liq sikl
1. **Mulk yaratilishi**: Sotuvchi (Seller) Toshkent shahri bo'yicha 2 xonali kvartirani tasdiqlangan holatda e'longa chiqaradi.
2. **Sevimlilarga qo'shish**: Haridor (Buyer) e'lonni o'z sevimlilariga (`Favorite`) qo'shadi.
3. **Ko'rish buyurtmasi**: Haridor sanani belgilab `ViewingRequest` yaratadi.
4. **Lead generatsiyasi**: `LeadService.ensure_lead_for_request()` orqali 1 ta aktiv lead ochiladi va savdo brokeriga biriktiriladi (`stage="new"`).
5. **Broker faoliyati**:
   - Broker aloqa qiladi va leadni `contacted` bosqichiga o'tkazadi.
   - Broker mijoz bilan muzokara tafsilotlarini `LeadNote` ga yozadi.
   - Broker `LeadFollowUp` (qo'ng'iroq vazifasi) belgilab uni yakunlaydi.
   - Lead ketma-ket `qualified -> viewing_scheduled -> negotiation -> won` bosqichlaridan o'tkaziladi.
6. **amoCRM Outbox**: `CRMSyncEvent` jadvalida ushbu lead uchun `amocrm` provayderli sinxronizatsiya hodisalari yaratiladi.
7. **Kaizen Tahlili**: `KaizenAnalyticsService.get_kpi_overview()` deterministik funneli:
   - `won_leads >= 1`
   - `reached_contacted >= 1`
   - `completed viewings >= 1`
   - `response_time sample_size >= 1` ekanligini tasdiqlaydi.

---

### ACC-02: E'lon Moderatsiyasi va Audit Xavfsizligi
1. **E'lon topshirish**: Sotuvchi tomonidan Chilonzor tumanidagi 3 xonali xonadon `submitted` statusida bazaga yoziladi.
2. **Moderatsiya ko'rigi**: Superadmin `/api/admin/v1/properties?status=submitted` orqali yangi e'lonni filtrlaydi.
3. **Tasdiqlash**: Admin `POST /api/admin/v1/properties/{id}/approve` endpointiga so'rov yuboradi (CSRF va HttpOnly cookie himoyalangan).
4. **Natija tekshiruvi**:
   - E'lon statusi `approved` bo'ladi.
   - `approved_at` vaqt tamg'asi o'rnatiladi.
   - `AdminAuditEvent` audit jadvalida `property.approve` amali, avvalgi va yangi statuslar bilan qayd etiladi.

---

### ACC-03: Admin Mulk Yaratish, RBAC va Kaizen PDCA
1. **Admin tomonidan mulk yaratish**: `POST /api/admin/v1/properties` endpointi orqali superadmin `auto_approve=True` parametri bilan yangi mulk ro'yxatini shakllantiradi.
2. **RBAC himoyasi**: Oddiy broker roli bilan xuddi shu amal bajarilganda tizim `403 Forbidden` bilan so'rovni to'xtatadi.
3. **Kaizen PDCA boshqaruvi**:
   - PDCA sikli `lead_response_optimization` maqsadi bilan yaratiladi.
   - Boshlang'ich KPI ko'rsatkichlari (baseline snapshot) fiksatsiya qilinadi.
   - Siklga `PDCAActionItem` (bajaruvchi broker bilan) qo'shiladi.
   - Sikl statuslari qat'iy davlat mashinasi asosida: `draft -> planned -> in_progress -> review -> completed` bosqichlaridan o'tadi.
   - Sikl baseline snapshotining o'zgarmasligi (immutability) tekshiriladi.

---

## 3. Testni Ishga Tushirish

Terminalda:
```bash
source .venv/bin/activate
pytest -W error tests/test_acceptance_e2e.py -v
```

Natija:
```text
tests/test_acceptance_e2e.py::test_acceptance_flow_customer_to_kaizen PASSED
tests/test_acceptance_e2e.py::test_acceptance_flow_property_moderation PASSED
tests/test_acceptance_e2e.py::test_acceptance_flow_admin_kaizen_pdca PASSED

============================== 3 passed in 1.26s ===============================
```
