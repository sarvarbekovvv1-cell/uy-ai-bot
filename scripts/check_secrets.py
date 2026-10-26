#!/usr/bin/env python3
"""Portable security scanner for detecting secrets and sensitive files before commit/push.

Uses only Python standard library. Suitable for local git hooks and CI/CD pipelines.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Patterns indicating potential raw secrets
SECRET_PATTERNS = [
    (
        "Telegram Bot Token",
        re.compile(r"(?<![A-Za-z0-9_])([0-9]{8,11}:[A-Za-z0-9_-]{35})(?![A-Za-z0-9_])"),
    ),
    (
        "Google AI / Gemini API Key (AIza)",
        re.compile(r"(?<![A-Za-z0-9_])(AIza[0-9A-Za-z_-]{35})(?![A-Za-z0-9_])"),
    ),
    (
        "Google AI / Gemini API Key (AQ)",
        re.compile(r"(?<![A-Za-z0-9_])(AQ\.[0-9A-Za-z_-]{35,})(?![A-Za-z0-9_])"),
    ),
    (
        "Private Key",
        re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----"),
    ),
    (
        "Generic API Key / Token Assignment",
        re.compile(
            r"(?i)(?:api_key|bot_token|access_token|refresh_token|secret_key|client_secret)\s*[:=]\s*['\"]([^'\"]{20,})['\"]"
        ),
    ),
]

# Patterns for dangerous file names that should never be committed
DANGEROUS_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env(?:\.(?!example$)[a-zA-Z0-9_-]+)?$"),
    re.compile(r".*\.(pem|key|p12|pfx|pkcs12)$"),
    re.compile(r"(^|/)(credentials|secrets)/"),
    re.compile(r".*\.(sqlite|sqlite3|db)$"),
]

# Paths explicitly whitelisted from scans
WHITELISTED_PATHS = {
    ".env.example",
    "README.md",
    "scripts/check_secrets.py",
}

# Known harmless test dummy tokens
KNOWN_TEST_DUMMIES = {
    "123456789:" + "ABCdefGhIJKlmNoPQRstuVWXyz",
    "123456789:" + "ABCdefGhIJKlmNoPQRsTUVwxyZ-12345Xyz",
    "test-gemini-api-key-12345",
}

# Values that are explicitly benign mocks/placeholders
MOCK_INDICATORS = {
    "test",
    "mock",
    "fake",
    "dummy",
    "placeholder",
    "example",
    "sample",
    "your_telegram_bot_token",
    "your_gemini_api_key",
    "postgresql://",
}

IGNORE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}

BENIGN_TEST_KEYWORDS = [
    "dummy",
    "fake",
    "mock",
    "example",
    "placeholder",
    "test",
    "token",
    "key",
]


def mask_secret(val: str) -> str:
    """Mask secret value for safe reporting."""
    if len(val) <= 8:
        return "***"
    return f"{val[:3]}...{val[-3:]}"


def is_mock_value(val: str) -> bool:
    """Check if value is clearly a dummy/mock placeholder."""
    val_lower = val.lower()
    if val in KNOWN_TEST_DUMMIES:
        return True
    return any(ind in val_lower for ind in MOCK_INDICATORS)


def get_git_files(repo_root: Path) -> list[Path]:
    """Get list of files tracked by git, or fallback to scanning directory."""
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
        )
        paths = [repo_root / p for p in output.decode("utf-8").split("\0") if p]
        return [p for p in paths if p.is_file()]
    except Exception:
        files = []
        for root, dirs, filenames in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fn in filenames:
                p = Path(root) / fn
                files.append(p)
        return files


def scan_repo(repo_root: Path) -> list[str]:
    """Scan the repository for dangerous files and potential secret leaks."""
    findings: list[str] = []
    files = get_git_files(repo_root)

    for file_path in files:
        rel_path = file_path.relative_to(repo_root).as_posix()

        # Whitelisted files skip all checks
        if rel_path in WHITELISTED_PATHS:
            continue

        # Check dangerous filenames
        for pattern in DANGEROUS_FILE_PATTERNS:
            if pattern.search(rel_path):
                findings.append(f"Dangerous file tracked in git: {rel_path}")
                break

        # Skip binary files and known non-code assets
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            # Check secret patterns
            for name, pattern in SECRET_PATTERNS:
                matches = pattern.finditer(line)
                for match in matches:
                    secret_val = match.group(1) if match.groups() else match.group(0)
                    if is_mock_value(secret_val):
                        continue
                    if "check_secrets.py" in rel_path:
                        continue

                    # If file is in tests/, allow mock-like values or fixtures
                    if rel_path.startswith("tests/"):
                        line_lower = line.lower()
                        if any(w in line_lower for w in BENIGN_TEST_KEYWORDS):
                            continue

                    findings.append(
                        f"Potential {name} at {rel_path}:{line_no} [{mask_secret(secret_val)}]"
                    )

    return findings


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    findings = scan_repo(repo_root)

    if findings:
        print("❌ Security audit failed! Potential secrets or dangerous files detected:")
        for finding in findings:
            print(f"  - {finding}")
        print("\nPlease remove all sensitive credentials and unstage dangerous files.")
        return 1

    print("✅ Security audit passed: No exposed secrets or dangerous files detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
