# UyAI Production Deployment Guide (Phase 13)

Ushbu qo'llanma UyAI platformasini noldan boshlab toza Linux (Ubuntu 22.04 / 24.04 LTS) serverida to'liq production rejimida o'rnatish va ishga tushirish jarayonini bosqichma-bosqich tushuntiradi.

---

## 1. Minimal Server Talablari

- **OS**: Ubuntu 22.04 LTS yoki Debian 12
- **CPU**: Kamida 2 vCPU
- **RAM**: Kamida 4 GB RAM
- **Disk**: 40 GB NVMe SSD
- **Dasturiy ta'minot**: Docker (24.0+), Docker Compose (2.20+), Nginx, Certbot (Let's Encrypt SSL)

---

## 2. Loyiha Kodini O'rnatish

```bash
# Yangi foydalanuvchi bilan kirish
sudo useradd -m -s /bin/bash uyai
sudo usermod -aG docker uyai
sudo su - uyai

# Repository klonlash
git clone https://github.com/your-org/uyai-bot.git /home/uyai/app
cd /home/uyai/app
```

---

## 3. Konfiguratsiya Faylini Sozlash (`.env`)

`.env.example` namunasidan nusxa olib, haqiqiy xavfsiz qiymatlarni kiriting:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Quyidagi parametrlarni majburiy to'ldiring:
```ini
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000

# PostgreSQL (Kuchli parol qo'ying)
DATABASE_USER=uyai_user
DATABASE_PASSWORD=SuperStrongProductionPassword2026_xyz!
DATABASE_NAME=uyai_prod
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_URL=postgresql+asyncpg://uyai_user:SuperStrongProductionPassword2026_xyz!@postgres:5432/uyai_prod

# Telegram Bot
BOT_TOKEN=<your_telegram_bot_token>

# AI Broker (Google Gemini)
AI_BROKER_ENABLED=true
GEMINI_API_KEY=AQ.ProductionGeminiApiKeyGoesHere

# Admin Sessiyasi (Kamida 32 ta tasodifiy belgi)
ADMIN_SESSION_SECRET=e7b4c91a03f8485293d019fba834c910384756291a0c8b746529401827364519
ADMIN_SESSION_COOKIE_SECURE=true
ADMIN_ALLOWED_ORIGINS=https://admin.uyai.uz
MINIAPP_ALLOWED_ORIGINS=https://miniapp.uyai.uz

# Media saqlash
MEDIA_STORAGE_DIR=/app/media
```

---

## 4. Docker Compose Orqali Ishga Tushirish

Loyihada 4 ta servis birlashtirilgan (`docker-compose.yml`):
- `postgres`: PostgreSQL 16 ma'lumotlar bazasi.
- `api`: FastAPI backend REST API.
- `bot`: Telegram aiogram bot xizmati.
- `crm_worker`: amoCRM outbox sinxronizatsiya daemon servisi.

```bash
# 1. Konteynerlarni yig'ish va ishga tushirish
docker compose up -d --build

# 2. Ishga tushganini tekshirish
docker compose ps
docker compose logs -f api
```

---

## 5. Ma'lumotlar Bazasi Migratsiyasi va Superadmin Yaratish

Konteynerlar ko'tarilgach:

```bash
# 1. Migratsiyalarni eng oxirgi holatga keltirish
docker compose exec api alembic upgrade head

# 2. Superadmin hisobini yaratish (Parol Terminalda yashirin so'raladi)
# Mavjud user ID bo'yicha:
docker compose exec -it api python3 scripts/bootstrap_admin.py --user-id 1 --username admin --role superadmin

# Yoki yangi Telegram ID bo'yicha:
docker compose exec -it api python3 scripts/bootstrap_admin.py --telegram-id 7165062713 --username admin --role superadmin
```

---

## 6. Nginx Reverse Proxy va SSL Sozlash

Nginx konfiguratsiya fayli: `/etc/nginx/sites-available/uyai.conf`

```nginx
server {
    server_name api.uyai.uz;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    server_name admin.uyai.uz;
    root /home/uyai/app/admin/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

SSL sertifikatini o'rnatish:
```bash
sudo certbot --nginx -d api.uyai.uz -d admin.uyai.uz
```

---

## 7. Salomatlikni Tekshirish (Verification)

```bash
# API liveness
curl -I https://api.uyai.uz/health
# HTTP/2 200 OK {"status":"ok"}

# Database readiness
curl https://api.uyai.uz/health/db
# {"status":"ok","database":"connected","checked_at":"..."}
```
