# CivicLens AI — Pitch Notes & Executive Overview

## 1. Problem Statement

Across India, governments release thousands of policy notifications, amendments, and public welfare guidelines each year. However, citizens face three critical barriers:

1. **Information Asymmetry**: Complex administrative circulars are written in dense legalese, making it difficult for ordinary citizens to know their rights or recognize policy changes.
2. **Misinformation Epidemic**: Viral social media messages distort welfare criteria, creating panic or spreading scams about financial benefits.
3. **Execution Gap**: Even when citizens understand their eligibility, they struggle to navigate fragmented government portals, gather required documents, or escalate civic grievances.

---

## 2. The Solution: CivicLens AI

CivicLens is an agentic AI civic intelligence web application built on three foundational pillars: **"Understand. Verify. Act."**

```
┌────────────────────────────────────────────────────────┐
│                      CIVICLENS AI                      │
├───────────────────┬───────────────────┬────────────────┤
│ 1. UNDERSTAND     │ 2. VERIFY         │ 3. ACT         │
├───────────────────┼───────────────────┼────────────────┤
│ • Policy RAG      │ • Fact Checking   │ • Guide Check  │
│ • Clause Diffing  │ • Source Library  │ • Grievance    │
│ • Page Citations  │ • Viral Debunk    │ • Demo Portal  │
└───────────────────┴───────────────────┴────────────────┘
```

---

## 3. Key Technological Innovations

### 3.1 Page-Level Grounded Citations
Unlike generic generative chatbots that hallucinate plausible answers, CivicLens uses a FAISS vector index with PyMuPDF text segmenting to return **authoritative, page-level citation anchors**. Every factual statement maps to a specific page of an uploaded official PDF.

### 3.2 Deterministic + Semantic Policy Diffing
Module 2 pairs strict regular-expression fact extraction (currencies, dates, scheme codes) with Gemini structured reasoning to identify what changed between two versions of a policy without guessing.

### 3.3 Genuine Bilingual Parity (English & Tamil)
Tamil is a first-class language across CivicLens. With 27,760+ Tamil Unicode characters, 100% key parity, script-ratio detection, and specialized Tamil system prompts, citizens can interact in their native tongue without broken English transliterations.

### 3.4 Ethical Agent Architecture & Human-in-the-Loop Gating
External or irreversible actions (e.g. filling out portal forms or drafting official complaints) are strictly gated. The agent cannot autonomously submit forms without generating a cryptographic SHA-256 confirmation hash and obtaining explicit human approval through an interactive modal.

### 3.5 Resource-Conscious Local Design
Designed to run on standard educational or low-cost computers: Intel Core i3 CPU, 8 GB RAM, no GPU, and free-tier Gemini API with an automated sliding-window quota cap.

---

## 4. Target Beneficiaries & Impact

- **General Citizens & Women Beneficiaries**: Access welfare schemes (e.g. Magalir Urimai Thittam) with zero middleman exploitation.
- **Civic Tech Journalists & Fact Checkers**: Rapidly cross-verify viral claims against official government gazette repositories.
- **Local Resident Welfare Associations (RWAs)**: Track municipal circulars, file categorized grievances, and monitor civic escalation channels.
