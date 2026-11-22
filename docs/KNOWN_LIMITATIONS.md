# CivicLens AI — Known Limitations & Boundaries

To ensure honest, ethical, and safe civic intelligence, CivicLens maintains strict operational boundaries. This document outlines the documented limitations of the `v1.0.0-hackathon` release.

---

## 1. Upstream AI & API Quotas
- **Gemini Free Tier Allocation**: CivicLens uses the Google Gemini 1.5/2.0 API. Free-tier accounts are subject to rate limits (typically 15 requests per minute and 1 million tokens per minute).
- **Proactive Throttling**: The backend implements a central sliding-window quota cap (`GEMINI_GLOBAL_RPM_CAP`, defaulting to 30 requests per minute across all endpoints) to prevent unexpected 429 quota exhaustion.
- **Offline / Mock Mode**: When no API key is provided (`GEMINI_API_KEY=""`), CivicLens falls back to deterministic offline extraction and indexing for evaluation and offline demonstrations.

---

## 2. Browser Automation & Portal Interaction
- **Isolated Demo Portal**: Playwright browser automation is strictly restricted to the local controlled demonstration portal (`http://127.0.0.1:8000/demo-portal` or `demo_portal/`).
- **Zero Live Government Submissions**: The system will **never** submit complaints, applications, or personal data directly to real live state or national government portals (e.g., CPGRAMS, e-Sevai, CM Helpline) without explicit manual user handling.
- **Human-in-the-Loop Approval Required**: All browser form actions require explicit user confirmation via an interactive modal with SHA-256 state hashing.
- **Browser Installation**: Browser features require Playwright Chromium binaries installed on the host (`playwright install chromium`). If unavailable, browser features degrade gracefully with informative messages.

---

## 3. Bilingual Language Scope
- **Languages Supported**: CivicLens is fully internationalized in **English (`en`)** and **Tamil (`ta`)** across all user interfaces, prompts, and evaluation datasets.
- **Other Indic Languages**: Support for Hindi, Telugu, Kannada, Malayalam, and Bengali is planned for post-hackathon roadmap milestones (`docs/FUTURE_WORK.md`).
- **Translation Quality**: Tamil translations are verified against official Tamil Nadu government gazette terminology. Highly technical legal terminology may occasionally feature English loanwords in parentheses.

---

## 4. Hardware & Resource Budget
- **Minimum Target**: Validated on Windows 11 with an Intel Core i3 CPU, 8 GB RAM, and no GPU.
- **Memory Ceiling**: Total combined memory consumption is constrained to stay below 6.0 GB RAM to prevent swapping or OS lag.
- **Local Embedding Indexing**: FAISS vector indexes and PyMuPDF text extractions execute on CPU. Large documents (>100 pages) may take several seconds to process.

---

## 5. Source Library Curation
- **Curated Official Sources**: The source library indexes documents uploaded or seeded via verified official sources (`manifest.json`).
- **No Autonomous Web Crawling**: CivicLens does not perform unvetted autonomous web scraping of third-party civic portals. All sources must be explicitly registered and fingerprinted with SHA-256 hashes to guarantee data provenance.

---

## 6. Privacy & PII Handling
- **Non-Reversible Masking**: Aadhaar numbers, PAN, credit cards, emails, and phone numbers are redacted in-memory before entering LLM prompts or audit logs.
- **Redaction Disclaimer**: Users are reminded never to share unredacted government identity credentials or passwords in public demonstration sessions.

---

## 7. Local Server Lifecycle & Connectivity
- **Dual-Server Architecture**: CivicLens runs a dual-server topology with the FastAPI backend on port 8000 and the Vite frontend on port 5173 (or single-origin mode where FastAPI serves the pre-built SPA on port 8000).
- **Graceful Health & Degraded Reporting**: The UI polls `/api/v1/health` and `/api/v1/info` and clearly distinguishes between `offline` (backend process not running / connection refused) and `degraded` (backend running, but database undergoing maintenance or migration). Public metrics endpoints (`/api/v1/system/status` and `/api/v1/system/stats`) are accessible without authentication so that dashboard indicators reflect live system health accurately.
- **Wait-for-Health Automation**: `scripts/start_all.ps1` includes an automated polling loop that verifies `/api/v1/health` readiness before launching the frontend, preventing startup race conditions.
