"""Fixed, deterministic scoring weights for the Trust Scoring Engine."""

from __future__ import annotations

from typing import Dict

from trust_scoring.domain.enums import FactorCategory, TrustLevel


# Component weights must sum to 1.0 for reproducibility.
COMPONENT_WEIGHTS: Dict[FactorCategory, float] = {
    FactorCategory.EVIDENCE_QUALITY: 0.20,
    FactorCategory.SCANNER_CONFIDENCE: 0.15,
    FactorCategory.CROSS_VALIDATION: 0.15,
    FactorCategory.HISTORICAL_RELIABILITY: 0.10,
    FactorCategory.FINDING_CORRELATION: 0.10,
    FactorCategory.ASSET_CONFIDENCE: 0.08,
    FactorCategory.THREAT_INTELLIGENCE: 0.08,
    FactorCategory.IOC_CONFIDENCE: 0.05,
    FactorCategory.DUPLICATE_FINDING: 0.04,
    FactorCategory.CONSISTENCY: 0.03,
    FactorCategory.FINDING_BASELINE: 0.02,
}

# Time-decay is applied as a multiplicative modifier, not a weighted component.
TIME_DECAY_HALF_LIFE_DAYS: float = 90.0
TIME_DECAY_FLOOR: float = 0.55

# Trust level thresholds on the 0–100 overall score.
TRUST_LEVEL_THRESHOLDS: tuple[tuple[float, TrustLevel], ...] = (
    (90.0, TrustLevel.VERY_HIGH),
    (75.0, TrustLevel.HIGH),
    (50.0, TrustLevel.MEDIUM),
    (25.0, TrustLevel.LOW),
    (0.0, TrustLevel.VERY_LOW),
)


def trust_level_for_score(score: float) -> TrustLevel:
    """Map a 0–100 score to a TrustLevel (deterministic)."""

    clamped = max(0.0, min(100.0, score))
    for threshold, level in TRUST_LEVEL_THRESHOLDS:
        if clamped >= threshold:
            return level
    return TrustLevel.VERY_LOW


def assert_weights_sum() -> None:
    """Internal invariant — weights must sum to 1.0 within floating tolerance."""

    total = sum(COMPONENT_WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        raise RuntimeError(f"COMPONENT_WEIGHTS must sum to 1.0, got {total}")


assert_weights_sum()
