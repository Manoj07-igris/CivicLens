# CivicLens — Project Brief

> **Motto**: "Understand. Verify. Act."

## 1. Executive Summary
CivicLens is an Agentic AI civic intelligence web application designed to bridge the gap between complex government documents and everyday citizens. Public notifications, legal gazettes, welfare scheme guidelines, and municipal procedures are frequently dense, hard to navigate, and prone to misinformation. CivicLens transforms these government communications into plain, verifiable, and actionable intelligence in English and Tamil.

---

## 2. Five Core Modules

1. **Policy Intelligence**
   - Enables citizens to upload official government PDFs (gazette notifications, scheme guidelines, circulars).
   - Allows natural language question-answering with strict, verbatim citations and paragraph-level evidence references.

2. **Policy Change Detection**
   - Automatically compares old vs. new versions of government notifications, policies, and acts.
   - Highlights additions, removals, eligibility modifications, deadline shifts, and fee adjustments in clear plain-language summaries.

3. **Fact Verification**
   - Evaluates viral civic claims and rumors against curated official government sources and legal records.
   - Categorizes claims into four precise verdicts:
     - **Supported**: Directly validated by an official record.
     - **Contradicted**: Directly refuted by an official record.
     - **Unverified**: Inconclusive or no official record exists.
     - **Outdated**: Previously true but superseded by newer notifications.

4. **Public Service Assistant**
   - Breaks down complex bureaucratic processes (e.g., obtaining certificates, applying for welfare benefits) into step-by-step procedures.
   - Produces customized document checklists and guides citizens through controlled, sandboxed browser simulations of portal workflows.

5. **Civic Grievance Assistant**
   - Assists citizens in identifying the correct department, jurisdiction, and format for municipal and civic complaints.
   - Drafts structured grievance letters and simulates tracking complaint workflows within a controlled demo environment.

---

## 3. The Agent Concept
CivicLens is architected around **ONE central AI Agent** powered by Google Gemini (via the Gemini API on Google AI Studio). The agent acts as an orchestrator rather than a passive chatbot:
- It interprets citizen inquiries in natural language.
- It reasons about the appropriate actions and autonomously invokes backend domain tools.
- It receives tool execution results, validates evidence, and synthesizes accurate, user-friendly responses.
- All AI calls and agent decisions originate exclusively from the secure FastAPI backend; frontend code never communicates directly with the Gemini API.

---

## 4. Bilingual Support
CivicLens natively supports:
- **English**: For standard civic and administrative documentation.
- **Tamil (தமிழ்)**: For local civic access, grassroots welfare inquiries, and Tamil state government notifications.
- All workflows support bilingual queries, cross-lingual retrieval (finding English sources from Tamil queries and vice versa), and Tamil responses with matching terminology.

---

## 5. Safety Principles & Guardrails

1. **Evidence-Based Answers Only**: The agent never speculates. Every factual assertion must be grounded in uploaded documents or verified official sources.
2. **Zero Hallucinated Citations**: If a citation, circular number, or URL does not exist in the verified context, the system states that the information cannot be found.
3. **Uploaded PDFs as Untrusted Input**: User-uploaded documents are treated as untrusted data and sanitized to prevent prompt injections and system manipulation.
4. **Human-in-the-Loop for Irreversible Actions**: The system requires explicit user confirmation before generating final formal drafts or proceeding with sensitive steps.
5. **Controlled Demo Automation**: Browser automation and complaint tracking are strictly restricted to isolated demo environments. CivicLens never posts live data to real government servers.
6. **No Representation of Official Authority**: CivicLens explicitly states that it is an independent civic intelligence assistant and does not claim official government affiliation or legal authority.
