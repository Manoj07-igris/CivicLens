# CivicLens AI — System Administration & Operations Guide

## 1. Environment & Deployment Configuration

All backend configuration is managed through environment variables or `backend/.env`.

### Core Production Settings
```ini
APP_ENV=production
ENABLE_API_DOCS=false
ALLOWED_HOSTS=127.0.0.1,localhost,civiclens.example.gov.in
CORS_ORIGINS=https://civiclens.example.gov.in
GEMINI_GLOBAL_RPM_CAP=30
ALLOW_SOURCE_MANAGEMENT=false
ALLOW_PORTAL_MANAGEMENT=false
SERVE_FRONTEND=true
```

---

## 2. System Administration API Endpoints

CivicLens provides a dedicated `/api/v1/system` router for administrative control and observability:

| Endpoint | Method | Description | Access / Parameters |
| :--- | :---: | :--- | :--- |
| `/api/v1/system/status` | `GET` | Database state, schema version, WAL size, and directory storage breakdown | Diagnostic |
| `/api/v1/system/stats` | `GET` | Aggregated record counts across all 5 modules, conversations, and tool runs | Monitoring |
| `/api/v1/system/resources` | `GET` | Real-time process memory (RSS), thread count, loaded indexes, and budget compliance | Resource Profiling |
| `/api/v1/system/backup` | `POST` | Trigger an immediate online hot backup using SQLite Backup API and prune older snapshots | Maintenance |
| `/api/v1/system/maintenance` | `POST` | Resolve interrupted comparisons, expire browser sessions, prune old activity, and run `PRAGMA optimize` | Scheduled Maintenance |
| `/api/v1/system/data` | `DELETE` | Wipe all citizen documents, chat records, and grievances | Requires `confirm=DELETE MY DATA` |
| `/api/v1/system/import-report` | `GET` | Inspect status of background legacy file importer | Diagnostics |

---

## 3. Database Maintenance & Backup Operations

### 3.1 SQLite WAL Mode & Backups
CivicLens uses SQLite configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and `busy_timeout=5000` to prevent database locks.

To trigger an online hot backup:
```powershell
# Via API call
curl -X POST http://127.0.0.1:8000/api/v1/system/backup
```
Backups are saved to `backend/data/backups/civiclens-YYYYMMDD-HHMMSS.db`. Older backups beyond `DATABASE_BACKUPS_KEEP` (default 5) are automatically pruned.

### 3.2 Scheduled Maintenance
It is recommended to run maintenance periodically (e.g. daily via cron or scheduled task):
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/system/maintenance -H "Content-Type: application/json" -d '{"remove_orphans": true, "vacuum": true}'
```

---

## 4. Administrative CLI & User Management (`app.cli`)

CivicLens includes a dedicated administrative CLI for local user management, password resets, and session revocations directly against SQLite:

```powershell
# In backend directory or with PYTHONPATH=backend:

# 1. Create a new administrator account interactively
python -m app.cli create-admin

# 2. List all registered citizens, roles, and active statuses
python -m app.cli list-users

# 3. Reset a user's password directly
python -m app.cli reset-password --email citizen@example.com

# 4. Deactivate a compromised or suspicious citizen account
python -m app.cli deactivate-user --email citizen@example.com

# 5. Reactivate an inactive citizen account
python -m app.cli activate-user --email citizen@example.com

# 6. Immediately terminate all active sessions for a citizen
python -m app.cli revoke-sessions --email citizen@example.com

# 7. Migrate all legacy pre-auth records (owner_id = 'local') to an administrator account
python -m app.cli claim-local-data --email admin@example.com
```

### 4.1 Claiming Legacy Data via Web UI
Administrators can also adopt unowned pre-auth records (`owner_id = 'local'`) directly from the CivicLens web interface:
- Look for the **"Claim Local Data"** button in the top navigation bar when logged in as an administrator.
- Clicking this executes `POST /api/v1/auth/claim-local-data`, migrating legacy documents, chat conversations, and grievances into the administrator's account in a single atomic transaction.

---

## 5. Resource Budget & Hardware Tuning

CivicLens is verified to run within a strict **6.0 GB RAM budget** on Windows 11 with an Intel Core i3 processor:

- **Process Memory Profile**:
  - FastAPI + SQLite idle: ~65 MB RSS
  - Active RAG retrieval: ~185 MB RSS
  - Headless Chromium demo session: ~120 MB RSS
- **Low-Spec Hardware (Lite Mode)**:
  On machines with 4 GB RAM, activate `LITE_MODE` overrides in `backend/.env` to halve embedding batch size, disable OCR, and throttle concurrency.
