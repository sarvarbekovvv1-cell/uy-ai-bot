# UyAI Tizimini Boshqarish va Nosozliklarni Bartaraf Qilish Qo'llanmasi (Runbook - Phase 13)

Ushbu runbook tizim administratorlari va DevOps muhandislari uchun nosozliklar yuz berganda (Incident Triage), muntazam xizmat ko'rsatishda va favqulodda tiklash holatlarida (Disaster Recovery) tezkor harakatlar rejasini taqdim etadi.

---

## 1. Servislarni Boshqarish (Muntazam Amallar)

### 1.1. Servislar Holatini Ko'rish
```bash
docker compose ps
```

### 1.2. Loglarni Kuzatish
```bash
# Backend API loglari
docker compose logs -f --tail=100 api

# Bot loglari
docker compose logs -f --tail=100 bot

# CRM Worker loglari
docker compose logs -f --tail=100 crm_worker

# Ma'lumotlar bazasi loglari
docker compose logs -f --tail=100 postgres
```

### 1.3. Qayta Ishga Tushirish (Graceful Restart)
```bash
# Alohida servisni qayta yuklash
docker compose restart api

# Barcha servislar
docker compose restart
```

---

## 2. Nosozliklar Ssenariylari (Incident Triage)

### Ssenariy 1: Telegram Bot Xabarlarga Javob Bermayapti
- **Alomat**: Foydalanuvchilar botga yozganda xabarlar o'qilmaydi yoki javob kelmaydi.
- **Tekshiruv**:
  ```bash
  docker compose logs bot --tail=50
  ```
- **Mumkin bo'lgan sabablar**:
  1. `BOT_TOKEN` noto'g'ri yoki Telegram tomonida bekor qilingan.
  2. Boshqa jarayon (process) ayni bot tokeni bilan polling boshlagan (`Conflict: terminated by other getUpdates request`).
  3. Internet/DNS uzilishi.
- **Yechim**:
  Eski jarayonlarni to'xtatish: `pkill -f "python.*app.bot.main"` va bot konteynerini qayta ishga tushirish: `docker compose restart bot`.

---

### Ssenariy 2: API 500 yoki 503 Xatolik Qaytarmoqda
- **Alomat**: Sayt yoki Mini App ochilganda `Internal Server Error` yoki `Service Unavailable` chiqadi.
- **Tekshiruv**:
  ```bash
  curl http://localhost:8000/health/db
  docker compose logs api --tail=50 | grep -E "ERROR|CRITICAL"
  ```
- **Yechim**:
  - Agar `/health/db` xato bersa: PostgreSQL konteyneri yoki xotira (RAM) to'lganligini tekshiring (`docker stats`).
  - Ma'lumotlar bazasi aloqasini qayta tiklash: `docker compose restart postgres api`.

---

### Ssenariy 3: amoCRM ga Lidlar Sinxronlashmayapti
- **Alomat**: Admin panelda `amoCRM Outbox` bo'limida hodisalar `failed` statusiga tushib qolgan.
- **Tekshiruv**:
  ```bash
  docker compose logs crm_worker --tail=100
  ```
- **Yechim**:
  1. amoCRM access tokenining muddati tugaganligini tekshiring.
  2. Subdomain yoki API kalitlarini `.env` da yangilang.
  3. Xatolik tuzatilgach, Admin panel orqali `Qayta urinish (Retry)` tugmasini bosing yoki `scripts/run_crm_worker.py` avtomatik qayta urinishlarini kuting.

---

### Ssenariy 4: 429 Too Many Requests (Rate Limiter Blokirovkasi)
- **Alomat**: Xodim admin panelga kirmoqchi bo'lganda `Rate limit exceeded` xabari chiqadi.
- **Sabab**: Xodim qisqa vaqt ichida juda ko'p marotaba login so'rovini yuborgan.
- **Yechim**:
  1. 60 soniya kutish kifoya (Sliding window 60 soniyadan so'ng avtomat ochiladi).
  2. Favqulodda holatda backend xizmatini qayta ishga tushirish in-memory limit hisoblagichlarini nollashtiradi: `docker compose restart api`.

---

## 3. Favqulodda Tiklash (Disaster Recovery)

Tizim to'liq ishdan chiqqan taqdirda, oxirgi zaxira nusxadan (backup) qayta tiklash:

1. **Servislarni to'xtatish**:
   ```bash
   docker compose stop api bot crm_worker
   ```
2. **Bazani tiklash**:
   ```bash
   # docs/BACKUP_RESTORE.md yo'riqnomasiga asosan:
   export PGPASSWORD="<db_parol>"
   pg_restore -h localhost -p 5432 -U uyai_user -d uyai_prod -c --if-exists /backups/uyai_backup_<sana>.dump
   ```
3. **Yaxlitlikni tekshirish**:
   ```bash
   python3 scripts/test_backup_restore.py
   ```
4. **Servislarni qayta yoqish**:
   ```bash
   docker compose start
   ```
