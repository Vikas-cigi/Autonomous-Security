"""Nuclei JSONL / JSON array normalizer."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from models.enums import FindingType, SourceTool
from models.security_finding import SecurityFindingObject
from normalization.base_normalizer import BaseNormalizer
from normalization.context import NormalizationContext
from normalization.exceptions import MalformedInputError
from normalization.mapping import clamp_cvss, map_severity


class NucleiNormalizer(BaseNormalizer):
    """
    Normalize Nuclei scan results.

    Accepts:
        - list of result objects
        - ``{\"results\": [...]}`` / ``{\"findings\": [...]}``
        - newline-delimited JSON string
    """

    @property
    def tool_key(self) -> str:
        return "nuclei"

    @property
    def source_tool(self) -> SourceTool:
        return SourceTool.NUCLEI

    def extract_items(self, raw_payload: Any) -> Sequence[Dict[str, Any]]:
        payload = raw_payload
        if isinstance(payload, str):
            payload = self._parse_jsonl_or_json(payload)

        if isinstance(payload, dict):
            for key in ("results", "findings", "matches", "data"):
                if key in payload and isinstance(payload[key], list):
                    payload = payload[key]
                    break
            else:
                if "template-id" in payload or "templateID" in payload or "info" in payload:
                    payload = [payload]
                else:
                    raise MalformedInputError(
                        "Nuclei payload must be a list or contain results/findings",
                        tool=self.tool_key,
                    )

        if not isinstance(payload, list):
            raise MalformedInputError(
                "Nuclei payload must resolve to a list of result objects",
                tool=self.tool_key,
            )

        return payload

    def normalize_item(
        self,
        item: Dict[str, Any],
        context: NormalizationContext,
    ) -> SecurityFindingObject:
        info = item.get("info") if isinstance(item.get("info"), dict) else {}
        template_id = (
            item.get("template-id")
            or item.get("templateID")
            or item.get("template_id")
            or info.get("name")
        )
        if not template_id:
            self.require_fields(item, ["template-id"])

        name = str(info.get("name") or template_id)
        severity = map_severity(info.get("severity") or item.get("severity"))
        description = str(
            info.get("description")
            or item.get("matcher-name")
            or f"Nuclei template {template_id} matched."
        )
        host = item.get("host") or item.get("matched-at") or item.get("matched_at") or ""
        summary = f"Nuclei matched {template_id} on {host}".strip()

        cves = self._extract_cves(info)
        cwes = [str(x) for x in info.get("classification", {}).get("cwe-id", []) or []]
        if isinstance(info.get("classification"), dict):
            raw_cwe = info["classification"].get("cwe-id") or info["classification"].get(
                "cwe_id"
            )
            if isinstance(raw_cwe, str):
                cwes = [raw_cwe]
            elif isinstance(raw_cwe, list):
                cwes = [str(x) for x in raw_cwe]

        evidence = self.build_evidence(
            context=context,
            summary=summary or name,
            item=item,
            confidence=0.85,
        )

        finding_type = FindingType.EXPOSURE
        tags = info.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        tag_set = {str(t).lower() for t in tags}
        if "cve" in tag_set or cves:
            finding_type = FindingType.VULNERABILITY
        elif "misconfig" in tag_set or "misconfiguration" in tag_set:
            finding_type = FindingType.MISCONFIGURATION

        # Critical findings require evidence — always attached above.
        return SecurityFindingObject(
            tenant_id=context.tenant_id,
            asset_id=context.asset_id,
            source_tool=self.source_tool,
            finding_type=finding_type,
            severity=severity,
            cvss_score=clamp_cvss(info.get("classification", {}).get("cvss-score"), severity)
            if isinstance(info.get("classification"), dict)
            else clamp_cvss(None, severity),
            confidence_score=0.8,
            evidence=[evidence],
            title=name[:512],
            description=description[:20000],
            cve_ids=cves,
            cwe_ids=cwes,
            metadata=self.base_metadata(
                context,
                template_id=str(template_id),
                extra_labels={"host": str(host)[:512]} if host else None,
            ),
        )

    def _extract_cves(self, info: Dict[str, Any]) -> List[str]:
        classification = info.get("classification") if isinstance(info.get("classification"), dict) else {}
        raw = classification.get("cve-id") or classification.get("cve_id") or info.get("cve") or []
        if isinstance(raw, str):
            raw = [raw]
        return [str(item).upper() for item in raw if str(item).upper().startswith("CVE-")]

    def _parse_jsonl_or_json(self, text: str) -> Any:
        text = text.strip()
        if not text:
            raise MalformedInputError("Empty Nuclei payload", tool=self.tool_key)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            items: List[Dict[str, Any]] = []
            for line_no, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise MalformedInputError(
                        f"Invalid Nuclei JSONL at line {line_no}",
                        tool=self.tool_key,
                        details=str(exc),
                    ) from exc
                if not isinstance(obj, dict):
                    raise MalformedInputError(
                        f"Nuclei JSONL line {line_no} is not an object",
                        tool=self.tool_key,
                    )
                items.append(obj)
            if not items:
                raise MalformedInputError("Nuclei JSONL contained no objects", tool=self.tool_key)
            return items
