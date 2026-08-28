"""DecisionContextAssembler — aggregate intelligence snapshots (no scoring logic)."""

from __future__ import annotations

from decision_service.domain.inputs import DecisionRequest
from decision_service.domain.models import DecisionContext, DecisionReasoning


class DecisionContextAssembler:
    """
    Assemble DecisionContext from caller-provided snapshots.

    Does not re-implement Trust / Risk / TI / Evidence scoring. Pure aggregation
    and operator-message formatting for downstream AI / deterministic advisors.
    """

    def assemble(self, request: DecisionRequest) -> DecisionContext:
        finding = request.finding
        trust = request.trust
        risk = request.risk
        ti = request.threat_intel
        asset = request.asset
        evidence = request.evidence

        evidence_ids = list(evidence.evidence_ids) if evidence else []
        evidence_count = evidence.evidence_count if evidence else 0
        highlights = list(evidence.highlights) if evidence else []

        reasoning = DecisionReasoning(
            risk_summary=(
                risk.explanation
                or (
                    f"Enterprise risk={risk.enterprise_risk_score:.2f}/100 "
                    f"({risk.risk_level or 'unknown'}); "
                    f"priority={risk.priority or 'n/a'}; "
                    f"SLA={risk.recommended_sla or 'n/a'}."
                )
            ),
            trust_summary=(
                trust.explanation
                or (
                    f"Trust score={trust.trust_score:.2f}/100 "
                    f"({trust.trust_level or 'unknown'}); "
                    f"recommendation_confidence={trust.recommendation_confidence or 'n/a'}."
                )
            ),
            threat_summary=self._threat_summary(ti),
            policy_summary=(
                f"Policy version={request.policy.policy_version}; "
                f"action_class={request.policy.action_class.value}; "
                f"scope={request.policy.scope.value}."
            ),
            evidence_summary=(
                f"Evidence count={evidence_count}; "
                f"validated={evidence.validated_count if evidence else 0}; "
                f"avg_confidence="
                f"{(evidence.average_confidence if evidence else 0.0):.2f}."
                if evidence_count or evidence
                else "No evidence attached."
            ),
            key_signals=self._key_signals(request, highlights),
        )

        operator_message = self._operator_message(request, reasoning)

        return DecisionContext(
            tenant_id=finding.tenant_id,
            finding_id=finding.finding_id,
            asset_id=finding.asset_id,
            finding_title=finding.title,
            finding_severity=finding.severity,
            trust_score=trust.trust_score,
            trust_level=trust.trust_level,
            enterprise_risk_score=risk.enterprise_risk_score,
            risk_level=risk.risk_level,
            risk_priority=risk.priority,
            recommended_sla=risk.recommended_sla,
            internet_facing=bool(asset.internet_facing) if asset else False,
            customer_facing=bool(asset.customer_facing) if asset else False,
            in_cisa_kev=bool(ti.in_cisa_kev) if ti else False,
            actively_exploited=bool(ti.actively_exploited) if ti else False,
            evidence_count=evidence_count,
            evidence_ids=evidence_ids,
            compliance_tags=list(asset.compliance_tags) if asset else [],
            cve_ids=list(finding.cve_ids),
            reasoning=reasoning,
            operator_message=operator_message,
            metadata={
                "assembler": self.__class__.__name__,
                "invoke_ai": request.invoke_ai,
                "asset_environment": asset.environment if asset else None,
            },
        )

    @staticmethod
    def _threat_summary(ti) -> str:
        if ti is None or not ti.enrichment_present:
            return "No threat intelligence enrichment present."
        return (
            ti.summary
            or (
                f"TI enrichment present; KEV={ti.in_cisa_kev}; "
                f"actively_exploited={ti.actively_exploited}; "
                f"EPSS={ti.epss_score if ti.epss_score is not None else 'n/a'}; "
                f"MITRE techniques={ti.mitre_technique_count}; "
                f"IOC matches={ti.ioc_match_count}."
            )
        )

    @staticmethod
    def _key_signals(request: DecisionRequest, highlights: list[str]) -> list[str]:
        signals: list[str] = []
        risk = request.risk
        trust = request.trust
        signals.append(f"risk_score={risk.enterprise_risk_score:.2f}")
        signals.append(f"trust_score={trust.trust_score:.2f}")
        if risk.risk_level:
            signals.append(f"risk_level={risk.risk_level}")
        if request.threat_intel and request.threat_intel.in_cisa_kev:
            signals.append("cisa_kev=true")
        if request.threat_intel and request.threat_intel.actively_exploited:
            signals.append("actively_exploited=true")
        if request.asset and request.asset.internet_facing:
            signals.append("internet_facing=true")
        signals.extend(highlights[:8])
        return signals

    @staticmethod
    def _operator_message(request: DecisionRequest, reasoning: DecisionReasoning) -> str:
        finding = request.finding
        parts = [
            "Prepare a cybersecurity decision for the following finding.",
            f"Finding ID: {finding.finding_id}",
            f"Title: {finding.title or 'n/a'}",
            f"Severity: {finding.severity or 'n/a'}",
            f"CVEs: {', '.join(finding.cve_ids) if finding.cve_ids else 'none'}",
            "",
            "Risk summary:",
            reasoning.risk_summary,
            "",
            "Trust summary:",
            reasoning.trust_summary,
            "",
            "Threat summary:",
            reasoning.threat_summary,
            "",
            "Evidence summary:",
            reasoning.evidence_summary,
            "",
            "Key signals: " + ", ".join(reasoning.key_signals),
            "",
            "Respond with JSON only using keys: decision_type, confidence, "
            "recommended_action, next_step, business_justification, "
            "technical_justification, explanation.",
            "decision_type must be one of: remediate, ignore, escalate, "
            "investigate, monitor.",
        ]
        return "\n".join(parts)
