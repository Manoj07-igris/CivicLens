# CivicLens AI (v1.1.0-auth)

> **Understand. Verify. Act.**

CivicLens is an Agentic AI civic intelligence web application prototype developed for a hackathon to empower citizens by making complex government information accessible, verifiable, and actionable in **English and Tamil (தமிழ்)**. 

> [!NOTE]
> **Prototype Status**: CivicLens is an offline-first research and demonstration prototype. All browser automation is strictly confined to an isolated local loopback mock practice portal, and the application has no direct or live integrations with production government databases or external portals. Evaluation figures reflect results on a small synthetic offline policy benchmark.

Powered by a Central AI Agent using Google Gemini (`gemini-2.5-flash`), CivicLens integrates five core civic modules and a secure authentication & account architecture:
1. **Authentication & Account System (v1.1.0)**: Argon2id password hashing, secure opaque SQLite sessions via HttpOnly `SameSite=Lax` cookies, memory-stored CSRF tokens, account lockout throttling, citizen identity management, and per-user data isolation (IDOR immunity).
2. **Policy Intelligence (Module 1)**: Multi-page gazette PDF ingestion with FAISS vector search, page-level citation anchors, and grounded Q&A.
3. **Policy Change Detection (Module 2)**: Structural pairwise diffing between policy revisions, deterministic fact delta extraction, and citizen impact scoring.
4. **Fact Verification (Module 3)**: Cross-verification of civic claims against official source libraries with deterministic atomic verdicts (`SUPPORTED`, `CONTRADICTED`, `UNVERIFIED`, `OUTDATED`, plus `MIXED` for multi-claim statements).
5. **Public Service Assistant (Module 4)**: Verified government portal matching and dynamic procedural checklists for government schemes and certificates.
6. **Civic Grievance Assistant (Module 5)**: Automated municipal complaint drafting, departmental routing, and strict zero-echo PII redaction.
7. **Central AI Agent**: 7-stage orchestrator enforcing an Evidence Ledger (`[E]`, `[C]`, `[S]` citations), step caps, and mandatory human confirmation gates for sensitive actions.
8. **Safe Browser Automation (Local Demo Only)**: Controlled Playwright demo workflow against an isolated local mock portal with SHA-256 confirmation hash binding.

---

## Technology Stack

- **Frontend**: React 19, Vite, Tailwind CSS v4, Lucide React icons, 100% bilingual English & Tamil localization with offline Noto Sans Tamil & Inter typography.
- **Backend**: Python 3.10+, FastAPI, Pydantic v2, Uvicorn, Argon2id (`argon2-cffi`).
- **AI Agent & LLM**: Google Gemini (`gemini-2.5-flash`) via the official Google GenAI SDK with structured outputs, safety guardrails, prompt injection boundary isolation, and sliding-window quota protection (`GEMINI_GLOBAL_RPM_CAP: 30`).
- **Document Processing**: PyMuPDF (`fitz`), Pillow image decompression-bomb defense, and optional Tesseract OCR.
- **RAG & Search**: Multilingual E5 sentence embeddings (`intfloat/multilingual-e5-small`) + CPU-based FAISS vector indexes.
- **Database & Persistence**: Standard library `sqlite3` in WAL mode (`PRAGMA journal_mode=WAL`), foreign key enforcement, 24 relational tables, and online hot backups.
- **Browser Automation**: Playwright headless Chromium automation confined exclusively to a local loopback practice demo portal with supervisor orphan cleanup.
- **Testing & Quality**: 264 automated tests across 23 test suites (including 36 dedicated auth tests), security audits, red-team prompt injection tests, privacy canaries, and 100% linguistic key parity.

---

## Easy Start for Beginners (Double-Click)

No terminal or PowerShell experience needed! You can start and stop CivicLens entirely using three double-click batch files located in the project root folder (or inside `scripts/`):

1. **`START_CIVICLENS.bat`** (Double-click to run):
   - Automatically verifies Python 3.10+ and Node.js (displays direct download links if either is missing).
   - Automatically provisions the Python virtual environment (`backend\.venv`) and installs frontend packages (`frontend\node_modules`) on first run.
   - Launches the FastAPI backend server in a dedicated window titled **"CivicLens Backend (keep this open)"**.
   - Launches the Vite frontend development server in a dedicated window titled **"CivicLens Frontend (keep this open)"**.
   - Verifies the backend health endpoint (`http://127.0.0.1:8000/api/v1/health`) and automatically opens your browser to `http://localhost:5173`.
   - If startup encounters an issue, the window pauses and shows the last lines of `backend\server.log`.

2. **`CHECK_CIVICLENS.bat`** (Double-click to inspect):
   - Runs a quick, safe system status check in seconds.
   - Verifies backend health, frontend reachability, `.env` configuration (strictly without echoing secrets), SQLite database integrity (`PRAGMA quick_check;`), core Python packages (`argon2-cffi`, `email-validator`, `fastapi`, `uvicorn`), and port statuses (8000 & 5173).
   - Provides clear green `[OK]`, yellow `[WARN]`, or red `[ERROR]` status badges with actionable guidance.

3. **`STOP_CIVICLENS.bat`** (Double-click to shut down):
   - Safely closes the backend and frontend console windows.
   - Frees ports 8000 and 5173.
   - Cleans up any orphan Playwright headless browser automation processes.

### How to Know It Is Working
- Two command prompt windows will remain open: **"CivicLens Backend (keep this open)"** and **"CivicLens Frontend (keep this open)"**. Keep both open while using CivicLens.
- Your web browser opens to `http://localhost:5173`.
- In the top header bar and on the Dashboard system status card, you will see a green dot with **"Backend Server Connected"**.

---

## One-Command Management Scripts (Windows PowerShell)

All operational tasks are automated via pre-configured scripts in `scripts/`:

```powershell
# 1. Preflight environment diagnostics (checks Python, Node, browser, database, API key)
.\scripts\check_env.ps1

# 2. Warm up embedding models, portal registry, and benchmark demo policies
.\scripts\warm_demo.ps1

# 3. Start both Backend (port 8000) and Frontend (port 5173)
.\scripts\start_all.ps1

# Optional single-origin mode (FastAPI serves API + production frontend on port 8000)
.\scripts\start_all.ps1 -SingleOrigin

# 4. Run Quality Evaluation Benchmark (100% offline, zero Gemini quota consumed)
.\scripts\run_evals.ps1

# 5. Reset demonstration state (backs up DB, clears user uploads, restores pristine seed)
.\scripts\reset_demo.ps1

# 6. Gracefully stop all servers and reap any orphan headless browser processes
.\scripts\stop_all.ps1
```

---

## Documentation Directory (`docs/`)

- [AUTH_DESIGN.md](docs/AUTH_DESIGN.md): Comprehensive Authentication & Account System specification, Argon2id benchmarks, and security model.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): Complete architectural specifications, diagrams, and threat models.
- [TEST_PLAN.md](docs/TEST_PLAN.md): Comprehensive traceability matrix for all modules, auth tests, and the 20 Core AI Rules.
- [SECURITY.md](docs/SECURITY.md): Security policy, threat model, and production deployment hardening.
- [API_INVENTORY.md](docs/API_INVENTORY.md): Complete catalog of registered API operations.
- [USER_GUIDE.md](docs/USER_GUIDE.md): Citizen walkthrough for authentication, accounts, and every module in English & Tamil.
- [ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md): Administrator operations, user management CLI, backups, and claiming local data.
- [RELEASE_REPORT.md](docs/RELEASE_REPORT.md): Final integration release report and failure drill outcomes.

---

## Running Automated Tests

Run the complete 255+ test suite:
```powershell
backend\.venv\Scripts\pytest.exe -v
```

Run dedicated authentication and account test suite:
```powershell
backend\.venv\Scripts\pytest.exe backend\tests\auth -v
```

Run security and red-team prompt injection tests:
```powershell
backend\.venv\Scripts\pytest.exe backend\tests\redteam\ backend\tests\test_privacy_canaries.py backend\tests\test_security_audit.py -v
```

---

## Hardware & Resource Budget
Tested and validated on **Windows 11, Intel Core i3, 8 GB RAM, no GPU**:
- Peak memory footprint: **< 500 MB RAM** (well below the 6.0 GB hardware budget ceiling).
- Operates on the Gemini Free Tier with proactive sliding-window rate limiting.
