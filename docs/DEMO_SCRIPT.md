# CivicLens AI — Hackathon Demonstration Script (5-Minute Live Pitch)

## Presentation Overview
- **Duration**: Exactly 5 Minutes (300 seconds)
- **Tagline**: **"Understand. Verify. Act."**
- **Presenter Role**: Lead Civic Intelligence Engineer
- **Audience**: Hackathon Evaluation Jury & Civic Tech Observers
- **Pre-Flight Command**: `.\scripts\warm_demo.ps1` executed 5 minutes prior to ensure zero cold-start delay.

---

## Minute-by-Minute Pitch Walkthrough

### 0:00 – 0:45 | The Problem & The Mission (Understand)
> *"Judges, every day millions of Indian citizens struggle to navigate complex government gazettes, circulars, and welfare schemes. Between 50-page legal notifications, changing eligibility rules, and rampant WhatsApp misinformation, people miss out on life-changing entitlements or fall victim to scams.*
>
> *Today, we present **CivicLens AI** — an Agentic civic intelligence platform designed to empower citizens in **English and Tamil**. Our philosophy is simple: **Understand. Verify. Act.**"*

- **Visual Action**: Display CivicLens Dashboard (`http://localhost:5173`).
- **Highlight**: Bilingual language toggle switch in the navbar (instantly switch to Tamil: *"புரிந்து கொள்ளுங்கள். சரிபாருங்கள். செயல்படுங்கள்."*).

---

### 0:45 – 1:45 | Module 1 & 2: Policy Intelligence & Change Detection
> *"Let's look at Module 1: Policy Intelligence. We ingest official gazette PDFs. Instead of generic chatbot summaries, CivicLens provides **page-level grounded citations**."*

- **Visual Action**: Click **Documents** tab. Open `TN_Magalir_Urimai_2024.pdf`.
- **Query Prompt**: *"What is the annual income ceiling under the revised guidelines?"*
- **Highlight**: Point to citation badge `[E1]` linking directly to Page 2, proving the fact: *Rs. 3,00,000*.

> *"Now, Module 2: Policy Change Detection. Policies change every year. How does a citizen know what shifted between the 2023 and 2024 gazette notifications?"*

- **Visual Action**: Click **Compare Policies**. Select 2023 and 2024 versions.
- **Highlight**: Structural diff showing:
  - Financial assistance increased from Rs. 1,000 to Rs. 1,200.
  - Income ceiling expanded from Rs. 2,50,000 to Rs. 3,00,000.
  - New statutory appeal window added before the Revenue Divisional Officer.

---

### 1:45 – 2:45 | Module 3: Fact Verification Against Official Sources
> *"Next: Module 3, Fact Verification. Misinformation spreads fast during elections and scheme rollouts. Citizens can submit viral claims to be cross-verified against our verified Official Source Library."*

- **Visual Action**: Navigate to **Verify** tab.
- **Input Claim**: *"The government has reduced the women's rights assistance to Rs 500."*
- **Result Display**:
  - Verdict badge: **`REFUTED`** in red.
  - Evidence text: Citing the official 2024 gazette stating the assistance is Rs. 1,200.
  - Confidence Score: *95%*.

---

### 2:45 – 3:45 | Module 4 & 5: Public Service Guidance & Grievance Drafting
> *"Once citizens understand and verify, they must **Act**. Modules 4 and 5 guide action.*
> *In Module 4, citizens ask how to apply. CivicLens automatically matches official verified state portals (`https://esevai.tn.gov.in`) and generates an actionable checklist of required documents.*
>
> *In Module 5, CivicLens assists with civic grievances (potholes, water leaks, power outages)."*

- **Visual Action**: Open **Grievances** tab.
- **Safety & PII Demonstration**: Type: *"Sewage leak near school. Call complainant at 9876543210."*
- **Highlight**: Immediate alert banner: **PII Masked / Redacted**. Phone numbers and personal IDs are stripped in-memory before entering AI prompts, preserving citizen privacy.

---

### 3:45 – 4:30 | Central Agent & Controlled Browser Automation
> *"Finally, everything is unified by our **Central Agent Orchestrator**. Notice rule #7 of ethical AI: **Human confirmation for irreversible actions**.*
> *The AI agent never autonomously submits forms to external portals without citizen approval."*

- **Visual Action**: Switch to **AI Assistant** tab. Ask the agent: *"Help me start my application on the demo portal."*
- **Interactive Gate**: An interactive approval modal pops up showing the canonical SHA-256 hash and exact form parameters.
- **Action**: Click **"Approve & Continue"**. Watch the Playwright headless browser snapshot the demo portal, fill required fields safely, and return a simulated demo reference number.

---

### 4:30 – 5:00 | Architecture, Constraints & Conclusion
> *"To conclude: CivicLens runs locally on standard consumer hardware — an Intel i3 with 8 GB RAM and no GPU, using the Gemini free tier with proactive quota throttling.*
> *It features 100% parameter-safe SQLite storage, zero plain-text secrets, 219+ passing tests, and genuine 100% bilingual parity in English and Tamil.*
>
> *CivicLens turns bureaucratic complexity into citizen agency: **Understand. Verify. Act.** Thank you!"*
