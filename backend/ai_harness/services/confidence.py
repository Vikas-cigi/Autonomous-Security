"""AIConfidenceService — evaluate output confidence from harness signals."""

from __future__ import annotations

from typing import List, Optional

from ai_harness.domain.enums import ConfidenceBand
from ai_harness.domain.models import (
    AIConfidence,
    AIProviderResult,
    AIValidationResult,
)


class AIConfidenceService:
    """
    Deterministic confidence scoring from validation + provider signals.

    No domain/business cybersecurity logic.
    """

    def evaluate(
        self,
        *,
        text: str,
        validation: Optional[AIValidationResult],
        provider_result: AIProviderResult,
        reflected: bool = False,
    ) -> AIConfidence:
        signals: List[str] = []
        score = 0.55

        if text and text.strip():
            score += 0.10
            signals.append("non_empty_text")
        else:
            score -= 0.35
            signals.append("empty_text")

        if validation is not None:
            if validation.valid:
                score += 0.20
                signals.append("validation_passed")
            else:
                score -= 0.25
                signals.append(f"validation_errors={validation.error_count}")
            if validation.parsed_payload:
                score += 0.05
                signals.append("structured_payload_present")

        if provider_result.success:
            score += 0.05
            signals.append("provider_success")
        else:
            score -= 0.20
            signals.append("provider_failure")

        if provider_result.attempt > 1:
            score -= 0.05 * min(3, provider_result.attempt - 1)
            signals.append(f"retries={provider_result.attempt - 1}")

        if reflected:
            score += 0.05
            signals.append("reflection_applied")

        # Mild length heuristic — very short answers are less reliable for structured tasks.
        if validation and validation.valid is False:
            pass
        elif 0 < len(text.strip()) < 20:
            score -= 0.05
            signals.append("very_short_text")

        score = round(max(0.0, min(1.0, score)), 4)
        band = self._band(score)
        return AIConfidence(
            score=score,
            band=band,
            signals=signals,
            explanation=(
                f"Harness confidence={score:.2f} ({band.value}) from signals: "
                + ", ".join(signals)
            ),
        )

    @staticmethod
    def _band(score: float) -> ConfidenceBand:
        if score >= 0.90:
            return ConfidenceBand.VERY_HIGH
        if score >= 0.75:
            return ConfidenceBand.HIGH
        if score >= 0.50:
            return ConfidenceBand.MEDIUM
        if score >= 0.25:
            return ConfidenceBand.LOW
        return ConfidenceBand.VERY_LOW
