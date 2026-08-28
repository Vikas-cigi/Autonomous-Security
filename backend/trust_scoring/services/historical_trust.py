"""Historical reliability scoring — deterministic, no I/O."""

from __future__ import annotations

from typing import Optional

from trust_scoring.domain.enums import FactorCategory, FactorPolarity
from trust_scoring.domain.inputs import HistoricalSignalInput
from trust_scoring.domain.models import ConfidenceFactor, HistoricalReliability
from trust_scoring.domain.weights import COMPONENT_WEIGHTS


class HistoricalTrustService:
    """
    Score historical reliability of similar findings and scanner accuracy.

    When sample size is insufficient, returns a neutral baseline so the
    overall trust score remains reproducible and conservative.
    """

    ALGORITHM_VERSION = "1.0.0"
    MIN_SAMPLE_SIZE = 5

    def assess(
        self,
        signal: Optional[HistoricalSignalInput],
    ) -> HistoricalReliability:
        if signal is None or signal.sample_size < self.MIN_SAMPLE_SIZE:
            sample = signal.sample_size if signal else 0
            return HistoricalReliability(
                score=0.50,
                sample_size=sample,
                true_positive_rate=signal.prior_true_positive_rate if signal else None,
                false_positive_rate=signal.prior_false_positive_rate if signal else None,
                scanner_accuracy=signal.scanner_historical_accuracy if signal else None,
                explanation=(
                    f"Insufficient historical sample (n={sample}; "
                    f"min={self.MIN_SAMPLE_SIZE}); using neutral reliability baseline."
                ),
            )

        tp = signal.prior_true_positive_rate
        fp = signal.prior_false_positive_rate
        scanner_acc = signal.scanner_historical_accuracy

        components: list[float] = []
        if tp is not None:
            components.append(tp)
        if fp is not None:
            components.append(1.0 - fp)
        if scanner_acc is not None:
            components.append(scanner_acc)

        if not components:
            base = 0.50
        else:
            base = sum(components) / len(components)

        # Larger samples slightly boost confidence toward the observed rate.
        sample_boost = min(0.10, (signal.sample_size - self.MIN_SAMPLE_SIZE) / 200.0)
        # Recency: older similar findings slightly reduce reliability signal.
        recency = 1.0
        if signal.days_since_last_similar is not None:
            recency = max(0.7, 1.0 - (signal.days_since_last_similar / 365.0) * 0.3)

        score = round(max(0.0, min(1.0, base * recency + sample_boost * (base - 0.5))), 4)
        return HistoricalReliability(
            score=score,
            sample_size=signal.sample_size,
            true_positive_rate=tp,
            false_positive_rate=fp,
            scanner_accuracy=scanner_acc,
            explanation=(
                f"Historical reliability from n={signal.sample_size}: "
                f"TP={tp if tp is not None else 'n/a'}, "
                f"FP={fp if fp is not None else 'n/a'}, "
                f"scanner accuracy={scanner_acc if scanner_acc is not None else 'n/a'}."
            ),
        )

    def to_factor(self, reliability: HistoricalReliability) -> ConfidenceFactor:
        weight = COMPONENT_WEIGHTS[FactorCategory.HISTORICAL_RELIABILITY]
        polarity = (
            FactorPolarity.SUPPORTING
            if reliability.score >= 0.55
            else FactorPolarity.NEGATIVE
            if reliability.score < 0.45
            else FactorPolarity.NEUTRAL
        )
        return ConfidenceFactor(
            category=FactorCategory.HISTORICAL_RELIABILITY,
            polarity=polarity,
            label="Historical reliability",
            description=reliability.explanation,
            raw_score=reliability.score,
            weight=weight,
            weighted_contribution=round(reliability.score * weight, 6),
        )
