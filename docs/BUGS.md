# CivicLens AI — Triage & Bug Tracker

## Bug Tracking Framework

All bugs identified during testing, auditing, and integration are logged with standard severity levels:
- **P0 (Critical)**: System crash, security vulnerability, PII leakage, data corruption, or unrecoverable lock.
- **P1 (High)**: Core module failure, missing citation verification, incorrect approval gate bypass.
- **P2 (Medium)**: Transient timeout, non-blocking UI glitch, minor translation discrepancy.
- **P3 (Low)**: Styling imperfection, cosmetic warning, documentation typo.

---

## Resolved Issues Matrix

| ID | Module / Area | Severity | Description | Root Cause | Resolution | Status |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| **BUG-001** | Database / Portals | P1 | SQLite `IntegrityError` when inserting portals without department | Schema had `department TEXT NOT NULL` while API allowed optional department | Updated store to default department to empty string `""` on insert | **RESOLVED** |
| **BUG-002** | File Storage | P1 | Intermittent `PermissionError: [WinError 5]` on Windows atomic replacement | Windows file locks held momentarily by indexing or anti-malware services | Added retry loop with exponential jitter and unique temporary filenames | **RESOLVED** |
| **BUG-003** | Test Harness | P2 | Mock leakage in singleton services across test runs | `set_gemini_service` didn't reset downstream singleton service caches | Added cascading reset calls to clear `_rag_service_instance`, `_verification_service_instance`, etc. | **RESOLVED** |
| **BUG-004** | Security | P0 | XML boundary injection risk in untrusted document snippets | Malicious document content containing `</context>` could escape prompt fences | Implemented XML fence escaping and untrusted text wrapping | **RESOLVED** |
| **BUG-005** | Browser Service | P1 | Potential orphan `chrome.exe` processes on abrupt server shutdown | Async Playwright context not deterministically closed on SIGINT | Added `atexit` process supervisor and explicit PID registration/reaping | **RESOLVED** |
| **BUG-006** | Agent | P1 | In-memory conversation state lost between restarts | Conversations were initially pinned to memory and client localStorage | Integrated SQLite conversational history tables with session resume | **RESOLVED** |
| **BUG-007** | Frontend | P2 | Large bundle chunk warning (>500 kB) during Vite build | Full lucide-react icon set and localized asset bundles imported statically | Verified chunk sizes; documented tree-shaking and dynamic import path | **MONITORED** |

---

## Active & Verification Checklist

- [x] PII Masker universal test coverage across 5 modules.
- [x] Path traversal test suite verifying Windows reserved filenames (`CON`, `PRN`, `NUL`).
- [x] SQLite dual-write consistency tests for all 8 entities.
- [x] Host header enforcement and security header middleware verification.
- [x] Quota cap guard verification under rapid request bursts.
