# CivicLens AI — Quality Evaluation & Benchmarking Report

**Evaluation Mode**: `OFFLINE`  
**Timestamp**: `2026-11-21T19:22:43.290747+00:00`  
**Overall Accuracy**: **100.0%** (6/6 benchmark tests passed)  
**Average Latency**: **9.87 ms**  
**Gemini Quota Calls Used**: `0 / 60`  

---

## Benchmark Results Matrix

| Module | Evaluation Metric | Score | Status | Latency | Details |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Module 1: Policy Intelligence** | Page-Level Grounded Citation Retrieval | `100%` | ✅ PASS | 18.51 ms | Found on page 2, expected page 2 |
| **Module 2: Policy Change Detection** | Structural Clause & Fact Diffing Recall | `100%` | ✅ PASS | 11.56 ms | Detected: Financial Assistance Shift (Rs. 1,000 -> Rs. 1,200), Income Ceiling Expansion (Rs. 2,50,000 -> Rs. 3,00,000), New Statutory Appeal Clause Added |
| **Module 3: Fact Verification** | Tripartite Truth Verdict Accuracy | `100%` | ✅ PASS | 0.02 ms | 3/3 claims matched ground truth (SUPPORTED, REFUTED, UNVERIFIED) |
| **Module 4: Public Service Guidance** | Portal Registry Matching & Checklist Recall | `75%` | ✅ PASS | 16.51 ms | Portal matched: True, Checklist items: 4/4 matched |
| **Module 5: Civic Grievance Assistant** | Zero-Echo PII Redaction & Category Routing | `100%` | ✅ PASS | 0.09 ms | PII blocked with 100% confidence, category properly mapped |
| **Central AI Agent** | Tool Registry Integrity & Human Approval Gating | `100%` | ✅ PASS | 12.5 ms | 12/12 tools available; 100% sensitive tools require explicit human approval |

---

## Evaluation Methodology & Guardrails

1. **Module 1 (Policy Intelligence)**: Validates text retrieval precision against synthetic multi-page gazette documents, verifying that citations link to the correct 1-based page numbers.
2. **Module 2 (Policy Change Detection)**: Compares 2023 vs 2024 synthetic policy gazettes, evaluating the detection of numeric threshold shifts (income ceiling, assistance entitlement) and newly added statutory appeal clauses.
3. **Module 3 (Fact Verification)**: Evaluates tripartite classification accuracy across ground-truth positive (`SUPPORTED`), contradictory (`REFUTED`), and hallucinated (`UNVERIFIED`) citizen claims.
4. **Module 4 (Public Service Guidance)**: Evaluates automated matching of citizen queries to verified government portal URLs and procedural checklist recall.
5. **Module 5 (Civic Grievance Assistant)**: Validates instant PII interception (Aadhaar, phone, email) and proper complaint classification into relevant civic departments.
6. **Central AI Agent**: Verifies that 100% of sensitive and irreversible tools (portal opening, form autofill, demo submission) enforce human approval gates and canonical SHA-256 state hashing.

---

## Reproducibility

To reproduce this evaluation locally:
```powershell
# Offline deterministic evaluation (Zero Gemini quota consumed)
.\scripts\run_evals.ps1

# Live AI evaluation with explicit quota authorization and call cap
.\scripts\run_evals.ps1 -Live -YesUseQuota -MaxCalls 60
```
