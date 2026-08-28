"""MITRE ATT&CK / CAPEC / CWE mapping helpers."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from threat_intelligence.domain.models import MITRETechnique, ThreatIntelligence
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository


# Lightweight static hints for common techniques (placeholder knowledge base).
_TECHNIQUE_NAMES: dict[str, str] = {
    "T1059": "Command and Scripting Interpreter",
    "T1059.001": "PowerShell",
    "T1190": "Exploit Public-Facing Application",
    "T1055": "Process Injection",
    "T1003": "OS Credential Dumping",
    "T1078": "Valid Accounts",
    "T1027": "Obfuscated Files or Information",
    "T1082": "System Information Discovery",
    "T1047": "Windows Management Instrumentation",
    "T1566": "Phishing",
}


class MITREMappingService:
    """Map and normalize MITRE / CWE / CAPEC identifiers onto enrichment."""

    def __init__(self, repository: Optional[ThreatIntelRepository] = None) -> None:
        self._repo = repository

    def resolve_technique(self, technique_id: str) -> MITRETechnique:
        normalized = technique_id.strip().upper()
        return MITRETechnique(
            technique_id=normalized,
            name=_TECHNIQUE_NAMES.get(normalized),
            url=f"https://attack.mitre.org/techniques/{normalized.replace('.', '/')}/",
        )

    def map_techniques(
        self,
        technique_ids: Sequence[str],
    ) -> List[MITRETechnique]:
        return [self.resolve_technique(t) for t in technique_ids if t.strip()]

    def apply_to_intelligence(
        self,
        intel: ThreatIntelligence,
        *,
        technique_ids: Optional[Iterable[str]] = None,
        cwe_ids: Optional[Iterable[str]] = None,
        capec_ids: Optional[Iterable[str]] = None,
        actor: Optional[str] = None,
        persist: bool = True,
    ) -> ThreatIntelligence:
        if technique_ids:
            by_id = {t.technique_id: t for t in intel.mitre_techniques}
            for tech in self.map_techniques(list(technique_ids)):
                by_id[tech.technique_id] = tech
            intel.mitre_techniques = list(by_id.values())

        if cwe_ids:
            merged = list(intel.cwe_ids)
            for cwe in cwe_ids:
                item = cwe.strip().upper()
                if item and item not in merged:
                    merged.append(item)
            intel.cwe_ids = merged

        if capec_ids:
            merged = list(intel.capec_ids)
            for capec in capec_ids:
                item = capec.strip().upper()
                if item and item not in merged:
                    merged.append(item)
            intel.capec_ids = merged

        if persist and self._repo is not None:
            return self._repo.save_intelligence(
                intel,
                actor=actor,
                change_summary="MITRE/CWE/CAPEC mapping applied",
            )
        return intel
