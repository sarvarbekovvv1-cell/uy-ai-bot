# UyAI Loyihasini Topshirish va Qabul Qilish Dalolatnomasi (Handover - Phase 13)

Ushbu hujjat UyAI platformasini ishlab chiquvchilar guruhidan buyurtmachi va ekspluatatsiya qiluvchi kompaniya texnik jamoasiga to'liq topshirish (Handover Checklist) bo'yicha yo'riqnoma hisoblanadi.

---

## 1. Topshiriladigan Aktivlar va Resurslar

| Aktiv turi | Tavsifi va Joylashuvi | Holati |
|------------|----------------------|--------|
| **Dastur kodi** | To'liq backend, Telegram bot, Mini App va Admin Panel repozitoriyasi | Phase 1–13 to'liq yakunlangan |
| **Ma'lumotlar bazasi** | Alembic migratsiyalari (`001` dan `008_create_kaizen_tables` gacha) | PostgreSQL 16 moslashuvchan |
| **Konteynerlar** | Multi-stage `Dockerfile`, `.dockerignore`, `docker-compose.yml` | Production-ready |
| **Avtomatlashgan testlar** | Backend (340 ta test), Admin (27 ta), Mini App (18 ta) | 100% PASS, 0 ogohlantirish |
| **Texnik hujjatlar** | `docs/` papkasidagi 10 ta to'liq qo'llanma va spetsifikatsiyalar | To'liq rasmiylashtirilgan |

---

## 2. Tashqi Xizmatlar va Hisoblar Ro'yxati

Topshirish paytida buyurtmachi egaligiga o'tkazilishi lozim bo'lgan hisoblar:
1. **Telegram Bot**: `@BotFather` orqali yaratilgan bot tokeni va unga biriktirilgan WebApp havolasi.
2. **Google AI Studio**: Gemini Flash API kaliti (AI Broker uchun).
3. **amoCRM / Kommo**: Ishlab chiquvchi hisobi (Client ID, Client Secret, Webhook URL).
4. **Server va Domen**: Cloud / VPS server (SSH kirish kalitlari), DNS provayderi (A-yozuvlari).

---

## 3. Muntazam Ekspluatatsiya Talablari

Kompaniyaning texnik ma'murlari tomonidan bajarilishi zarur bo'lgan vazifalar:
- **Har kuni**: Zaxira nusxalash (`cron` orqali PostgreSQL dump olinishi va hajmi tekshirilishi).
- **Har hafta**: `amoCRM Outbox` va `Audit Log` jurnallaridagi xatoliklarni tahlil qilish.
- **Har oy**: `scripts/check_secrets.py` orqali xavfsizlik auditini yuritish va Python/Node.js kutubxonalarining xavfsizlik yangilanishlarini o'rnatish.
- **Chorakda bir**: Barcha xodimlar va brokerlarning kirish huquqlarini (RBAC) qayta ko'rib chiqish.

---

## 4. Qabul Qilish Tekshiruv Ro'yxati (Sign-Off Checklist)

- [x] Barcha 13 ta faza arxitekturaviy talablarga muvofiq bajarilgan.
- [x] Backend testlari (`pytest -W error`): 340 ta test to'liq muvaffaqiyatli.
- [x] Frontend testlari va build: Admin (27 passed), Mini App (18 passed).
- [x] Xavfsizlik auditi: Kod bazasida hech qanday yashirin parol yoki API kaliti yo'qligi tasdiqlangan.
- [x] Migratsiyalar: Alembic `008_create_kaizen_tables` bosh holatida.
- [x] Zaxira nusxa va tiklash vositalari: `docs/BACKUP_RESTORE.md` va `scripts/test_backup_restore.py` sinovdan o'tgan.
