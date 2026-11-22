# CivicLens AI — Citizen User Guide

Welcome to **CivicLens AI** — your AI-powered civic intelligence web application ("Understand. Verify. Act.").
This guide explains how to use each feature of the platform in both **English** and **Tamil (தமிழ்)**.

---

## 1. Citizen Accounts & Privacy Controls

CivicLens protects your civic research, documents, and grievances with per-user data isolation:

### 1.1 Creating an Account & Signing In
1. Navigate to the application. If not signed in, you will be directed to the **Sign In** page.
2. If you are a new citizen, click **"Create citizen account"** (`/signup`).
3. Enter your full name, email address, and choose a password meeting security criteria (at least 12 characters, including 3 of 4 categories: uppercase, lowercase, numbers, and symbols).
4. Select your preferred default language (**English** or **தமிழ்**) and accept the Terms of Service.
5. If you are on a personal device, check **"Remember this device for 30 days"** during sign-in to keep your session active.

### 1.2 Managing Active Sessions & Security
1. Navigate to **Account Settings** (`/settings`) from the top header or sidebar.
2. Under the **Security & Sessions** tab:
   - Review all devices currently logged into your account.
   - Terminate remote or unfamiliar sessions with the **"Revoke"** button.
   - Change your password anytime (which automatically revokes all other active sessions).

### 1.3 Exporting & Deleting Your Data
1. Open the **Data & Privacy** tab in Settings.
2. Click **"Download Identity Summary"** to export a portable JSON file containing your citizen record metadata.
3. If you ever wish to erase your account, use the **"Danger Zone"** section to permanently wipe all your documents, OCR chunks, vector embeddings, and chat history from the local machine.

---

## 2. Changing the Interface Language
- Locate the language toggle in the top-right corner of the navigation bar.
- Click **"தமிழ்"** to switch the entire application interface, buttons, and assistant instructions to Tamil.
- Click **"English"** to return to English.
- The assistant also features automatic language detection: if you ask a question in Tamil, the assistant will reply in natural, clear Tamil.

---

## 2. Policy Document Intelligence (Module 1)
Use this module to read, understand, and question government policies, gazette notifications, or scheme circulars.

1. Navigate to the **Documents** page from the top navigation bar.
2. Click **Upload Policy Document** (supports PDF files up to 20 MB / 200 pages).
3. Once processed, select the document to view its page-by-page text.
4. Use the search/question box to ask specific questions (e.g. *"What is the family income limit for this scheme?"*).
5. Review the answer along with verified **page-level citation badges** (e.g. `[Page 2]`). Click any citation badge to jump directly to that page in the document.

---

## 3. Policy Change Detection (Module 2)
Use this module to discover what changed between two versions of a policy or government order (G.O.).

1. Navigate to the **Compare Policies** page.
2. Select the **Original (Old) Document** from the dropdown.
3. Select the **Revised (New) Document** from the dropdown.
4. Click **Run Comparison**.
5. The comparison view highlights:
   - **Key Factual Shifts**: Automatically extracted changes in dates, amounts, percentages, or eligibility rules.
   - **Clause Differences**: Color-coded insertions (green), modifications (blue), and removals (red).
   - **Citizen Impact Badges**: Rated as High, Medium, or Low impact with plain-language explanations.

---

## 4. Civic Fact Verification (Module 3)
Use this module to verify viral social media claims or rumours against verified official government sources.

1. Navigate to the **Fact Verification** page.
2. Type or paste the statement you want to check (e.g. *"Is the women's rights assistance reduced to Rs 500?"*).
3. Click **Verify Claim**.
4. The system searches the Official Source Library and returns an honest, tripartite verdict:
   - **SUPPORTED** (Green): Confirmed by official source documents.
   - **REFUTED** (Red): Directly contradicted by official source documents.
   - **UNVERIFIED** (Amber): No official source exists to substantiate the claim.
5. Each verdict includes the exact quote, document title, and issuing authority.

---

## 5. Public Service Guidance & Checklists (Module 4)
Use this module to learn how to apply for government services and certificates.

1. Navigate to the **Public Services** page.
2. Enter the service you need (e.g. *"How to apply for an Income Certificate in Tamil Nadu"*).
3. The platform matches the official verified government portal URL (e.g. `https://esevai.tn.gov.in`).
4. CivicLens generates a step-by-step procedure and an actionable checklist of required documents (Ration Card, Aadhaar, Land Records, etc.) with checkboxes to help you track your progress.

---

## 6. Civic Grievance Assistant (Module 5)
Use this module to organize, classify, and draft formal complaints for civic issues (potholes, water leaks, streetlights, garbage).

1. Navigate to the **Grievances** page.
2. Describe your issue and location.
3. **Privacy Protection**: Notice that any personal identification numbers (Aadhaar, PAN, phone numbers) are automatically redacted in-memory to protect your privacy.
4. The assistant determines the appropriate municipal department, estimates severity, and drafts an official, structured complaint letter ready to be submitted to authorities or the CM Helpline (1100).

---

## 7. Central AI Assistant & Approval Gates
The central assistant unifies all 5 modules in a conversational interface.

1. Navigate to the **AI Assistant** page.
2. Chat freely in English or Tamil.
3. When the assistant needs to perform an external or sensitive action (e.g. opening a portal or filling out a demo form):
   - An **Approval Modal** will appear detailing the exact action and arguments.
   - Click **Approve** to authorize the action, or **Deny** to cancel.
   - The assistant will never perform an irreversible action without your explicit consent.
