# CivicLens AI — Comprehensive Test Plan & Traceability Matrix

## 1. Quality Assurance Strategy

CivicLens enforces automated, layered testing ensuring that every civic intelligence capability is grounded, privacy-preserving, and verifiable.

```
       [ E2E System Integration & Scenarios ]
                 ▲
                 │
       [ Red-Team & Adversarial Security ]
                 ▲
                 │
       [ Module Quality Benchmark Harness ]
                 ▲
                 │
   [ Unit & Functional Tests (219+ Tests) ]
```

---

## 2. Requirement Traceability Matrix

| Requirement / Module | Architectural Scope | Verification File(s) | Status |
| :--- | :--- | :--- | :---: |
| **M1: Policy Intelligence** | PDF parsing, OCR fallback, FAISS vector index, page citations | `test_documents.py`, `test_rag.py` | **VERIFIED** |
| **M2: Change Detection** | Deterministic token diffing, clause matching, severity classification | `test_comparison.py`, `test_fact_extractor.py` | **VERIFIED** |
| **M3: Fact Verification** | Official source library, SHA-256 fingerprints, tripartite verdicts | `test_verification.py`, `test_sources.py` | **VERIFIED** |
| **M4: Public Services** | Verified portal registry, checklist generation, domain routing | `test_services.py`, `test_portals.py` | **VERIFIED** |
| **M5: Civic Grievances** | Complaint drafting, image decompression bomb defense, PII masking | `test_grievances.py`, `test_security.py` | **VERIFIED** |
| **Central AI Agent** | 7-stage orchestrator, Evidence Ledger (E/C/S), step caps, approvals | `test_agent.py`, `test_e2e_integration.py` | **VERIFIED** |
| **Persistence & Storage** | Dual-write filesystem + SQLite WAL, migrations, online hot backup | `test_db.py`, `test_system.py`, `test_privacy_canaries.py` | **VERIFIED** |
| **Authentication & Accounts** | Argon2id, HttpOnly sessions, CSRF tokens, lockout throttle, IDOR immunity | `backend/tests/auth/` (36 tests) | **VERIFIED** |
| **Security & Privacy** | PII guard, XML boundary sanitization, host header, security headers | `test_security.py`, `test_security_audit.py`, `test_redteam_injection.py` | **VERIFIED** |
| **Bilingual Parity** | English & Tamil 100% key parity, script detection, Tamil prompt guidance | `test_language_parity.py` | **VERIFIED** |
| **Browser Automation** | Controlled demo portal Playwright workflow, PID supervisor, TTL | `test_browser.py`, `test_demo_portal.py` | **VERIFIED** |

---

## 3. Compliance Matrix: 20 Core AI & Ethical Rules

| Rule # | Requirement Description | Enforcing Implementation | Verifying Tests |
| :---: | :--- | :--- | :--- |
| **1** | Evidence-grounded answers only | `AgentOrchestrator._extract_grounded_evidence` | `test_agent.py`, `test_rag.py` |
| **2** | Page-level citation anchors required | `RAGService.search` returning 1-based `page_number` | `test_rag.py`, `test_e2e_integration.py` |
| **3** | Honest uncertainty over hallucinations | `RAG_MIN_SCORE: 0.65`, fallback uncertainty prompts | `test_agent.py`, `test_chat.py` |
| **4** | Tripartite verification verdicts | `VerificationVerdict` (`SUPPORTED`, `REFUTED`, `UNVERIFIED`) | `test_verification.py`, `backend/evals/` |
| **5** | Zero PII echoing or logging | `PIIGuard.ensure_no_pii`, `find_pii` | `test_security.py`, `test_privacy_canaries.py` |
| **6** | No fake government integration claims | Clear simulation disclaimers on demo portal / grievances | `test_browser.py`, `test_grievances.py` |
| **7** | Human confirmation for external actions | `requires_approval: True`, canonical SHA-256 state hash | `test_agent.py`, `test_redteam_injection.py` |
| **8** | XML boundary prompt isolation | `wrap_untrusted_content()` with tag sanitization | `test_security.py`, `test_redteam_injection.py` |
| **9** | Outbound Gemini RPM quota guard | `GEMINI_GLOBAL_RPM_CAP: 30` sliding-window token bucket | `test_security_audit.py` |
| **10** | Strict file size and page caps | `MAX_UPLOAD_MB: 20`, `MAX_PDF_PAGES: 200` | `test_documents.py`, `test_security.py` |
| **11** | Decompression bomb protection | `GRIEVANCE_MAX_PIXELS: 25_000_000` | `test_grievances.py` |
| **12** | Path traversal & reserved filename defense | UUID resolution, Windows device name checks (`CON`, `NUL`) | `test_security.py`, `test_security_audit.py` |
| **13** | 100% Parameterized database queries | SQLite parameterized queries via standard library `sqlite3` | `test_security.py`, `test_db.py` |
| **14** | Zero API secret disclosure | Keys excluded from API responses, masked as `<masked-api-key>` | `test_gemini.py`, `test_security.py` |
| **15** | DNS rebinding protection | `TrustedHostMiddleware` enforcing `ALLOWED_HOSTS` | `test_security_audit.py` |
| **16** | Strict security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` | `test_security_audit.py` |
| **17** | Guaranteed memory budget (< 6 GB) | CPU-only FAISS, streamed reading, zero memory leaks | `test_security_audit.py`, `test_system.py` |
| **18** | Complete bilingual parity (EN & TA) | `en.js` & `ta.js` 100% key parity, Unicode script detection | `test_language_parity.py` |
| **19** | Deterministic offline testability | Mock Gemini service, synthetic dataset generators | `test_gemini.py`, `backend/evals/` |
| **20** | Controlled browser sandbox with orphan cleanup | Playwright session TTL, idle timeout, `atexit` PID supervisor | `test_browser.py`, `test_demo_portal.py` |

---

## 4. Test Execution Suites

### 4.1 Unit and Functional Pytest Suite
```powershell
backend\.venv\Scripts\pytest backend/tests/ -v
```

### 4.2 Security and Red-Team Adversarial Suite
```powershell
backend\.venv\Scripts\pytest backend/tests/redteam/ backend/tests/test_privacy_canaries.py backend/tests/test_security_audit.py -v
```

### 4.3 Randomized / Shuffled Test Execution
To guarantee that tests have zero global state leaks or execution order dependencies:
```powershell
backend\.venv\Scripts\pytest backend/tests/ --randomly-seed=1234
backend\.venv\Scripts\pytest backend/tests/ --randomly-seed=5678
backend\.venv\Scripts\pytest backend/tests/ --randomly-seed=9999
```

### 4.4 Automated Quality Evaluation Harness
```powershell
.\scripts\run_evals.ps1
```

### 4.5 Dedicated Authentication & Account Test Suite
Run the 36 dedicated auth tests verifying registration policies, persistent throttling lockouts, remote session revocations, origin and CSRF enforcement, default-deny route protection, and cross-user IDOR isolation:
```powershell
backend\.venv\Scripts\pytest backend/tests/auth/ -v
```
