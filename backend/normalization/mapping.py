"""
Severity / taxonomy mapping helpers shared by tool adapters.
"""

from __future__ import annotations

from typing import Optional

from models.enums import FindingType, Severity


_SEVERITY_ALIASES = {
    "critical": Severity.CRITICAL,
    "crit": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "med": Severity.MEDIUM,
    "moderate": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFORMATIONAL,
    "informational": Severity.INFORMATIONAL,
    "none": Severity.INFORMATIONAL,
    "unknown": Severity.UNKNOWN,
    "negligible": Severity.LOW,
}


# Representative CVSS midpoints consistent with SecurityFindingObject validators.
_SEVERITY_CVSS = {
    Severity.CRITICAL: 9.5,
    Severity.HIGH: 8.0,
    Severity.MEDIUM: 5.5,
    Severity.LOW: 2.0,
    Severity.INFORMATIONAL: 0.0,
    Severity.UNKNOWN: None,
}


def map_severity(raw: Optional[str]) -> Severity:
    """Map vendor severity strings onto canonical ``Severity``."""

    if raw is None:
        return Severity.UNKNOWN
    key = str(raw).strip().lower()
    return _SEVERITY_ALIASES.get(key, Severity.UNKNOWN)


def cvss_for_severity(severity: Severity) -> Optional[float]:
    """
    Return a CVSS value aligned with severity bands.

    Returns ``None`` for ``UNKNOWN`` so validators do not enforce a band.
    """

    return _SEVERITY_CVSS[severity]


def clamp_cvss(score: Optional[float], severity: Severity) -> Optional[float]:
    """
    Clamp an upstream CVSS into the band required by ``SecurityFindingObject``.

    If score is missing, derive a representative value from severity.
    """

    if score is None:
        return cvss_for_severity(severity)

    try:
        value = float(score)
    except (TypeError, ValueError):
        return cvss_for_severity(severity)

    value = max(0.0, min(10.0, value))
    bands = {
        Severity.CRITICAL: (9.0, 10.0),
        Severity.HIGH: (7.0, 8.9),
        Severity.MEDIUM: (4.0, 6.9),
        Severity.LOW: (0.1, 3.9),
        Severity.INFORMATIONAL: (0.0, 0.0),
        Severity.UNKNOWN: (0.0, 10.0),
    }
    low, high = bands[severity]
    if severity == Severity.INFORMATIONAL:
        return 0.0
    if severity == Severity.UNKNOWN:
        return value
    return max(low, min(high, value))


def map_finding_type(*, category: Optional[str] = None, default: FindingType) -> FindingType:
    """Best-effort map of vendor categories onto ``FindingType``."""

    if not category:
        return default
    key = category.strip().lower()
    mapping = {
        "vulnerability": FindingType.VULNERABILITY,
        "vuln": FindingType.VULNERABILITY,
        "misconfiguration": FindingType.MISCONFIGURATION,
        "misconfig": FindingType.MISCONFIGURATION,
        "configuration": FindingType.MISCONFIGURATION,
        "secret": FindingType.SECRET_EXPOSURE,
        "secrets": FindingType.SECRET_EXPOSURE,
        "exposure": FindingType.EXPOSURE,
        "compliance": FindingType.COMPLIANCE,
        "identity": FindingType.IDENTITY_RISK,
        "malware": FindingType.MALWARE,
        "supply-chain": FindingType.SUPPLY_CHAIN,
        "supply_chain": FindingType.SUPPLY_CHAIN,
    }
    return mapping.get(key, default)
