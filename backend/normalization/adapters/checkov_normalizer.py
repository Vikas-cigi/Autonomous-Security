"""Checkov JSON normalizer."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from models.enums import FindingType, SourceTool
from models.security_finding import SecurityFindingObject
from normalization.base_normalizer import BaseNormalizer
from normalization.context import NormalizationContext
from normalization.exceptions import MalformedInputError
from normalization.mapping import clamp_cvss, map_severity


class CheckovNormalizer(BaseNormalizer):
    """
    Normalize Checkov IaC / policy-as-code results.

    Accepts Checkov CLI JSON with ``results.failed_checks`` or a flat list of
    failed check objects.
    """

    @property
    def tool_key(self) -> str:
        return "checkov"

    @property
    def source_tool(self) -> SourceTool:
        return SourceTool.CHECKOV

    def extract_items(self, raw_payload: Any) -> Sequence[Dict[str, Any]]:
        if isinstance(raw_payload, list):
            return raw_payload

        if not isinstance(raw_payload, dict):
            raise MalformedInputError(
                "Checkov payload must be an object or list",
                tool=self.tool_key,
            )

        results = raw_payload.get("results")
        if isinstance(results, dict):
            failed = results.get("failed_checks") or results.get("failedChecks") or []
            if isinstance(failed, list):
                return failed

        for key in ("failed_checks", "failedChecks", "findings"):
            value = raw_payload.get(key)
            if isinstance(value, list):
                return value

        # Checkov can nest by check type.
        collected: List[Dict[str, Any]] = []
        if isinstance(results, dict):
            for value in results.values():
                if isinstance(value, dict):
                    failed = value.get("failed_checks") or []
                    if isinstance(failed, list):
                        collected.extend(item for item in failed if isinstance(item, dict))
        if collected:
            return collected

        raise MalformedInputError(
            "Checkov payload missing results.failed_checks",
            tool=self.tool_key,
        )

    def normalize_item(
        self,
        item: Dict[str, Any],
        context: NormalizationContext,
    ) -> SecurityFindingObject:
        check_id = item.get("check_id") or item.get("checkId") or item.get("id")
        if not check_id:
            self.require_fields(item, ["check_id"])

        title = str(item.get("check_name") or item.get("checkName") or check_id)
        severity = map_severity(item.get("severity") or item.get("Severity") or "medium")
        file_path = item.get("file_path") or item.get("filePath") or item.get("repo_file_path") or ""
        resource = item.get("resource") or item.get("resource_address") or ""
        description = str(
            item.get("description")
            or item.get("guideline")
            or f"Checkov check {check_id} failed on {resource or file_path or 'resource'}."
        )

        evidence = self.build_evidence(
            context=context,
            summary=f"Checkov {check_id} failed resource={resource} file={file_path}",
            item=item,
            confidence=0.82,
        )

        return SecurityFindingObject(
            tenant_id=context.tenant_id,
            asset_id=context.asset_id,
            source_tool=self.source_tool,
            finding_type=FindingType.MISCONFIGURATION,
            severity=severity,
            cvss_score=clamp_cvss(None, severity),
            confidence_score=0.8,
            evidence=[evidence],
            title=title[:512],
            description=description[:20000],
            metadata=self.base_metadata(
                context,
                rule_id=str(check_id),
                extra_labels={
                    k: str(v)[:512]
                    for k, v in {"file_path": file_path, "resource": resource}.items()
                    if v
                },
            ),
        )
