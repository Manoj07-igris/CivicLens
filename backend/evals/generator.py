"""Synthetic Policy Document and Ground-Truth Evaluation Dataset Generator (Phase 16).

Generates synthetic, bilingual policy documents in PDF format using PyMuPDF (fitz)
with deterministic factual assertions for benchmarking:
- RAG retrieval and citation accuracy (Module 1)
- Policy change detection precision and recall (Module 2)
- Fact verification verdict accuracy (Module 3)
- Public service checklist recall (Module 4)
- Grievance classification and redaction (Module 5)
"""

from pathlib import Path
from typing import Dict, List, Tuple
import fitz  # PyMuPDF


def create_synthetic_policy_pdf(output_path: Path, title: str, clauses: List[Dict[str, str]]) -> Path:
    """Create a multi-page PDF document containing structured civic policy clauses."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    for i, clause in enumerate(clauses):
        page = doc.new_page(width=595, height=842)  # A4 size
        # Page header
        header_text = f"GOVERNMENT OF TAMIL NADU - OFFICIAL POLICY GAZETTE\n{title} (Page {i+1})\n" + ("=" * 60)
        page.insert_text((50, 50), header_text, fontsize=10)

        # Clause body
        body_text = f"\nClause {i+1}: {clause['title']}\n\n{clause['content']}\n"
        if "notes" in clause:
            body_text += f"\nStatutory Notes:\n{clause['notes']}\n"

        page.insert_textbox(
            fitz.Rect(50, 100, 545, 780),
            body_text,
            fontsize=11,
            lineheight=1.4,
        )

    doc.save(str(output_path))
    doc.close()
    return output_path


def generate_benchmark_assets(target_dir: Path) -> Dict[str, Path]:
    """Generate all synthetic policy PDFs and return their paths."""
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. 2023 Policy Baseline (Old)
    policy_2023_clauses = [
        {
            "title": "Title, Objective and Scope of Financial Assistance",
            "content": "The Kalaignar Magalir Urimai Thittam provides financial assistance of Rs. 1,000 per month to eligible female heads of families in Tamil Nadu to support livelihoods and social security.",
            "notes": "Effective date: 15 September 2023. Disbursed directly via DBT into bank accounts."
        },
        {
            "title": "Family Income Eligibility Ceiling",
            "content": "The annual family income of the applicant household from all sources must not exceed Rs. 2,50,000 (Rupees Two Lakh Fifty Thousand only).",
            "notes": "Verified against Tamil Nadu e-Governance database and Income Certificate."
        },
        {
            "title": "Land Holding and Property Ownership Restrictions",
            "content": "Families owning more than 5 acres of dry land or more than 2.5 acres of wetland are ineligible for assistance under this scheme.",
            "notes": "Revenue department land records (Patta/Chitta) shall be verified."
        },
        {
            "title": "Application Channels and Verification Process",
            "content": "Applications must be submitted in person at designated e-Sevai centers across Tamil Nadu. Fingerprint biometric authentication is mandatory at submission.",
            "notes": "No online self-service portal is currently provided for initial enrollment."
        }
    ]

    # 2. 2024 Policy Revision (New)
    policy_2024_clauses = [
        {
            "title": "Title, Objective and Scope of Financial Assistance",
            "content": "The Kalaignar Magalir Urimai Thittam provides revised financial assistance of Rs. 1,200 per month to eligible female heads of families in Tamil Nadu to adjust for cost of living.",
            "notes": "Effective date: 15 September 2024. Monthly entitlement increased from Rs. 1,000 to Rs. 1,200."
        },
        {
            "title": "Family Income Eligibility Ceiling",
            "content": "The annual family income ceiling of the applicant household has been raised to Rs. 3,00,000 (Rupees Three Lakh only) to expand coverage.",
            "notes": "Threshold expanded from previous limit of Rs. 2,50,000."
        },
        {
            "title": "Land Holding and Property Ownership Restrictions",
            "content": "Families owning more than 5 acres of dry land or more than 2.5 acres of wetland are ineligible for assistance under this scheme.",
            "notes": "Landholding thresholds remain unchanged from the 2023 gazette notification."
        },
        {
            "title": "Application Channels and Verification Process",
            "content": "Applications may be submitted at e-Sevai centers or online via the official web portal at https://esevai.tn.gov.in. Biometric or OTP-based Aadhaar e-KYC is accepted.",
            "notes": "Online web portal submission introduced as an authorized application channel."
        },
        {
            "title": "Grievance Redressal and Appeal Mechanism",
            "content": "Applicants whose forms are rejected may file an appeal before the Revenue Divisional Officer (RDO) within 30 days of notification or call the toll-free CM Helpline 1100.",
            "notes": "New formal appeal window and statutory escalation procedure established."
        }
    ]

    pdf_2023 = target_dir / "TN_Magalir_Urimai_2023.pdf"
    pdf_2024 = target_dir / "TN_Magalir_Urimai_2024.pdf"

    create_synthetic_policy_pdf(pdf_2023, "Kalaignar Magalir Urimai Thittam - 2023 Guidelines", policy_2023_clauses)
    create_synthetic_policy_pdf(pdf_2024, "Kalaignar Magalir Urimai Thittam - 2024 Revised Guidelines", policy_2024_clauses)

    return {
        "policy_2023": pdf_2023,
        "policy_2024": pdf_2024,
    }


# Ground Truth Test Scenarios for Evaluation Harness
GROUND_TRUTH_EVAL_CASES = [
    {
        "id": "eval_m1_retrieval",
        "module": "Module 1: Policy Intelligence (RAG)",
        "query": "What is the annual income ceiling under the 2024 revised guidelines?",
        "expected_substrings": ["3,00,000", "Three Lakh"],
        "expected_page": 2,
    },
    {
        "id": "eval_m2_comparison",
        "module": "Module 2: Policy Change Detection",
        "expected_changes": [
            {"type": "modified", "clause": "Financial Assistance", "old": "1,000", "new": "1,200", "material": True},
            {"type": "modified", "clause": "Income Ceiling", "old": "2,50,000", "new": "3,00,000", "material": True},
            {"type": "modified", "clause": "Application Channels", "old": "in person", "new": "online via https://esevai.tn.gov.in", "material": True},
            {"type": "added", "clause": "Grievance Redressal", "material": True},
        ]
    },
    {
        "id": "eval_m3_fact_verification",
        "module": "Module 3: Fact Verification",
        "claims": [
            {
                "claim": "The annual income ceiling under the revised Magalir Urimai scheme is Rs 3,00,000.",
                "expected_verdict": "SUPPORTED",
            },
            {
                "claim": "The monthly financial assistance under the scheme was decreased to Rs 500 per month.",
                "expected_verdict": "REFUTED",
            },
            {
                "claim": "Every family receiving the grant will also receive a free solar cooker.",
                "expected_verdict": "UNVERIFIED",
            }
        ]
    },
    {
        "id": "eval_m4_service_guide",
        "module": "Module 4: Public Service Guidance",
        "query": "Apply for Kalaignar Magalir Urimai Thittam online",
        "expected_portal": "https://esevai.tn.gov.in",
        "expected_checklist_keywords": ["Income Certificate", "Patta/Chitta", "Bank Account", "Aadhaar"],
    },
    {
        "id": "eval_m5_grievance",
        "module": "Module 5: Civic Grievance Assistant",
        "complaint_text": "Massive sewage overflow and deep potholes on Rajaji Street causing severe scooter accidents and health hazards.",
        "expected_category_keywords": ["drainage", "sewage", "roads", "civic"],
        "expected_severity": "high",
        "pii_test_payload": "Contact complainant at 9876543210 regarding the leak.",
        "expected_pii_blocked": True,
    }
]
