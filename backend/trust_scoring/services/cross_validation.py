"""Multi-scanner confidence and cross-validation — deterministic, no I/O."""

from __future__ import annotations

from typing import List, Set, Tuple

from models.enums import SourceTool
from trust_scoring.domain.enums import (
    CrossValidationStatus,
    FactorCategory,
    FactorPolarity,
)
from trust_scoring.domain.inputs import ScannerObservationInput
from trust_scoring.domain.models import (
    ConfidenceFactor,
    CrossValidationResult,
    ScannerConfidence,
)
from trust_scoring.domain.weights import COMPONENT_WEIGHTS


class CrossValidationService:
    """
    Evaluate agreement across scanner observations.

    Deterministic rules:
    - 0 observations → inconclusive / single-source fallback handled by caller
    - 1 unique tool → SINGLE_SOURCE
    - ≥2 tools with high agreement → CONFIRMED / PARTIAL
    - Severity or signature conflicts → CONFLICTING
    """

    ALGORITHM_VERSION = "1.0.0"

    def assess_scanner_confidence(
        self,
        observations: List[ScannerObservationInput],
        *,
        primary_tool: SourceTool,
    ) -> ScannerConfidence:
        if not observations:
            return ScannerConfidence(
                score=0.35,
                primary_tool=primary_tool,
                observation_count=0,
                unique_tools=[],
                average_scanner_confidence=0.0,
                severity_agreement_rate=1.0,
                explanation=(
                    "No scanner observations provided; using conservative "
                    f"baseline for primary tool {primary_tool.value}."
                ),
            )

        tools = list({o.source_tool for o in observations})
        avg_conf = sum(o.scanner_confidence for o in observations) / len(observations)
        severity_agree = sum(1 for o in observations if o.severity_agrees) / len(
            observations
        )
        avg_similarity = sum(o.title_similarity for o in observations) / len(
            observations
        )
        multi = min(1.0, (len(tools) - 1) / 2.0) if len(tools) > 1 else 0.0

        score = round(
            max(
                0.0,
                min(
                    1.0,
                    0.45 * avg_conf
                    + 0.25 * severity_agree
                    + 0.20 * avg_similarity
                    + 0.10 * (0.4 + 0.6 * multi),
                ),
            ),
            4,
        )
        return ScannerConfidence(
            score=score,
            primary_tool=primary_tool,
            observation_count=len(observations),
            unique_tools=sorted(tools, key=lambda t: t.value),
            average_scanner_confidence=round(avg_conf, 4),
            severity_agreement_rate=round(severity_agree, 4),
            explanation=(
                f"{len(observations)} observation(s) from {len(tools)} tool(s); "
                f"avg scanner confidence={avg_conf:.2f}, "
                f"severity agreement={severity_agree:.0%}."
            ),
        )

    def cross_validate(
        self,
        observations: List[ScannerObservationInput],
    ) -> CrossValidationResult:
        if not observations:
            return CrossValidationResult(
                status=CrossValidationStatus.INCONCLUSIVE,
                score=0.30,
                confirming_tools=[],
                conflicting_tools=[],
                agreement_ratio=0.0,
                explanation="No observations available for cross-validation.",
            )

        tools: Set[SourceTool] = {o.source_tool for o in observations}
        if len(tools) == 1:
            only = next(iter(tools))
            conf = observations[0].scanner_confidence
            return CrossValidationResult(
                status=CrossValidationStatus.SINGLE_SOURCE,
                score=round(0.40 + 0.25 * conf, 4),
                confirming_tools=[only],
                conflicting_tools=[],
                agreement_ratio=1.0,
                explanation=f"Single-source finding from {only.value}; no independent confirmation.",
            )

        confirming, conflicting = self._partition(observations)
        agreement = len(confirming) / len(tools) if tools else 0.0

        if conflicting and agreement < 0.5:
            status = CrossValidationStatus.CONFLICTING
            score = round(0.20 + 0.20 * agreement, 4)
        elif agreement >= 0.75 and not conflicting:
            status = CrossValidationStatus.CONFIRMED
            score = round(0.75 + 0.25 * agreement, 4)
        elif agreement >= 0.5:
            status = CrossValidationStatus.PARTIAL
            score = round(0.55 + 0.25 * agreement, 4)
        else:
            status = CrossValidationStatus.INCONCLUSIVE
            score = round(0.35 + 0.20 * agreement, 4)

        return CrossValidationResult(
            status=status,
            score=min(1.0, score),
            confirming_tools=sorted(confirming, key=lambda t: t.value),
            conflicting_tools=sorted(conflicting, key=lambda t: t.value),
            agreement_ratio=round(agreement, 4),
            explanation=(
                f"Cross-validation {status.value}: {len(confirming)} confirming / "
                f"{len(conflicting)} conflicting tool(s); agreement={agreement:.0%}."
            ),
        )

    def scanner_factor(self, scanner: ScannerConfidence) -> ConfidenceFactor:
        weight = COMPONENT_WEIGHTS[FactorCategory.SCANNER_CONFIDENCE]
        polarity = (
            FactorPolarity.SUPPORTING
            if scanner.score >= 0.5
            else FactorPolarity.NEGATIVE
        )
        return ConfidenceFactor(
            category=FactorCategory.SCANNER_CONFIDENCE,
            polarity=polarity,
            label="Scanner confidence",
            description=scanner.explanation,
            raw_score=scanner.score,
            weight=weight,
            weighted_contribution=round(scanner.score * weight, 6),
        )

    def cross_validation_factor(
        self,
        result: CrossValidationResult,
    ) -> ConfidenceFactor:
        weight = COMPONENT_WEIGHTS[FactorCategory.CROSS_VALIDATION]
        if result.status == CrossValidationStatus.CONFLICTING:
            polarity = FactorPolarity.NEGATIVE
        elif result.status in (
            CrossValidationStatus.CONFIRMED,
            CrossValidationStatus.PARTIAL,
        ):
            polarity = FactorPolarity.SUPPORTING
        else:
            polarity = FactorPolarity.NEUTRAL
        return ConfidenceFactor(
            category=FactorCategory.CROSS_VALIDATION,
            polarity=polarity,
            label=f"Cross-validation: {result.status.value}",
            description=result.explanation,
            raw_score=result.score,
            weight=weight,
            weighted_contribution=round(result.score * weight, 6),
        )

    @staticmethod
    def _partition(
        observations: List[ScannerObservationInput],
    ) -> Tuple[List[SourceTool], List[SourceTool]]:
        confirming: List[SourceTool] = []
        conflicting: List[SourceTool] = []
        seen: Set[SourceTool] = set()
        for obs in observations:
            if obs.source_tool in seen:
                continue
            seen.add(obs.source_tool)
            if obs.severity_agrees and obs.title_similarity >= 0.6:
                confirming.append(obs.source_tool)
            else:
                conflicting.append(obs.source_tool)
        return confirming, conflicting
