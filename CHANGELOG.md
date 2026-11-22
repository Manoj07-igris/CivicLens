# CivicLens AI — Changelog

All notable changes across the development of CivicLens AI are documented in this file.

---

## [1.1.0-auth] — 2026-11-22

### Authentication, Account System & Easy Start Automation (Hackathon Prototype)
- **Multi-User Authentication & Account System**: Production-grade Argon2id password hashing (`argon2-cffi`), opaque SQLite session tokens, HttpOnly `SameSite=Lax` cookies with standard path (`/`), and in-memory CSRF tokens.
- **Account Security & Throttling**: Progressive exponential IP and account lockout throttling for login attempts, password blocklist checking, and security audit event logging.
- **Per-User Data Isolation (IDOR Immunity)**: Enforced strict user ownership across all five modules (documents, comparisons, verifications, service guides, grievances, browser sessions, conversations).
- **Database Schema Expansion**: Added migration `0002_auth.sql` bringing total relational tables to 24 (including `users`, `auth_sessions`, `auth_throttle`, `password_reset_tokens`, `auth_events`, and `schema_migrations`).
- **Beginner-Friendly Start Automation**: Added double-click Windows launcher scripts (`START_CIVICLENS.bat`, `CHECK_CIVICLENS.bat`, `STOP_CIVICLENS.bat`) with automatic environment bootstrapping and safe health monitoring.
- **Test Suite Expansion**: Added 36 dedicated authentication and security hygiene tests, bringing the test suite to 264 automated tests across 23 test suites.

---

## [1.0.0-hackathon] — 2026-11-22

### Phase 16: Security, Testing and Final Integration
- Implemented comprehensive security hardening: `SecurityHeadersMiddleware` injecting nosniff, DENY, and same-origin headers; `TrustedHostMiddleware` for DNS rebinding protection.
- Created central sliding-window quota cap (`GEMINI_GLOBAL_RPM_CAP: 30`) across all Gemini invocations.
- Developed the Red-Team Adversarial Test Suite in `backend/tests/redteam/test_redteam_injection.py`.
- Developed Privacy Canaries Test Suite in `backend/tests/test_privacy_canaries.py` verifying zero secret token leakage.
- Added system resource profiling endpoint (`GET /api/v1/system/resources`) reporting RAM, active threads, and budget status.
- Built quality evaluation harness in `backend/evals/` evaluated on a small synthetic offline benchmark, producing `docs/EVAL_REPORT.md`.
- Added PowerShell automation tools in `scripts/` (`check_env.ps1`, `start_all.ps1`, `stop_all.ps1`, `reset_demo.ps1`, `warm_demo.ps1`, `run_evals.ps1`).
- Authored operational, user, admin, pitch, and demo guides across `docs/` noting prototype status and demo-only constraints.
- Validated test suite and production Vite build.

### Phase 15: Unified Database, History & Persistence
- Integrated SQLite database engine (`backend/data/civiclens.db`) in WAL mode with busy timeout handling.
- Implemented database migrations runner and applied initial schema provisioning.
- Implemented dual-layer persistence across document, comparison, source, verification, guide, grievance, and browser stores.
- Added conversation persistence, message storage, and activity ledger with 90-day retention pruning.
- Implemented hot online backup API (`POST /api/v1/system/backup`) and prototype safe wipe (`DELETE /api/v1/system/data`).

### Phase 14: Playwright Browser Automation (Controlled Demo Workflow)
- Implemented controlled Playwright browser service for local demo portal automation only (no external or real government integrations).
- Restrictive demo workflow requiring explicit human confirmation with SHA-256 state hashing.
- Auto-cleanup of browser sessions with 10-minute TTL and supervisor termination guards.

### Phase 13: Civic Grievance Assistant (Module 5)
- Automated citizen complaint drafting and structural classification.
- Decompression bomb protection for uploaded grievance photos (`GRIEVANCE_MAX_PIXELS: 25,000,000`).
- Strict in-memory PII masking for Aadhaar, PAN, phone numbers, and email addresses.

### Phase 12: Public Service Assistant (Module 4)
- Verified government portal registry with domain matcher.
- Step-by-step procedural checklist generator grounded in official source documentation.

### Phase 11: Fact Verification & Official Source Library (Module 3)
- Curated official source document library with SHA-256 integrity fingerprinting.
- Deterministic fact verification engine returning `SUPPORTED`, `CONTRADICTED`, `UNVERIFIED`, and `OUTDATED` atomic verdicts (plus `MIXED` for multi-claim statements).

### Phase 10: Policy Change Detection (Module 2)
- Pairwise document clause alignment and structural diffing.
- Deterministic fact delta extraction (currencies, dates, percentages) and citizen impact scoring.

### Phase 9: Central AI Agent Orchestrator & Tool Registry
- 7-stage orchestrator enforcing an Evidence Ledger (`[E]`, `[C]`, `[S]` citations).
- Tool registry safe execution pipeline with explicit human approval gates for external actions.

### Phases 1–8: Foundation, Bilingual UI, PDF Parsing, RAG
- Initialized FastAPI backend and React + Vite + Tailwind frontend.
- Built bilingual internationalization system with 100% key parity in English and Tamil.
- Implemented PyMuPDF text segmenter and multilingual FAISS vector search.
