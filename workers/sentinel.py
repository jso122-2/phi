"""
Sentinel — sensitive-file protection layer for the oesophagus pipeline.

Every file is screened before ingestion.  The sentinel runs three passes:

  1. Extension block-list  — hard-reject file types that should never enter
                             the vault (key files, env files, credential stores)
  2. Pattern scan          — regex scan of the first SCAN_BYTES of text files
                             for credentials, tokens, private keys, PII
  3. Path quarantine       — path component check for suspicious directory
                             names (shadow, vault, .ssh, .gnupg, etc.)

A file must pass all three gates.  Blocked files are never read beyond what
is needed for screening — they are quarantined in place and a SentinelReport
is returned explaining why.

Sensitive content found inside a file that is not block-listed is REDACTED
from the ingested text, not blocked outright.  The file enters the vault
with a [REDACTED] marker so the graph knows it exists but the secret is
never written to any .md node.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCAN_BYTES = 8_192  # max bytes read for pattern scanning

# Extensions that must never enter the vault under any circumstances
_BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".cer", ".crt",   # certificates / private keys
    ".env", ".envrc",                                   # environment files
    ".netrc", ".npmrc", ".pypirc",                      # credential stores
    ".gpg", ".asc",                                     # encrypted blobs
    ".id_rsa", ".id_ed25519", ".id_ecdsa",              # SSH private keys
    ".shadow", ".htpasswd",                             # auth files
    ".kdbx", ".kdb",                                    # KeePass databases
})

# Directory path components that quarantine everything under them.
# These are matched against individual path part names, so they must be
# specific enough to not collide with OS-level directory names.
# "private" is intentionally excluded — macOS resolves /var/folders through
# /private/var/folders, which would falsely quarantine all temp files.
_QUARANTINE_DIRS: frozenset[str] = frozenset({
    ".ssh", ".gnupg", ".aws", ".azure", ".gcloud",
    "credentials", "secrets", "shadow",
    ".vault",
})

# Patterns that trigger REDACTION (not full block) in file content
_SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key",         re.compile(r'(?i)(api[_\-]?key\s*[:=]\s*)[\w\-]{16,}', re.I)),
    ("secret_key",      re.compile(r'(?i)(secret[_\-]?key\s*[:=]\s*)[\w\-]{16,}', re.I)),
    ("token",           re.compile(r'(?i)(token\s*[:=]\s*)[\w\-\.]{20,}', re.I)),
    ("password",        re.compile(r'(?i)(password\s*[:=]\s*)\S{6,}', re.I)),
    ("bearer_token",    re.compile(r'(?i)bearer\s+[\w\-\.]{20,}')),
    ("private_key_pem", re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ("aws_access_key",  re.compile(r'(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])')),
    ("aws_secret",      re.compile(r'(?i)aws[_\-]secret[_\-]access[_\-]key\s*[:=]\s*[\w/+]{40}')),
    ("github_pat",      re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}')),
    ("spotify_secret",  re.compile(r'(?i)spotify[_\-]?(client[_\-]?secret|token)\s*[:=]\s*[\w\-]{16,}')),
    ("basic_auth_url",  re.compile(r'https?://\w+:[^@\s]{4,}@')),
]

_REDACT_MARKER = "[REDACTED by Sentinel]"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SentinelReport:
    path: str
    allowed: bool
    redacted: bool = False
    block_reason: str = ""
    redactions: list[str] = field(default_factory=list)
    safe_text: str | None = None   # cleaned text if file was allowed; None if blocked

    def __str__(self) -> str:
        if not self.allowed:
            return f"BLOCKED  {self.path!r}  reason={self.block_reason!r}"
        if self.redacted:
            return f"REDACTED {self.path!r}  patterns={self.redactions}"
        return f"PASSED   {self.path!r}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extension_blocked(path: Path) -> str:
    """Return block reason string if extension is on the block-list, else ''.

    Handles three cases:
    1. Normal extension:  secrets.pem  → suffix='.pem'
    2. Dotfile with ext:  .npmrc       → suffix='' but name='.npmrc' → check '.npmrc'
    3. Dotfile plain:     .env         → suffix='' and name='.env'   → check '.env'
    """
    ext = path.suffix.lower()
    name = path.name.lower()
    # For dotfiles where Python reports no suffix (e.g. .env, .netrc),
    # treat the full name as the "extension" to check
    candidates = {ext} if ext else set()
    if not ext and name.startswith("."):
        candidates.add(name)           # e.g. '.env', '.netrc'
    for candidate in candidates:
        if candidate in _BLOCKED_EXTENSIONS:
            return f"blocked extension: {candidate}"
    return ""


def _path_quarantined(path: Path) -> str:
    """Return block reason if any parent directory is on the quarantine list."""
    parts = {p.lower() for p in path.parts}
    hit = parts & _QUARANTINE_DIRS
    if hit:
        return f"quarantined directory: {hit.pop()}"
    return ""


def _scan_content(text: str) -> tuple[str, list[str]]:
    """
    Scan text for sensitive patterns.

    Returns
    -------
    cleaned_text  : text with sensitive matches replaced by _REDACT_MARKER
    found_patterns: list of pattern names that were triggered
    """
    found: list[str] = []
    out = text
    for name, pat in _SENSITIVE_PATTERNS:
        def _replace(m: re.Match, _name: str = name) -> str:
            found.append(_name)
            # Keep the key/label portion, redact the value
            groups = m.groups()
            if groups:
                return groups[0] + _REDACT_MARKER
            return _REDACT_MARKER

        out, n = pat.subn(_replace, out)
        if n == 0 and name in found:
            found.remove(name)  # subn with the closure adds duplicates — dedupe

    deduped = list(dict.fromkeys(found))
    return out, deduped


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def screen(path: Path, text: str | None = None) -> SentinelReport:
    """
    Screen a single file.

    Parameters
    ----------
    path : path to the file
    text : if already read, pass the text to avoid a second disk read.
           If None and the file is text-readable, it is read up to SCAN_BYTES.

    Returns
    -------
    SentinelReport  — always returned, even for blocked files.
                      Check `.allowed` before using `.safe_text`.
    """
    p = Path(path)

    # Gate 1: extension
    reason = _extension_blocked(p)
    if reason:
        return SentinelReport(path=str(p), allowed=False, block_reason=reason)

    # Gate 2: path quarantine
    reason = _path_quarantined(p)
    if reason:
        return SentinelReport(path=str(p), allowed=False, block_reason=reason)

    # Gate 3: content scan (only for text files)
    if text is None:
        try:
            raw = p.read_bytes()
            # Quick binary sniff: if >30% non-printable bytes, skip content scan
            sample = raw[:512]
            non_print = sum(1 for b in sample if b < 9 or (13 < b < 32) or b == 127)
            if len(sample) > 0 and non_print / len(sample) > 0.30:
                return SentinelReport(path=str(p), allowed=True, safe_text=None)
            text = raw[:SCAN_BYTES].decode("utf-8", errors="replace")
        except OSError:
            return SentinelReport(path=str(p), allowed=True, safe_text=None)

    cleaned, found = _scan_content(text)

    return SentinelReport(
        path=str(p),
        allowed=True,
        redacted=bool(found),
        redactions=found,
        safe_text=cleaned,
    )


def screen_batch(paths: list[Path]) -> list[SentinelReport]:
    """Screen a list of paths, returning one SentinelReport per path."""
    return [screen(p) for p in paths]
