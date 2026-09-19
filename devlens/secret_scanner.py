"""Heuristic secret / credential exposure scanner.

IMPORTANT HONESTY NOTE (see README/SECURITY.md):
This is heuristic pattern + entropy based detection. It does not
guarantee that all secrets are found, and not every finding is
necessarily a real credential. Findings are meant to prompt human
review, not to serve as a certification of "no secrets present".

Secrets are NEVER reproduced in full anywhere: not in the terminal
report, not in JSON, not in CSV. Only a short, safe, redacted prefix
is ever shown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .models import Finding, Severity
from .utils import redact, safe_read_text, shannon_entropy, stable_hash_int

MAX_SECRET_SCAN_BYTES = 2 * 1024 * 1024  # don't fully scan huge files

# Obvious placeholder values that should never be flagged.
PLACEHOLDER_TOKENS = {
    "changeme", "your_api_key", "your-api-key", "xxxxxxxx", "example",
    "placeholder", "insert_key_here", "dummy", "fake", "test", "secret",
    "password", "yourpassword", "your_password_here", "todo", "tbd",
    "none", "null", "1234567890", "abcdef", "sample", "demo1234",
}

FILENAME_HINTS = {".env", ".env.local", ".env.production", "credentials", "secrets.json"}


@dataclass
class SecretRule:
    id: str
    category: str
    pattern: re.Pattern
    severity: Severity
    title: str
    explanation: str
    recommendation: str
    min_entropy: Optional[float] = None


def _compile_rules() -> List[SecretRule]:
    return [
        SecretRule(
            id="SEC-AWS-KEY",
            category="Security",
            pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            severity=Severity.CRITICAL,
            title="Possible AWS access key ID",
            explanation="This string matches the format of an AWS access key ID (AKIA...).",
            recommendation="Rotate the credential immediately and remove it from source control history.",
        ),
        SecretRule(
            id="SEC-GH-TOKEN",
            category="Security",
            pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
            severity=Severity.CRITICAL,
            title="Possible GitHub token",
            explanation="This string matches the format of a GitHub personal access / app token.",
            recommendation="Revoke the token in GitHub settings and rotate it.",
        ),
        SecretRule(
            id="SEC-SLACK-TOKEN",
            category="Security",
            pattern=re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
            severity=Severity.HIGH,
            title="Possible Slack token",
            explanation="This string matches the format of a Slack API token.",
            recommendation="Revoke the token in Slack app settings and rotate it.",
        ),
        SecretRule(
            id="SEC-STRIPE-KEY",
            category="Security",
            pattern=re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{16,}\b"),
            severity=Severity.HIGH,
            title="Possible Stripe API key",
            explanation="This string matches the format of a Stripe secret/publishable key.",
            recommendation="Rotate the key from the Stripe dashboard immediately if this is a live key.",
        ),
        SecretRule(
            id="SEC-GOOGLE-KEY",
            category="Security",
            pattern=re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
            severity=Severity.HIGH,
            title="Possible Google API key",
            explanation="This string matches the format of a Google API key.",
            recommendation="Restrict or rotate the key in the Google Cloud Console.",
        ),
        SecretRule(
            id="SEC-PRIVATE-KEY",
            category="Security",
            pattern=re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----"),
            severity=Severity.CRITICAL,
            title="Private key material detected",
            explanation="A PEM-format private key header was found in this file.",
            recommendation="Remove the private key from the repository and rotate it; private keys should never be committed.",
        ),
        SecretRule(
            id="SEC-JWT",
            category="Security",
            pattern=re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
            severity=Severity.MEDIUM,
            title="Possible JWT token",
            explanation="This string has the three-part base64url structure of a JSON Web Token.",
            recommendation="Confirm this is not a live session/auth token; rotate if it is.",
        ),
        SecretRule(
            id="SEC-DB-CONN",
            category="Security",
            pattern=re.compile(r"\b(postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://[^\s\"']+:[^\s\"'@]+@[^\s\"']+"),
            severity=Severity.HIGH,
            title="Database connection string with embedded credentials",
            explanation="A connection URI containing an inline username/password was found.",
            recommendation="Move credentials to environment variables or a secrets manager instead of a connection string literal.",
        ),
        SecretRule(
            id="SEC-BEARER",
            category="Security",
            pattern=re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{20,}"),
            severity=Severity.MEDIUM,
            title="Possible bearer token",
            explanation="A hardcoded 'Bearer <token>' authorization value was found.",
            recommendation="Load bearer tokens from environment/config at runtime rather than hardcoding them.",
        ),
        SecretRule(
            id="SEC-GENERIC-ASSIGN",
            category="Security",
            pattern=re.compile(
                r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|pwd)\b"
                r"\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]"
            ),
            severity=Severity.MEDIUM,
            title="Possible hardcoded credential assignment",
            explanation="A variable name commonly associated with credentials is assigned a literal string value.",
            recommendation="Move this value into an environment variable, .env file (excluded from git), or a secrets manager.",
            min_entropy=2.5,
        ),
    ]


class SecretScanner:
    def __init__(self):
        self.rules = _compile_rules()

    def scan_file(self, path: Path, rel_path: str) -> List[Finding]:
        findings: List[Finding] = []
        text = safe_read_text(path, max_bytes=MAX_SECRET_SCAN_BYTES)
        if text is None:
            return findings

        lines = text.splitlines()
        seen_on_line: set = set()

        for line_no, line in enumerate(lines, start=1):
            for rule in self.rules:
                for match in rule.pattern.finditer(line):
                    value = match.group(2) if match.groups() and rule.id == "SEC-GENERIC-ASSIGN" else match.group(0)
                    if self._is_placeholder(value):
                        continue
                    if rule.min_entropy is not None and shannon_entropy(value) < rule.min_entropy:
                        continue
                    key = (rule.id, line_no)
                    if key in seen_on_line:
                        continue
                    seen_on_line.add(key)

                    findings.append(
                        Finding(
                            id=f"{rule.id}-{len(findings) + 1:03d}",
                            severity=rule.severity,
                            category=rule.category,
                            title=rule.title,
                            path=rel_path,
                            line=line_no,
                            evidence=self._safe_evidence(line, value),
                            explanation=rule.explanation,
                            recommendation=rule.recommendation,
                        )
                    )

        # Bare mention of a sensitive filename (e.g. committed .env)
        name = path.name.lower()
        if name in FILENAME_HINTS or name.startswith(".env"):
            findings.append(
                Finding(
                    id=f"SEC-ENV-FILE-{stable_hash_int(rel_path):03d}",
                    severity=Severity.MEDIUM,
                    category="Security",
                    title="Environment/credentials file present in repository",
                    path=rel_path,
                    line=None,
                    evidence="(filename pattern match, contents not reproduced)",
                    explanation="Files like .env or credentials.json commonly store secrets and should usually not be committed.",
                    recommendation="Add this file to .gitignore and commit a .env.example with placeholder values instead.",
                )
            )

        return findings

    _PLACEHOLDER_HINT = re.compile(
        r"your[_-]?(api)?[_-]?(key|token|secret|password)|"
        r"(key|token|secret|password)[_-]?(here|goes[_-]?here)|"
        r"insert[_-]?.*[_-]?here|<[^>]+>|\{\{.*\}\}|\$\{.*\}"
    )

    @classmethod
    def _is_placeholder(cls, value: str) -> bool:
        stripped = value.strip().strip("'\"")
        lowered = stripped.lower()
        if lowered in PLACEHOLDER_TOKENS:
            return True
        if re.fullmatch(r"x{4,}|\*{4,}|0{4,}", lowered):
            return True
        if len(stripped) < 8:
            return True
        if cls._PLACEHOLDER_HINT.search(lowered):
            return True
        return False

    @staticmethod
    def _safe_evidence(line: str, value: str) -> str:
        redacted_value = redact(value)
        safe_line = line.replace(value, redacted_value)
        safe_line = safe_line.strip()
        if len(safe_line) > 160:
            safe_line = safe_line[:160] + "..."
        return safe_line
