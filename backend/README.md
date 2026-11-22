# CivicLens Backend Service

FastAPI backend providing the central API, security, configuration, and AI agent orchestration for CivicLens.

---

## Prerequisites
- Python 3.10 to 3.12 (tested on Python 3.10)
- Virtual environment at `backend/.venv` (created in Phase 1)

---

## Windows PowerShell Setup & Execution

### 1. Activate the Virtual Environment
From the repository root (`CivicLens AI`):
```powershell
.\backend\.venv\Scripts\Activate.ps1
```
*(If PowerShell blocks execution, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 2. Configure Environment Variables
Inside the `backend/` directory, copy the template file to `.env`:
```powershell
cd backend
Copy-Item .env.example .env
```
*(Note: The server will boot normally even if `GEMINI_API_KEY` is left blank during development).*

### 3. Install Dependencies (if not already installed)
```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

### 4. Start the FastAPI Development Server
From inside the `backend/` folder:
```powershell
uvicorn app.main:app --reload --port 8000
```
Or from the project root:
```powershell
.\backend\.venv\Scripts\uvicorn.exe backend.app.main:app --reload --port 8000
```

The API will be available at:
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Endpoint**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **System Info Endpoint**: [http://localhost:8000/api/v1/info](http://localhost:8000/api/v1/info)
- **Gemini Status Endpoint**: [http://localhost:8000/api/v1/gemini/status](http://localhost:8000/api/v1/gemini/status)
- **Gemini Diagnostic Test**: [http://localhost:8000/api/v1/gemini/test](http://localhost:8000/api/v1/gemini/test) (POST)
- **Central AI Agent Chat**: [http://localhost:8000/api/v1/agent/chat](http://localhost:8000/api/v1/agent/chat) (POST)
- **Agent Tools Registry**: [http://localhost:8000/api/v1/agent/tools](http://localhost:8000/api/v1/agent/tools) (GET)
- **Citizen Action Approvals**: [http://localhost:8000/api/v1/agent/approvals/{id}](http://localhost:8000/api/v1/agent/approvals/{id}) (POST)
- **Conversational Chatbot (Legacy)**: [http://localhost:8000/api/v1/chat](http://localhost:8000/api/v1/chat) (POST)
- **Document Capabilities**: [http://localhost:8000/api/v1/documents/capabilities](http://localhost:8000/api/v1/documents/capabilities) (GET)
- **Document Upload**: [http://localhost:8000/api/v1/documents/upload](http://localhost:8000/api/v1/documents/upload) (POST multipart/form-data)
- **Document List**: [http://localhost:8000/api/v1/documents](http://localhost:8000/api/v1/documents) (GET)
- **Policy Comparison Start**: [http://localhost:8000/api/v1/compare](http://localhost:8000/api/v1/compare) (POST)
- **Policy Comparison List**: [http://localhost:8000/api/v1/compare](http://localhost:8000/api/v1/compare) (GET)
- **Policy Comparison Report**: [http://localhost:8000/api/v1/compare/{id}](http://localhost:8000/api/v1/compare/{id}) (GET)
- **Official Source Library List**: [http://localhost:8000/api/v1/sources](http://localhost:8000/api/v1/sources) (GET)
- **Official Source Upload**: [http://localhost:8000/api/v1/sources](http://localhost:8000/api/v1/sources) (POST multipart/form-data)
- **Fact Verification Start**: [http://localhost:8000/api/v1/verify](http://localhost:8000/api/v1/verify) (POST)
- **Fact Verification Status / Report**: [http://localhost:8000/api/v1/verify/{id}](http://localhost:8000/api/v1/verify/{id}) (GET)
- **Fact Verification History**: [http://localhost:8000/api/v1/verify](http://localhost:8000/api/v1/verify) (GET)
- **Public Service Guidance & Checklist**: [http://localhost:8000/api/v1/services/guide](http://localhost:8000/api/v1/services/guide) (POST)
- **Public Service Guide Report**: [http://localhost:8000/api/v1/services/guide/{id}](http://localhost:8000/api/v1/services/guide/{id}) (GET)
- **Form Fields Extraction**: [http://localhost:8000/api/v1/services/form-fields/extract](http://localhost:8000/api/v1/services/form-fields/extract) (POST)
- **Form Fields Explanation**: [http://localhost:8000/api/v1/services/form-fields/explain](http://localhost:8000/api/v1/services/form-fields/explain) (POST)
- **Curated Official Portals List**: [http://localhost:8000/api/v1/portals](http://localhost:8000/api/v1/portals) (GET)
- **Curated Official Portals Match**: [http://localhost:8000/api/v1/portals/match](http://localhost:8000/api/v1/portals/match) (POST)
- **Grievance Assistant Capabilities**: [http://localhost:8000/api/v1/grievances/capabilities](http://localhost:8000/api/v1/grievances/capabilities) (GET)
- **Grievance Photo Upload**: [http://localhost:8000/api/v1/grievances/image](http://localhost:8000/api/v1/grievances/image) (POST multipart/form-data)
- **Grievance Analysis & Drafting**: [http://localhost:8000/api/v1/grievances/analyze](http://localhost:8000/api/v1/grievances/analyze) (POST)
- **Grievance Record & Progress**: [http://localhost:8000/api/v1/grievances/{id}](http://localhost:8000/api/v1/grievances/{id}) (GET)
- **Grievance Draft Patch**: [http://localhost:8000/api/v1/grievances/{id}](http://localhost:8000/api/v1/grievances/{id}) (PATCH)
- **Grievance DEMO Registration**: [http://localhost:8000/api/v1/grievances/{id}/register-demo](http://localhost:8000/api/v1/grievances/{id}/register-demo) (POST)
- **Grievance DEMO Status Advance**: [http://localhost:8000/api/v1/grievances/{id}/demo-advance](http://localhost:8000/api/v1/grievances/{id}/demo-advance) (POST)
- **Grievance Records List**: [http://localhost:8000/api/v1/grievances](http://localhost:8000/api/v1/grievances) (GET)
- **Browser Automation Capabilities**: [http://localhost:8000/api/v1/browser/capabilities](http://localhost:8000/api/v1/browser/capabilities) (GET)
- **Browser Workflow Manifest**: [http://localhost:8000/api/v1/browser/manifest](http://localhost:8000/api/v1/browser/manifest) (GET)
- **Browser Sample Fictional Data**: [http://localhost:8000/api/v1/browser/sample-data](http://localhost:8000/api/v1/browser/sample-data) (GET)
- **Browser Start Session**: [http://localhost:8000/api/v1/browser/sessions](http://localhost:8000/api/v1/browser/sessions) (POST)
- **Browser Session Fill**: [http://localhost:8000/api/v1/browser/sessions/{id}/fill](http://localhost:8000/api/v1/browser/sessions/{id}/fill) (POST)
- **Browser Session Next/Back**: [http://localhost:8000/api/v1/browser/sessions/{id}/next](http://localhost:8000/api/v1/browser/sessions/{id}/next) (POST)
- **Browser Session Review Preview**: [http://localhost:8000/api/v1/browser/sessions/{id}/preview](http://localhost:8000/api/v1/browser/sessions/{id}/preview) (POST)
- **Browser Session Submit**: [http://localhost:8000/api/v1/browser/sessions/{id}/submit](http://localhost:8000/api/v1/browser/sessions/{id}/submit) (POST)
- **Browser Screenshots**: [http://localhost:8000/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}](http://localhost:8000/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}) (GET)
- **Local Demo Portal**: [http://localhost:8000/demo-portal/](http://localhost:8000/demo-portal/) (Static Loopback Mount)
- **Chat Conversations List & Create**: [http://localhost:8000/api/v1/conversations](http://localhost:8000/api/v1/conversations) (GET, POST)
- **Chat Conversation Messages & Detail**: [http://localhost:8000/api/v1/conversations/{id}](http://localhost:8000/api/v1/conversations/{id}) (GET, PATCH, DELETE)
- **Bulk Conversation Import**: [http://localhost:8000/api/v1/conversations/import](http://localhost:8000/api/v1/conversations/import) (POST)
- **User Preferences**: [http://localhost:8000/api/v1/preferences](http://localhost:8000/api/v1/preferences) (GET, PUT)
- **Activity Feed & Tool Runs Ledger**: [http://localhost:8000/api/v1/activity](http://localhost:8000/api/v1/activity) (GET)
- **System Health & Storage Diagnostics**: [http://localhost:8000/api/v1/system/status](http://localhost:8000/api/v1/system/status) (GET)
- **System Module Statistics**: [http://localhost:8000/api/v1/system/stats](http://localhost:8000/api/v1/system/stats) (GET)
- **Online Database Hot Backup**: [http://localhost:8000/api/v1/system/backup](http://localhost:8000/api/v1/system/backup) (POST)
- **System Maintenance & Pruning**: [http://localhost:8000/api/v1/system/maintenance](http://localhost:8000/api/v1/system/maintenance) (POST)
- **Prototype Data Wipe**: [http://localhost:8000/api/v1/system/data](http://localhost:8000/api/v1/system/data) (DELETE)

---

## Central AI Agent & Function Calling (Phase 9)

The central AI agent coordinates backend tools (`list_documents`, `read_document`, `retrieve_evidence`), validates arguments through Pydantic schemas, grounds answers via bracketed citations (`[E1]`), and pauses for human authorization on sensitive actions.

### 1. Interact with the Central AI Agent:
```powershell
$body = @{
    message = "What are the subsidy guidelines under the Tamil Nadu EV policy?"
    history = @()
    language = "auto"
    document_ids = @("your-document-uuid-here")
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agent/chat" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5
```

### 2. Inspect Registered Tools & Status:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agent/tools" -Method Get | ConvertTo-Json -Depth 4
```

### 3. Approve or Deny a Pending Action:
```powershell
$body = @{
    decision = "approve"  # or "deny"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agent/approvals/appr_123456789abc" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5
```

---

## Document Intelligence Endpoints (Phase 7)

Provides secure endpoints for official PDF upload, PyMuPDF page-level extraction, Tesseract OCR fallback, page-isolated chunking, and AI-grounded summarization.

### Upload a PDF via PowerShell:
```powershell
$form = @{
    file = Get-Item -Path "path\to\government_notification.pdf"
}
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/upload" -Method Post -Form $form
```

### Request an AI Document Summary:
```powershell
$body = @{ language = "en" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/<document_id>/summary" -Method Post -ContentType "application/json" -Body $body
```

---

## RAG & Document Q&A Endpoints (Phase 8)

Enables hybrid vector + lexical search and evidence-grounded Q&A with exact page citations.

### 1. Build / Rebuild FAISS Vector Index:
```powershell
$body = @{ force = $true } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/<document_id>/index" -Method Post -ContentType "application/json" -Body $body
```

### 2. Standalone Hybrid Passage Retrieval (Zero Quota):
```powershell
$body = @{
    query = "Who is eligible for this welfare grant?"
    top_k = 4
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/<document_id>/retrieve" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json
```

### 3. Ask an Evidence-Grounded Question:
```powershell
$body = @{
    question = "What are the required documents for applying?"
    language = "auto"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/<document_id>/ask" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json
```

---

## Policy Change Detection Endpoints (Phase 10)

Module 2 compares an older and newer version of a policy or notification to pinpoint changed numbers, deadlines, eligibility criteria, and clauses with token-level diffs and dual page citations.

### 1. Start a Comparison Job (Background Task):
```powershell
$body = @{
    old_document_id = "old-doc-uuid"
    new_document_id = "new-doc-uuid"
    language = "auto"
    force_reanalyze = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/compare" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json
```

### 2. Poll Status or Retrieve Report:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/compare/<comparison_id>" -Method Get | ConvertTo-Json -Depth 6
```

### 3. List Past Comparisons:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/compare" -Method Get | ConvertTo-Json -Depth 4
```

### 4. Retry Failed AI Analysis:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/compare/<comparison_id>/retry-analysis" -Method Post | ConvertTo-Json
```

---

## Conversational AI Chat Endpoint (Phase 6)

The chat endpoint accepts multi-turn civic messages, detects the query language, and returns non-hallucinated explanations.

### Sample Request (PowerShell):
```powershell
$body = @{
    message = "What documents are required to apply for a community certificate in Tamil Nadu?"
    history = @()
    language = "auto"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json
```

### Sample Request in Tamil:
```powershell
$body = @{
    message = "குடும்ப அட்டை பெறுவதற்கான தகுதிகள் என்ன?"
    history = @()
    language = "ta"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json
```

---

## Google Gemini API Configuration (Phase 5)

CivicLens uses the official `google-genai` Python SDK to interact with Google AI Studio's Gemini models.

### Setting your API Key
1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Open `backend/.env` and paste your key:
   ```env
   GEMINI_API_KEY=AIzaSy...your_actual_key_here
   ```
3. (Optional) Customize the model and parameters in `backend/.env`:
   ```env
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_TIMEOUT_SECONDS=30
   GEMINI_MAX_RETRIES=2
   GEMINI_TEMPERATURE=0.2
   GEMINI_MAX_OUTPUT_TOKENS=2048
   AGENT_MAX_STEPS=4
   AGENT_MAX_TOOL_CALLS_PER_RUN=6
   AGENT_TOOL_TIMEOUT_SECONDS=15
   AGENT_RATE_LIMIT_PER_MINUTE=10
   COMPARE_MAX_PAGES_PER_DOC=100
   COMPARE_MAX_CANDIDATES=60
   COMPARE_BATCH_SIZE=12
   COMPARE_MAX_GEMINI_CALLS=4
   COMPARE_SIMILARITY_MATCH_THRESHOLD=0.55
   COMPARE_RATE_LIMIT_PER_MINUTE=3
   VERIFY_MAX_GEMINI_CALLS=2
   VERIFY_MAX_CLAIMS=5
   VERIFY_CLAIM_MAX_CHARS=1000
   VERIFY_TOP_K_PER_SOURCE=3
   VERIFY_TOP_K_TOTAL=8
   VERIFY_MAX_SOURCES_SEARCHED=30
   VERIFY_RATE_LIMIT_PER_MINUTE=5
   SOURCE_STALE_AFTER_DAYS=365
   ALLOW_SOURCE_MANAGEMENT=True
   SERVICE_MAX_GEMINI_CALLS=1
   SERVICE_QUERY_MAX_CHARS=600
   SERVICE_TOP_K_TOTAL=10
   SERVICE_RATE_LIMIT_PER_MINUTE=5
   SERVICE_MAX_CHECKLIST_ITEMS=30
   FORM_FIELDS_MAX=40
   ALLOW_PORTAL_MANAGEMENT=True
   BROWSER_ENABLED=true
   BROWSER_HEADLESS=true
   BROWSER_SLOW_MO_MS=0
   BROWSER_SESSION_TTL_SECONDS=600
   BROWSER_IDLE_CLOSE_SECONDS=120
   BROWSER_MAX_ACTIONS_PER_SESSION=60
   BROWSER_ACTION_TIMEOUT_MS=8000
   BROWSER_NAVIGATION_TIMEOUT_MS=10000
   BROWSER_VIEWPORT_WIDTH=1024
   BROWSER_VIEWPORT_HEIGHT=720
   BROWSER_SCREENSHOT_MAX_WIDTH=900
   BROWSER_SCREENSHOT_QUALITY=70
   BROWSER_MAX_SCREENSHOTS_PER_SESSION=40
   BROWSER_MAX_CONCURRENT_SESSIONS=1
   BROWSER_RECORDS_MAX=50
   BROWSER_RATE_LIMIT_PER_MINUTE=20
   PUBLIC_BASE_URL="http://127.0.0.1:8000"
   ```

### Playwright Browser Automation Setup
Phase 14 introduces safe Playwright browser automation for simulating citizen workflows on the local demo portal (`/demo-portal/`).
1. Install playwright python package:
   ```powershell
   pip install playwright
   ```
2. Install the Chromium browser binary:
   ```powershell
   python -m playwright install chromium
   ```

> **Security Note**: Never commit `backend/.env` or share your key. It is pre-configured in `.gitignore`.

---

## Running Automated Tests

### 1. Run Standard Mocked Tests (Zero Quota)
From the repository root:
```powershell
.\backend\.venv\Scripts\pytest.exe -p no:cacheprovider backend\tests -v
```

### 2. Run Optional Real Live Gemini Call Test
To verify live end-to-end communication with Google AI Studio using your real configured key:
```powershell
$env:RUN_REAL_GEMINI_TEST="1"
.\backend\.venv\Scripts\pytest.exe -p no:cacheprovider backend\tests\test_gemini.py -k test_real_gemini_api_call -v
```
