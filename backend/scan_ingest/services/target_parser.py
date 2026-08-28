"""Parse scan intents and targets from free-form chat messages."""

from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse

from scan_ingest.exceptions import ScanTargetParseError

_SCAN_HINT = re.compile(
    r"\b(scan|nuclei|trivy|prowler|checkov|probe|enumerate|vuln(?:erability)?\s*scan)\b",
    re.IGNORECASE,
)

_URL = re.compile(
    r"(https?://[^\s<>\"']+|(?:[\w-]+\.)+[a-zA-Z]{2,}(?::\d{1,5})?(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)

_TOOL_HINTS = (
    ("nuclei", re.compile(r"\bnuclei\b", re.I)),
    ("trivy", re.compile(r"\btrivy\b", re.I)),
    ("prowler", re.compile(r"\bprowler\b", re.I)),
    ("checkov", re.compile(r"\bcheckov\b", re.I)),
)


def is_scan_intent(message: str) -> bool:
    """Return True when the message looks like a scan request."""

    if not message or not message.strip():
        return False
    return bool(_SCAN_HINT.search(message))


def detect_tool_name(message: str, *, default: str = "nuclei") -> str:
    """Pick a scanner tool from message keywords."""

    for name, pattern in _TOOL_HINTS:
        if pattern.search(message or ""):
            return name
    return default


def extract_target(message: str) -> str:
    """
    Extract the first URL/host-like target from ``message``.

    Raises:
        ScanTargetParseError: when no usable target is present.
    """

    if not message or not message.strip():
        raise ScanTargetParseError("Empty message; no scan target.")

    match = _URL.search(message)
    if not match:
        raise ScanTargetParseError(
            "No scan target found. Include a URL or hostname "
            "(e.g. 'scan https://api.example.com').",
            details={"message_excerpt": message[:200]},
        )

    target = match.group(1).rstrip(".,);]")
    if "://" not in target and not target.startswith("/"):
        # Prefer https for bare hostnames so adapters get a full URL.
        target = f"https://{target}"
    return target


def parse_scan_message(message: str) -> Tuple[str, str]:
    """Return ``(tool_name, target)`` parsed from a chat message."""

    if not is_scan_intent(message):
        raise ScanTargetParseError(
            "Message is not a scan intent.",
            details={"message_excerpt": (message or "")[:200]},
        )
    tool = detect_tool_name(message)
    target = extract_target(message)
    return tool, target


def asset_external_id_for_target(target: str) -> str:
    """Stable external_id used to upsert inventory assets for a target."""

    parsed = urlparse(target if "://" in target else f"https://{target}")
    host = parsed.hostname or target
    port = f":{parsed.port}" if parsed.port else ""
    path = (parsed.path or "").rstrip("/")
    return f"scan-target:{host}{port}{path}"[:512]


def short_asset_name(target: str) -> str:
    """Human-readable asset name derived from target."""

    parsed = urlparse(target if "://" in target else f"https://{target}")
    return (parsed.hostname or target)[:256]
