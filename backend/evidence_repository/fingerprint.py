"""Fingerprint helpers for deduplication and correlation."""

from __future__ import annotations

import hashlib

from models.security_finding import SecurityFindingObject


def finding_fingerprint(finding: SecurityFindingObject) -> str:
    """
    Stable fingerprint for deduplication within a tenant/asset.

    Uses tool, type, title, CVEs, and rule/template labels — never raw JSON.
    """

    rule = finding.metadata.labels.get("rule_id") or finding.metadata.labels.get(
        "template_id", ""
    )
    cves = ",".join(sorted(finding.cve_ids))
    material = "|".join(
        [
            str(finding.tenant_id),
            str(finding.asset_id),
            finding.source_tool.value,
            finding.finding_type.value,
            finding.title.strip().lower(),
            cves,
            rule.strip().lower(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def correlation_key(finding: SecurityFindingObject) -> str:
    """
    Cross-scanner correlation key (CVE+asset preferred, else fingerprint sans tool).
    """

    if finding.cve_ids:
        cves = ",".join(sorted(finding.cve_ids))
        material = f"{finding.tenant_id}|{finding.asset_id}|cve|{cves}"
    else:
        rule = finding.metadata.labels.get("rule_id") or finding.metadata.labels.get(
            "template_id", ""
        )
        material = "|".join(
            [
                str(finding.tenant_id),
                str(finding.asset_id),
                finding.finding_type.value,
                finding.title.strip().lower(),
                rule.strip().lower(),
            ]
        )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
