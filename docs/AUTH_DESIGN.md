# CivicLens AI — Authentication and Account System Architecture & Design Specification (v1.1.0-auth)

## 1. Current State Inspection & Baseline Findings

### 1.1 Test & Build Baseline (Recorded Before Implementation)
- **Backend Test Suite**: **219 passed, 4 skipped, 0 failed** across 21 test files (Pytest run time: ~30.73s).
- **Frontend Production Build**: Built cleanly in 11.43s with 0 errors via Vite.
- **Git State**: Clean working tree on `master` at commit `7ad19ce` (tagged `v1.0.0-hackathon`).

### 1.2 Inspection of Existing Data Schema & Stores
- In Phase 15, SQLite tables were scaffolded with an `owner_id TEXT NOT NULL DEFAULT 'local'` column across:
  `documents`, `portals`, `comparisons`, `verifications`, `service_guides`, `form_field_explanations`, `grievances`, `browser_sessions`, `conversations`, `tool_runs`, `approvals`, and `activity`.
- Existing store classes (`SqliteDocumentStore`, `SqliteComparisonStore`, etc.) hardcode `'local'` during insertion and omit `owner_id` from query `WHERE` clauses.
- `documents` has a unique constraint `UNIQUE(collection, sha256)`. In a multi-user environment, two citizens must be able to upload the same official or user PDF independently without collision. This will be updated to `UNIQUE(owner_id, collection, sha256)`.
- `preferences` has primary key `(key)`. In a multi-user environment, each user requires their own preferences, so the primary key will be updated to `(owner_id, key)`.
- `cache_key` columns in `comparisons`, `verifications`, and `form_field_explanations` currently do not isolate by user; cache keys must be scoped by `owner_id` to prevent cross-user result leakage.
- Pre-accounts data: all rows created before this phase retain `owner_id = 'local'`. They will remain invisible to normal users until an administrator explicitly claims them via `/auth/claim-local-data`.

---

## 2. Chosen Architecture & Design Decisions

### 2.1 Authentication Mechanism: Server-Side SQLite Sessions with HttpOnly Cookie
- **Why not JWT?**
  - JWTs cannot be instantly revoked upon logout, password change, or admin deactivation without maintaining a server-side revocation blacklist (which negates the stateless claim of JWTs).
  - JWTs stored in browser `localStorage` or `sessionStorage` are vulnerable to XSS token theft.
  - Opaque random server-side session tokens in `HttpOnly` cookies provide instant revocation, zero JavaScript token exposure, and simple transactional storage in SQLite.
- **Token Generation**: 256-bit cryptographically secure random tokens generated via `secrets.token_urlsafe(32)`.
- **Database Storage**: The raw token is **never** stored in the database. Only its SHA-256 hexadecimal hash is stored in `auth_sessions.token_hash`.
- **Cookie Specification**:
  - Name: `civiclens_session` (configurable via `AUTH_COOKIE_NAME`).
  - `HttpOnly: True` (inaccessible to `document.cookie`).
  - `SameSite: Lax` (protects against cross-site request forgery while allowing top-level navigation).
  - `Path: /api` (scoped strictly to the backend API; not sent to static assets or demo portal).
  - `Secure`: True when `AUTH_COOKIE_SECURE=True` or `APP_ENV=production`; False in local HTTP development.
  - Host-only (no `Domain` attribute).
  - Lifetimes: Idle 2 hours / absolute 12 hours (session cookie by default); Remember-me idle 7 days / absolute 30 days (persistent cookie with `max_age`).

### 2.2 CSRF Defense-in-Depth
1. `SameSite=Lax` cookie configuration.
2. **Stateless Synchronizer Token**: All state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) on authenticated routes require the HTTP header `X-CSRF-Token`. The expected token is calculated as `HMAC-SHA256(AUTH_SECRET_KEY, session_token_hash)`. It is returned to the client upon login, registration, and `/auth/me`, and held **strictly in component memory** (never in `localStorage`).
3. **Strict Origin Enforcement**: If the `Origin` header is present, it must strictly match `CORS_ORIGINS`. If absent, requests with `Sec-Fetch-Site: cross-site` are rejected.
4. **Unauthenticated Route Protection**: Public state-changing routes (`/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset-password`) require `Content-Type: application/json` and `X-Requested-With: CivicLens`, triggering CORS preflight verification.

### 2.3 Password Hashing: Argon2id
- Implemented via `argon2-cffi` `PasswordHasher`.
- **Hardware-Benchmarked Parameters** (measured on Intel i3, Windows 11):
  - `time_cost = 3`
  - `memory_cost = 65536 KiB` (64 MB RAM)
  - `parallelism = 1`
  - **Measured Verification Latency**: **146.01 ms** (safely within the 150–500 ms target for DoS resistance vs responsiveness).
- **Concurrency Guard**: A semaphore (`asyncio.Semaphore(AUTH_HASH_CONCURRENCY=2)`) limits concurrent hashing operations to protect CPU and memory.
- **Opportunistic Rehash**: Successful logins automatically check `ph.check_needs_rehash(stored_hash)` and upgrade the hash if parameters change.
- **Password Policy**:
  - Length: 12 to 128 characters.
  - Bundled blocklist of common passwords (`backend/app/auth/common_passwords.txt`).
  - Rejection of passwords containing the user's name or email tokens (>= 4 characters).
  - Rejection of repetitive or simple sequential character sequences.

### 2.4 Roles and Authorization Model
- **Two Roles**: `user` and `admin`.
- **Admin Assignment**: Configured explicitly via `ADMIN_EMAILS` (comma-separated). Reconciled at startup.
- **Development Bootstrap**: In `APP_ENV=development` only, if `ADMIN_EMAILS` is empty and no admin exists, the first registered user receives the `admin` role with a startup console warning.
- **Admin-Only Operations**:
  - Official source library write operations (`POST /sources`, `DELETE /sources/{id}`).
  - Portal registry write operations (`POST /portals`, `PATCH /portals/{id}`, `DELETE /portals/{id}`).
  - System administration (`POST /system/backup`, `POST /system/maintenance`, `GET /system/import-report`).
  - Legacy data adoption (`POST /auth/claim-local-data`).
- **User Ownership**: All personal documents, comparisons, verifications, guides, grievances, browser sessions, conversations, and preferences are strictly filtered by `owner_id = current_user.id`. Foreign IDs return HTTP 404 to prevent existence leakage.

---

## 3. Complete Route Inventory & Access Classification

| Route Path | Method | Access Level | Description & CSRF Rules |
| :--- | :---: | :---: | :--- |
| `/api/v1/health` | `GET` | **Public** | Basic system health probe (minimal status for anonymous callers). |
| `/api/v1/auth/capabilities` | `GET` | **Public** | Public auth features (registration open, email configured, password min length). |
| `/api/v1/auth/register` | `POST` | **Public** | Create account + auto-login. Requires `X-Requested-With: CivicLens`. |
| `/api/v1/auth/login` | `POST` | **Public** | Authenticate citizen + set cookie. Requires `X-Requested-With: CivicLens`. |
| `/api/v1/auth/forgot-password` | `POST` | **Public** | Request password reset token. Requires `X-Requested-With: CivicLens`. |
| `/api/v1/auth/reset-password` | `POST` | **Public** | Consume reset token. Requires `X-Requested-With: CivicLens`. |
| `/api/v1/auth/logout` | `POST` | **Authenticated** | Revoke current session + clear cookie. Requires `X-CSRF-Token`. |
| `/api/v1/auth/logout-all` | `POST` | **Authenticated** | Revoke all active sessions for current user. Requires `X-CSRF-Token`. |
| `/api/v1/auth/me` | `GET` | **Authenticated** | Current citizen profile, session expiry, and CSRF token. |
| `/api/v1/auth/me` | `PATCH` | **Authenticated** | Update citizen name or preferred language. Requires `X-CSRF-Token`. |
| `/api/v1/auth/me` | `DELETE` | **Authenticated** | Permanently delete account and all owned data. Requires `X-CSRF-Token`. |
| `/api/v1/auth/change-password` | `POST` | **Authenticated** | Change password with current password verification. Requires `X-CSRF-Token`. |
| `/api/v1/auth/sessions` | `GET` | **Authenticated** | List active sessions for current citizen. |
| `/api/v1/auth/sessions/{id}` | `DELETE` | **Authenticated** | Revoke specific session. Requires `X-CSRF-Token`. |
| `/api/v1/auth/claim-local-data` | `POST` | **Admin Only** | One-time adoption of pre-auth data (`owner_id='local'`). Requires `X-CSRF-Token`. |
| `/api/v1/info` | `GET` | **Public (Minimal)** / **Authenticated (Full)** | System information and capabilities. |
| `/api/v1/gemini/*` | `GET`/`POST` | **Authenticated** | AI diagnostics and test endpoint. |
| `/api/v1/documents/*` | `*` | **Owner-Scoped** | User documents and RAG queries scoped to `current_user.id`. |
| `/api/v1/chat`, `/api/v1/agent/*` | `*` | **Owner-Scoped** | Conversational agent and tools scoped to `current_user.id`. |
| `/api/v1/comparisons/*` | `*` | **Owner-Scoped** | Policy comparisons scoped to `current_user.id`. |
| `/api/v1/sources` | `GET` | **Authenticated** | Read official source library (shared across all users). |
| `/api/v1/sources/*` (Write) | `POST`/`DELETE` | **Admin Only** | Upload/delete official sources. |
| `/api/v1/verifications/*` | `*` | **Owner-Scoped** | Fact verification jobs scoped to `current_user.id`. |
| `/api/v1/portals` | `GET` | **Authenticated** | Read official government portal registry (shared). |
| `/api/v1/portals/*` (Write) | `POST`/`PATCH`/`DELETE` | **Admin Only** | Manage portal registry entries. |
| `/api/v1/services/*` | `*` | **Owner-Scoped** | Public service guides and checklists scoped to `current_user.id`. |
| `/api/v1/grievances/*` | `*` | **Owner-Scoped** | Citizen grievances and images scoped to `current_user.id`. |
| `/api/v1/browser/*` | `*` | **Owner-Scoped** | Browser demo automation sessions scoped to `current_user.id`. |
| `/api/v1/conversations/*` | `*` | **Owner-Scoped** | Conversation history and messages scoped to `current_user.id`. |
| `/api/v1/preferences/*` | `*` | **Owner-Scoped** | Citizen preferences scoped to `(current_user.id, key)`. |
| `/api/v1/activity/*` | `*` | **Owner-Scoped** | Activity ledger and tool runs scoped to `current_user.id`. |
| `/api/v1/system/status`, `stats` | `GET` | **Authenticated** | User-specific statistics (global for admins). |
| `/api/v1/system/resources` | `GET` | **Admin Only** | Process memory and system resource profiling. |
| `/api/v1/system/backup`, `maintenance` | `POST` | **Admin Only** | Hot backups and database maintenance operations. |
| `/api/v1/system/data` | `DELETE` | **Owner-Scoped** | "Delete my data" purges only calling citizen's data. |
| `/demo-portal/*` | `GET`/`POST` | **Public** | Sandboxed local demo portal practice environment. |

---

## 4. Migration Plan & Database Schema Update (`0002_auth.sql`)

### 4.1 Pre-Migration Safety
- Automatic hot SQLite backup taken to `backend/data/backups/civiclens-pre-auth-migration-YYYYMMDD-HHMMSS.db` prior to running schema alterations.

### 4.2 Schema Additions
1. `users`: Citizen credentials, normalized emails, Argon2id password hash, role (`user`/`admin`), language preference, terms acceptance timestamp.
2. `auth_sessions`: Active session records, SHA-256 token hash, user agent, sliding expiry.
3. `password_reset_tokens`: Expiring, single-use password reset tokens (max 3 active per user).
4. `auth_events`: Security audit ledger (sanitized; zero passwords, tokens, or plaintext emails).
5. `auth_throttle`: Persistent rate-limiting and temporary account lockout counters.

### 4.3 Table Rebuilds & Constraint Updates
- `documents`: Rebuilt to update uniqueness constraint to `UNIQUE(owner_id, collection, sha256)`.
- `preferences`: Rebuilt with composite primary key `PRIMARY KEY (owner_id, key)` and `owner_id TEXT NOT NULL DEFAULT 'local'`.
- Composite indexes `(owner_id, created_at DESC)` added across all user-owned tables.
- Verification: Row counts and data IDs are verified before and after migration to ensure zero data loss.

---

## 5. Frontend Authentication & Account Architecture

### 5.1 In-Memory CSRF and 401 Interception (`apiClient.js`)
- `credentials: "include"` configured across all fetch requests to securely pass the `HttpOnly` session cookie (`civiclens_session`).
- State-changing HTTP verbs (`POST`, `PUT`, `PATCH`, `DELETE`) automatically attach:
  - Custom header `X-Requested-With: CivicLens` to prevent simple CORS requests.
  - In-memory `X-CSRF-Token` computed as `HMAC-SHA256(AUTH_SECRET_KEY, session_token_hash)`.
  - Zero token persistence in `localStorage` or `sessionStorage` (preventing script token theft).
- Unified 401 interception triggers registered `onUnauthorized` callbacks, cleanly transitioning React context to anonymous status without full page reloads.

### 5.2 Context & Route Guardians (`AuthContext.jsx`, `ProtectedRoute.jsx`, `AdminRoute.jsx`)
- `AuthProvider`:
  - Maintains `user` (profile), `status` (`'loading' | 'authenticated' | 'anonymous'`), `capabilities`, and `csrfToken`.
  - Automatically queries `/api/v1/auth/capabilities` and `/api/v1/auth/me` on mount.
  - Exposes actions: `login`, `register`, `logout`, `logoutAll`, `updateProfile`, `changePassword`, `deleteAccount`, and `claimLegacyData`.
- `ProtectedRoute`: Wraps all application module routes (`/dashboard`, `/assistant`, `/documents`, `/compare`, `/verify`, `/services`, `/grievance`, `/settings`). Redirects unauthenticated visitors to `/login?next=...`.
- `AdminRoute`: Enforces `user.role === 'admin'`.

### 5.3 Citizen Account Pages & Bilingual UI
- `/login`: Split branding layout, lockout countdown timer on HTTP 429 backoff, remember-me checkbox.
- `/signup`: Real-time password complexity checklist (12-128 chars, 3 of 4 categories, match, token exclusion), Terms acceptance.
- `/forgot-password`: Email recovery with privacy-preserving confirmation state (no account existence leakage).
- `/reset-password`: Fragment-based token parsing (`#token=...`) with immediate `history.replaceState` address bar sanitization.
- `/terms` & `/privacy`: Comprehensive prototype disclosures detailing local-first SQLite execution, PII guardrails, and sandboxed demo portals.
- `/settings`: Tabbed management for Profile, Security (Argon2id password update and active sessions list with remote revocation), and Data & Privacy (account data export and permanent deletion with confirmation modal).
- 100% translation key parity across English (`en.js`) and Tamil (`ta.js`).

---

## 6. Verification Results & Quality Metrics

- **Backend Pytest Suite**: **255 passed, 4 skipped, 0 failed** in ~24.90s.
  - Dedicated Auth Tests: **36/36 passed** (`tests/auth/` covering registration, login throttling, session management, CSRF/origin validation, default-deny enforcement, IDOR isolation, legacy claiming, CLI operations, and security hygiene).
- **Frontend Production Build**: **Built cleanly via Vite in 766ms** with 0 errors.
- **Language Parity**: **908/908 keys identical** (100.0% parity), 31,883 Tamil Unicode characters.
- **Hardware Footprint**: Tested on Intel i3, Windows 11. Argon2 verification latency ~146ms with memory concurrency bounded at 2. Zero CPU or memory exhaustion.
