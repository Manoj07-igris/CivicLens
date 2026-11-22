# CivicLens AI — Changelog

All notable changes to the CivicLens AI project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0-auth] — 2026-11-22

### Added
- **Production-Grade Authentication Core**:
  - Memory-hard Argon2id password hashing (`time_cost=3`, `memory_cost=64MB`, `parallelism=1`) with bounded concurrency (`asyncio.Semaphore(2)`).
  - Timing attack equalization: Nonexistent user login attempts trigger simulated Argon2 verification.
  - Password complexity policy: 12–128 characters, at least 3 of 4 categories (uppercase, lowercase, digits, symbols), bundled 10,000 common password blocklist check, and personal token (name/email) exclusion.
  - Opaque random server-side sessions stored as SHA-256 hashes in `auth_sessions` SQLite table.
  - Delivered via `HttpOnly`, `SameSite=Lax`, `Path=/api` cookies (`civiclens_session`).
  - CSRF defense-in-depth: Stateless synchronizer token `HMAC-SHA256(AUTH_SECRET_KEY, session_token_hash)` sent via `X-CSRF-Token` from memory, `X-Requested-With: CivicLens`, and strict `Origin` header matching.
  - Persistent brute-force lockout: 5 failed attempts per IP/email trigger exponential backoff lockout via `auth_throttle`.
  - Roles & Authorization: Citizen (`user`) and Administrator (`admin`). Automatic development bootstrapping for the first registered user.
  - Insecure Direct Object Reference (IDOR) immunity: All queries enforce `WHERE owner_id = current_user.id`; foreign access returns HTTP 404.
  - Administrative CLI (`app.cli`): User creation, listing, password reset, deactivation, activation, session revocation, and legacy data migration.
- **Frontend Authentication & Account Management**:
  - `AuthContext` and `useAuth` hook managing citizen state, capability introspection, and session lifecycle.
  - Intercepting `apiClient.js` with `credentials: "include"`, automatic CSRF header attachment, and 401 unauthenticated event dispatch.
  - Route guards: `ProtectedRoute` and `AdminRoute`.
  - New pages: `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/terms`, `/privacy`, `/settings`.
  - Tabbed Account Settings: Profile details, Security & Sessions (Argon2id password change and active session table with remote revocation), and Data & Privacy (portable record export and permanent account deletion modal).
  - 100% bilingual translation key parity across English (`en.js`) and Tamil (`ta.js`) (908/908 keys).
- **Dedicated Auth Test Suite**:
  - 36 tests in `backend/tests/auth/` verifying registration policies, lockout throttling, remote session revocations, origin and CSRF enforcement, default-deny route protection, cross-user IDOR isolation, legacy data claiming, CLI operations, and security hygiene.

---

## [1.0.0-hackathon] — 2026-11-21

### Added
- **Core Modules & Capabilities**:
  - Module 1 (Policy Intelligence): Ingestion of official gazette PDFs with PyMuPDF text extraction, chunking, and grounded Q&A with verifiable page-level citations.
  - Module 2 (Policy Change Detection): Structural pairwise diffing between policy notifications, deterministic fact change extraction, and citizen impact scoring.
  - Module 3 (Fact Verification): Tripartite truth verdicts (`SUPPORTED`, `REFUTED`, `UNVERIFIED`) against official sources.
  - Module 4 (Public Service Assistant): Portal matching, interactive checklist generation, and educational Playwright demo automation on local loopback portal.
  - Module 5 (Civic Grievance Assistant): Categorized complaint drafting with zero-echo PII redaction and simulated resolution tracking.
  - Central AI Agent: 7-stage orchestrator enforcing an Evidence Ledger (`[E]`, `[C]`, `[S]` citations) and human confirmation gates for sensitive actions.
  - SQLite persistence layer in WAL mode with foreign key constraints, 18 relational tables, and online hot backup support.
  - 219 passing automated tests with zero failures.
