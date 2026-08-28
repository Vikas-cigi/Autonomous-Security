"""Prowler JSON normalizer."""

from __future__ import annotations

from typing import Any, Dict, Sequence

from models.enums import FindingType, SourceTool
from models.security_finding import SecurityFindingObject
from normalization.base_normalizer import BaseNormalizer
from normalization.context import NormalizationContext
from normalization.exceptions import MalformedInputError, NormalizationItemError
from normalization.mapping import clamp_cvss, map_severity


class ProwlerNormalizer(BaseNormalizer):
    """
    Normalize Prowler cloud security findings.

    Accepts list payloads or ``{\"findings\": [...]}`` documents used by
    Prowler v3/v4 JSON exporters. PASS rows are skipped as non-findings.
    """

    @property
    def tool_key(self) -> str:
        return "prowler"

    @property
    def source_tool(self) -> SourceTool:
        return SourceTool.PROWLER

    def extract_items(self, raw_payload: Any) -> Sequence[Dict[str, Any]]:
        payload = raw_payload
        if isinstance(payload, dict):
            for key in ("findings", "results", "Checks", "checks"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
            if "CheckID" in payload or "check_id" in payload or "Status" in payload:
                return [payload]
            raise MalformedInputError(
                "Prowler payload must contain a findings list",
                tool=self.tool_key,
            )
        if not isinstance(payload, list):
            raise MalformedInputError(
                "Prowler payload must be a list or object with findings",
                tool=self.tool_key,
            )
        return payload

    def normalize_item(
        self,
        item: Dict[str, Any],
        context: NormalizationContext,
    ) -> SecurityFindingObject:
        check_id = item.get("CheckID") or item.get("check_id") or item.get("checkId")
        if not check_id:
            self.require_fields(item, ["CheckID"])

        status = str(item.get("Status") or item.get("status") or "").upper()
        if status in {"PASS", "PASSED", "OK"}:
            raise NormalizationItemError(
                "Skipping Prowler PASS result (not a finding)",
                tool=self.tool_key,
            )

        title = str(
            item.get("CheckTitle")
            or item.get("check_title")
            or item.get("title")
            or check_id
        )
        severity = map_severity(item.get("Severity") or item.get("severity"))
        description = str(
            item.get("StatusExtended")
            or item.get("status_extended")
            or item.get("Description")
            or item.get("description")
            or title
        )
        service = item.get("ServiceName") or item.get("service_name") or ""
        region = item.get("Region") or item.get("region") or ""

        evidence = self.build_evidence(
            context=context,
            summary=f"Prowler {check_id} status={status or 'FAIL'} service={service}",
            item=item,
            confidence=0.8,
        )

        finding_type = (
            FindingType.COMPLIANCE
            if item.get("Compliance") or item.get("compliance")
            else FindingType.MISCONFIGURATION
        )

        return SecurityFindingObject(
            tenant_id=context.tenant_id,
            asset_id=context.asset_id,
            source_tool=self.source_tool,
            finding_type=finding_type,
            severity=severity,
            cvss_score=clamp_cvss(None, severity),
            confidence_score=0.78,
            evidence=[evidence],
            title=title[:512],
            description=description[:20000],
            metadata=self.base_metadata(
                context,
                rule_id=str(check_id),
                extra_labels={
                    k: str(v)[:512]
                    for k, v in {
                        "service": service,
                        "region": region,
                        "status": status,
                    }.items()
                    if v
                },
            ),
        )
