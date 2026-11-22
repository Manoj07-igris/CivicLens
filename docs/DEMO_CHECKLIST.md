# CivicLens AI — Demonstration Readiness Checklist

Use this checklist 15 minutes before presenting to judges or recording a demonstration video.

---

## 1. System Pre-Flight (T-15 Minutes)
- [ ] Run preflight environment check:
  ```powershell
  .\scripts\check_env.ps1
  ```
  *(Verify 8/8 checks pass with 0 failures).*
- [ ] Check available system RAM (ensure >= 2 GB free headroom).
- [ ] Clean temporary session artifacts:
  ```powershell
  .\scripts\reset_demo.ps1
  ```
- [ ] Pre-warm embedding models, portals, and synthetic policy documents:
  ```powershell
  .\scripts\warm_demo.ps1
  ```

---

## 2. Server Startup & Verification (T-10 Minutes)
- [ ] Start backend and frontend servers:
  ```powershell
  .\scripts\start_all.ps1
  ```
- [ ] Verify Frontend loads at `http://localhost:5173`.
- [ ] Verify Backend API Docs respond at `http://127.0.0.1:8000/docs`.
- [ ] Verify Demo Portal responds at `http://127.0.0.1:8000/demo-portal`.
- [ ] Verify language switcher toggles between English and Tamil smoothly.

---

## 3. Live Presentation Guardrails (During Demo)
- [ ] Never paste real personal identity credentials (Aadhaar, PAN, real passwords).
- [ ] Show the PII redaction banner when highlighting security.
- [ ] Highlight that Playwright browser automation is strictly sandboxed to the local demo portal.
- [ ] Emphasize that all external actions require explicit human approval via the interactive confirmation modal.

---

## 4. Teardown & Post-Presentation (T+5 Minutes)
- [ ] Stop all background servers and reap browser processes:
  ```powershell
  .\scripts\stop_all.ps1
  ```
- [ ] Review system audit log in SQLite or run `.\scripts\run_evals.ps1` to view quality report.
