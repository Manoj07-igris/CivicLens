"""Script to introspect FastAPI OpenAPI spec and generate comprehensive docs/API_INVENTORY.md."""

import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.main import app

def generate_inventory():
    spec = app.openapi()
    paths = spec.get("paths", {})
    
    entries = []
    for path, methods_dict in paths.items():
        for method, op in methods_dict.items():
            if method.lower() in ("parameters", "servers"):
                continue
            tags = op.get("tags", ["General"])
            summary = op.get("summary") or op.get("description") or "-"
            op_id = op.get("operationId", "-")
            entries.append({
                "method": method.upper(),
                "path": path,
                "tags": ", ".join(tags),
                "op_id": op_id,
                "summary": summary.split("\n")[0].strip(),
            })

    # Sort entries by path then method
    entries.sort(key=lambda r: (r["path"], r["method"]))

    md_lines = [
        "# CivicLens AI — Complete API Inventory & Route Catalog",
        "",
        "This catalog documents every active HTTP endpoint in CivicLens (v1.0.0-hackathon), automatically introspected from the application schema.",
        "",
        f"**Total Registered Operations**: {len(entries)} across {len(paths)} unique paths.",
        "",
        "| Method | Path | Tag | Operation ID | Summary / Description |",
        "| :---: | :--- | :--- | :--- | :--- |",
    ]

    for e in entries:
        summary_clean = e["summary"].replace("|", "\\|")
        md_lines.append(f"| `{e['method']}` | `{e['path']}` | {e['tags']} | `{e['op_id']}` | {summary_clean} |")

    md_lines.extend([
        "",
        "---",
        "",
        "## Security, Authentication & Input Validation Controls",
        "",
        "| Domain / Prefix | Rate Limiter | PII Guard | Access / Security Controls |",
        "| :--- | :---: | :---: | :--- |",
        "| `/api/v1/health`, `/api/v1/info` | - | - | Public system probes, zero secret disclosure. |",
        "| `/api/v1/gemini/*` | 5/min | Active | Key masking, model connectivity diagnostics. |",
        "| `/api/v1/documents/*` | 10/min | Active | Max upload 20MB, max 200 pages, UUID validation, traversal immunity. |",
        "| `/api/v1/chat`, `/api/v1/agent/*` | 10/min | Active | XML boundary escaping, evidence ledger, human approval gates. |",
        "| `/api/v1/comparisons/*` | 3/min | Active | Dual PDF alignment, strict clause matching, staged job timeouts. |",
        "| `/api/v1/sources/*` | 5/min | Active | SHA-256 integrity hashing, series tracking, admin gate option. |",
        "| `/api/v1/verifications/*` | 5/min | Active | Tripartite verdict verification, official source cross-check. |",
        "| `/api/v1/portals/*`, `/api/v1/services/*` | 5/min | Active | Verified government URL registry, checklist generation caps. |",
        "| `/api/v1/grievances/*` | 6/min | Active | PII blocking, 25M pixel decompression defense, safe drafting. |",
        "| `/api/v1/browser/*` | 20/min | Active | Playwright isolated demo portal session, strict TTL, orphan process cleanup. |",
        "| `/api/v1/conversations/*`, `/api/v1/activity/*` | - | Active | Parameterized SQLite query persistence, 90-day retention pruning. |",
        "| `/api/v1/system/*` | - | - | Diagnostics, online hot backup, maintenance, memory/thread profiling, confirmation-phrase wipe. |",
        "| `/demo-portal/*` | - | Active | Sandboxed local mock portal simulation; rejects all citizen PII. |",
        ""
    ])

    output_path = Path(__file__).resolve().parent.parent / "docs" / "API_INVENTORY.md"
    output_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Generated {output_path} with {len(entries)} operations.")

if __name__ == "__main__":
    generate_inventory()
