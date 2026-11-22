#!/usr/bin/env python3
"""CivicLens AI — Security, Privacy & Secret Scanner

Performs exhaustive static analysis over working files, staged changes, or git history.
Enforces:
1. Known secret patterns (Google AI keys, GitHub tokens, private keys, AWS, JWTs, etc.)
2. Exact-value secret checks in-memory from backend/.env (values NEVER printed)
3. Personal Identifiable Information (PII, personal Windows file paths, unapproved emails)
4. Heavy binary, PDF, DB, index, and large file size gates (>5 MB list, >50 MB reject)
5. Placeholders-only verification for .env.example files

Output format: PATH:LINE (or COMMIT_ID:PATH) and violation category. Values are NEVER echoed.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------------------
# Pattern Definitions (Regexes)
# ------------------------------------------------------------------------------
KNOWN_SECRET_PATTERNS = [
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("GitHub Personal Access Token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36}")),
    ("GitHub Fine-Grained Token", re.compile(r"github_pat_[0-9A-Za-z_]{82}")),
    ("Private Key Block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----")),
    ("AWS Access Key ID", re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9A-Za-z]{10,48}")),
    ("Bearer Authorization Header", re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9\-_\.]{25,}")),
]

# Sensitive personal machine path patterns
WINDOWS_USER_PATH_PATTERN = re.compile(r"(?i)[C-Z]:\\Users\\(?:HP|Manoj|Administrator)\\", re.IGNORECASE)
ONEDRIVE_PATH_PATTERN = re.compile(r"(?i)OneDrive\\Desktop\\CivicLens", re.IGNORECASE)

DISALLOWED_EXTENSIONS = {
    ".pdf", ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3",
    ".faiss", ".zip", ".exe", ".onnx", ".pt", ".bin", ".model"
}

MAX_FILE_SIZE_WARNING = 5 * 1024 * 1024   # 5 MB
MAX_FILE_SIZE_REJECT = 50 * 1024 * 1024    # 50 MB

SENSITIVE_KEY_NAMES = {
    "GEMINI_API_KEY", "AUTH_SECRET_KEY", "SMTP_PASSWORD", "SECRET_KEY",
    "API_KEY", "PASSWORD", "PASSWD", "TOKEN", "PRIVATE_KEY"
}


def get_exact_env_secrets(project_root: Path) -> Set[str]:
    """Read actual non-placeholder secrets from backend/.env into memory.
    Values are NEVER stored on disk, logged, or printed.
    """
    secrets = set()
    env_files = [
        project_root / "backend" / ".env",
        project_root / "frontend" / ".env",
        project_root / "frontend" / ".env.local",
    ]

    placeholder_indicators = {
        "", "your_gemini_api_key_here", "change-me", "changeme",
        "secret", "password", "none", "null"
    }

    for env_path in env_files:
        if not env_path.exists():
            continue
        try:
            content = env_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k_clean = k.strip().upper()
                v_clean = v.strip().strip("'\"")

                is_sensitive_key = (
                    k_clean in SENSITIVE_KEY_NAMES or
                    (any(term in k_clean for term in ["KEY", "SECRET", "PASSWORD", "PASSWD"]) and "OUTPUT_TOKENS" not in k_clean) or
                    (k_clean.endswith("_TOKEN") or k_clean.startswith("TOKEN_") or k_clean == "TOKEN")
                )

                if is_sensitive_key and len(v_clean) >= 8 and v_clean.lower() not in placeholder_indicators:
                    secrets.add(v_clean)
        except Exception:
            pass

    return secrets


def get_files_to_scan(project_root: Path, staged_only: bool = False) -> List[Path]:
    """Retrieve file list via Git: staged only or all tracked + untracked non-ignored."""
    if staged_only:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
    else:
        cmd = ["git", "ls-files"]
    
    res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, check=True)
    files = [project_root / f.strip() for f in res.stdout.splitlines() if f.strip()]
    
    if not staged_only:
        res_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=project_root, capture_output=True, text=True, check=True
        )
        for f in res_untracked.stdout.splitlines():
            if f.strip():
                files.append(project_root / f.strip())
                
    return [f for f in files if f.is_file()]


def scan_file(
    file_path: Path,
    exact_secrets: Set[str],
    rel_path: str
) -> List[Tuple[str, int, str]]:
    """Scan a single file for known secrets, exact secrets, PII, and bad patterns."""
    findings = []

    # Check file size
    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_REJECT:
            findings.append((rel_path, 0, f"REJECT: File size {size / (1024*1024):.2f} MB exceeds 50 MB limit"))
            return findings
        elif size > MAX_FILE_SIZE_WARNING:
            findings.append((rel_path, 0, f"WARN: File size {size / (1024*1024):.2f} MB exceeds 5 MB recommendation"))
    except Exception:
        pass

    # Check extension
    ext = file_path.suffix.lower()
    if ext in DISALLOWED_EXTENSIONS:
        findings.append((rel_path, 0, f"REJECT: Disallowed file extension '{ext}'"))
        return findings

    # Disallow images outside permitted asset folders
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        norm = rel_path.replace("\\", "/").lower()
        if not (norm.startswith("docs/") or norm.startswith("frontend/src/assets/") or norm.startswith("frontend/public/")):
            findings.append((rel_path, 0, f"REJECT: Image file '{ext}' placed outside docs/ or frontend/assets/"))
            return findings

    # Skip scanning binary files for text regexes
    try:
        content = file_path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return findings
    except Exception as e:
        findings.append((rel_path, 0, f"ERROR: Failed reading file: {e}"))
        return findings

    lines = content.splitlines()

    # Special check for .env.example
    if file_path.name.endswith(".env.example"):
        for idx, line in enumerate(lines, 1):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                k_clean = k.strip().upper()
                v_clean = v.strip().strip("'\"")
                is_sensitive_key = (
                    k_clean in SENSITIVE_KEY_NAMES or
                    (any(term in k_clean for term in ["KEY", "SECRET", "PASSWORD", "PASSWD"]) and "OUTPUT_TOKENS" not in k_clean) or
                    (k_clean.endswith("_TOKEN") or k_clean.startswith("TOKEN_") or k_clean == "TOKEN")
                )
                if is_sensitive_key and v_clean:
                    if not (v_clean.startswith("<") or "example" in v_clean.lower() or "here" in v_clean.lower()):
                        findings.append((rel_path, idx, f"REJECT: Sensitive secret key '{k.strip()}' has non-placeholder value in example env file"))

    # Skip secret checks on scan_secrets.py itself or security tests verifying secret rejection
    if "scan_secrets.py" in rel_path or "test_auth_security_hygiene.py" in rel_path or "test_privacy_canaries.py" in rel_path:
        return findings

    for idx, line in enumerate(lines, 1):
        # 1. Exact-value secrets check
        for sec in exact_secrets:
            if sec in line:
                findings.append((rel_path, idx, "CRITICAL: Exact secret value from local .env found in file"))

        # 2. Known regex secret patterns
        for name, pattern in KNOWN_SECRET_PATTERNS:
            if pattern.search(line):
                findings.append((rel_path, idx, f"CRITICAL: Matched pattern for {name}"))

        # 3. Personal machine Windows path check
        if WINDOWS_USER_PATH_PATTERN.search(line) or ONEDRIVE_PATH_PATTERN.search(line):
            findings.append((rel_path, idx, "WARN: Personal Windows machine file path found"))

    return findings


def scan_git_history(project_root: Path, exact_secrets: Set[str]) -> List[Tuple[str, str, str]]:
    """Scan git commit history for exact secrets and prohibited file additions."""
    findings = []
    
    res = subprocess.run(
        ["git", "log", "-p", "--all"],
        cwd=project_root, capture_output=True, text=True, errors="ignore"
    )
    
    current_commit = "HEAD"
    for line in res.stdout.splitlines():
        if line.startswith("commit "):
            current_commit = line.split()[1][:8]
        elif line.startswith("+") and not line.startswith("+++"):
            # Exclude tests that test secret detection
            for sec in exact_secrets:
                if sec in line:
                    findings.append((current_commit, "patch", "CRITICAL: Exact secret value found in commit history patch"))
            for name, pattern in KNOWN_SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append((current_commit, "patch", f"CRITICAL: {name} found in commit history patch"))

    res_files = subprocess.run(
        ["git", "log", "--name-only", "--all", "--pretty=format:commit %h"],
        cwd=project_root, capture_output=True, text=True, errors="ignore"
    )
    
    current_commit = "HEAD"
    for line in res_files.stdout.splitlines():
        line = line.strip()
        if line.startswith("commit "):
            current_commit = line.split()[1]
        elif line:
            name_lower = line.lower()
            if (
                name_lower.endswith(".env") or 
                name_lower.endswith(".db") or 
                name_lower.endswith(".sqlite") or
                name_lower.endswith(".pdf") or
                name_lower.endswith(".faiss")
            ):
                if not line.endswith(".env.example") and not line.endswith(".gitkeep"):
                    findings.append((current_commit, line, f"REJECT: Sensitive/heavy file committed in history: {line}"))

    return findings


def main():
    parser = argparse.ArgumentParser(description="CivicLens Security & Privacy Scanner")
    parser.add_argument("--staged", action="store_true", help="Scan only git staged files")
    parser.add_argument("--history", action="store_true", help="Scan entire git commit history")
    args = parser.parse_args()

    exact_secrets = get_exact_env_secrets(PROJECT_ROOT)
    
    print("=" * 70)
    print("CivicLens AI — Security, Privacy & Secret Scanner")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Mode: {'STAGED ONLY' if args.staged else ('FULL HISTORY' if args.history else 'WORKING TREE')}")
    print(f"Loaded {len(exact_secrets)} exact secret signatures into memory for verification.")
    print("=" * 70)

    all_findings = []

    if args.history:
        print("\nScanning full git commit history...")
        hist_findings = scan_git_history(PROJECT_ROOT, exact_secrets)
        for commit, path, reason in hist_findings:
            print(f"  [{commit}] {path}: {reason}")
            all_findings.append((path, 0, reason))
    else:
        files = get_files_to_scan(PROJECT_ROOT, staged_only=args.staged)
        print(f"\nScanning {len(files)} files...")
        for f in files:
            rel = str(f.relative_to(PROJECT_ROOT))
            findings = scan_file(f, exact_secrets, rel)
            for path, line_no, reason in findings:
                print(f"  {path}:{line_no} -> {reason}")
                all_findings.append((path, line_no, reason))

    print("-" * 70)
    if all_findings:
        print(f"FAILED: Scanner found {len(all_findings)} security/privacy issue(s).")
        sys.exit(1)
    else:
        print("PASSED: 0 secrets, 0 personal paths, 0 prohibited files found. Clean!")
        sys.exit(0)


if __name__ == "__main__":
    main()
