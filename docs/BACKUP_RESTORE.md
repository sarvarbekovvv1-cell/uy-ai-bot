# UyAI — Database Backup & Disaster Recovery Guide

This document defines standard operating procedures for backing up, verifying, and restoring the UyAI production PostgreSQL database.

---

## 1. Security & Credential Handling Principles

> [!IMPORTANT]
> **Never pass passwords directly in command arguments.**
> Passing `--password=<secret>` or placing credentials in command lines exposes them to system process listings (`ps aux`), process monitors, and shell histories (`~/.bash_history`, `~/.zsh_history`).

### Recommended Authentication Methods

#### Option A: Password File (`~/.pgpass`) — Recommended
Create a protected `~/.pgpass` file on the deployment host:
```bash
# Format: hostname:port:database:username:password
localhost:5432:uyai_db:uyai_user:your_strong_production_password
```
Set strict permissions (PostgreSQL refuses to read `.pgpass` if world/group readable):
```bash
chmod 0600 ~/.pgpass
```

#### Option B: Environment Variable
Export `PGPASSWORD` within a restricted subshell or script:
```bash
export PGPASSWORD="your_strong_production_password"
# Execute backup
unset PGPASSWORD
```

---

## 2. Backup Procedures

### A. Full Custom-Format Compressed Backup (`pg_dump`)
The custom archive format (`-F c`) is compressed, flexible, and supports parallel restoration:

```bash
# Set parameters
BACKUP_DIR="/var/backups/uyai"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/uyai_backup_${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"
chmod 0700 "${BACKUP_DIR}"

# Execute dump
pg_dump \
  -h "${DATABASE_HOST:-localhost}" \
  -p "${DATABASE_PORT:-5432}" \
  -U "${DATABASE_USER:-uyai_user}" \
  -d "${DATABASE_NAME:-uyai_db}" \
  -F c \
  -b \
  -v \
  -f "${BACKUP_FILE}"

# Verify non-zero size
if [ -s "${BACKUP_FILE}" ]; then
  echo "✅ Backup successfully created: ${BACKUP_FILE} ($(du -h ${BACKUP_FILE} | cut -f1))"
else
  echo "❌ Backup failed or produced empty file!" >&2
  exit 1
fi
```

### B. Automated Daily Cron Job
Add to `/etc/cron.d/uyai_backup`:
```cron
# Daily backup at 03:00 UTC with 14-day retention
0 3 * * * uyai /usr/local/bin/uyai_backup.sh >> /var/log/uyai_backup.log 2>&1
```

Retention script snippet:
```bash
# Prune backups older than 14 days
find /var/backups/uyai -type f -name "uyai_backup_*.dump" -mtime +14 -delete
```

---

## 3. Restoration Procedure

### Prerequisites
1. Stop mutating services to prevent split-brain transactions during restore:
   ```bash
   docker compose stop api bot crm_worker
   ```
2. Verify target database availability:
   ```bash
   pg_isready -h "${DATABASE_HOST:-localhost}" -p "${DATABASE_PORT:-5432}"
   ```

### Execution (`pg_restore`)
```bash
BACKUP_FILE="/var/backups/uyai/uyai_backup_20261026_030000.dump"

pg_restore \
  -h "${DATABASE_HOST:-localhost}" \
  -p "${DATABASE_PORT:-5432}" \
  -U "${DATABASE_USER:-uyai_user}" \
  -d "${DATABASE_NAME:-uyai_db}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  -v \
  "${BACKUP_FILE}"
```

### Post-Restore Verification
1. Run database integrity check script:
   ```bash
   python3 scripts/test_backup_restore.py --verify-only
   ```
2. Check Alembic migration head alignment:
   ```bash
   .venv/bin/alembic current
   ```
3. Restart application services:
   ```bash
   docker compose start api bot crm_worker
   ```
4. Verify HTTP and DB readiness endpoints:
   ```bash
   curl -f http://localhost:8000/health
   curl -f http://localhost:8000/health/db
   ```

---

## 4. Rollback Strategy

If a newly deployed migration or release causes critical failures:
1. **Immediate Service Isolation:**
   ```bash
   docker compose stop api bot crm_worker
   ```
2. **Restore Pre-Deployment Snapshot:**
   Restore the database dump created immediately prior to deployment.
3. **Rollback Git Release / Container Image:**
   ```bash
   docker compose up -d --no-deps api bot crm_worker
   ```
4. **Health Check Verification:**
   Ensure `/health` and `/health/db` return HTTP 200.
