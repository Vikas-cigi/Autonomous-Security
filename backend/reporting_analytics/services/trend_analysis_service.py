"""Historical / time-series trend analysis from snapshot series."""

from __future__ import annotations

from typing import List, Optional

from reporting_analytics.domain.enums import TrendDirection
from reporting_analytics.domain.inputs import (
    HistoricalSeriesInput,
    PlatformAnalyticsInput,
)
from reporting_analytics.domain.models import (
    Metric,
    RemediationTrend,
    RiskTrend,
    TimeSeriesMetric,
    TrendAnalysis,
    TrustTrend,
)


class TrendAnalysisService:
    """Analyze caller-provided series; never invents or recalculates source scores."""

    def analyze_series(self, series: HistoricalSeriesInput) -> TrendAnalysis:
        values = [p.value for p in series.points]
        timestamps = [p.timestamp for p in series.points]
        if not values:
            return TrendAnalysis(
                name=series.name,
                direction=TrendDirection.UNKNOWN,
                change_ratio=0.0,
                current_value=0.0,
                previous_value=None,
                explanation=f"No data points for {series.name}.",
                series=TimeSeriesMetric(name=series.name),
            )
        current = values[-1]
        previous = values[-2] if len(values) > 1 else None
        direction, change = self._direction(current, previous)
        ts = TimeSeriesMetric(
            name=series.name,
            timestamps=timestamps,
            values=values,
            points=[
                Metric(name=series.name, value=v, metadata={"index": str(i)})
                for i, v in enumerate(values)
            ],
        )
        return TrendAnalysis(
            name=series.name,
            direction=direction,
            change_ratio=change,
            current_value=current,
            previous_value=previous,
            explanation=(
                f"{series.name}: {direction.value} "
                f"(change_ratio={change:.3f}, current={current})."
            ),
            series=ts,
        )

    def analyze_all(self, snapshot: PlatformAnalyticsInput) -> List[TrendAnalysis]:
        trends = [self.analyze_series(s) for s in snapshot.historical_series]
        # Derived named trends from period averages when series absent
        if snapshot.risk.pre_period_average_risk is not None:
            trends.append(
                RiskTrend(
                    name="risk",
                    direction=self._direction(
                        snapshot.risk.post_period_average_risk
                        or snapshot.risk.average_risk,
                        snapshot.risk.pre_period_average_risk,
                    )[0],
                    change_ratio=self._direction(
                        snapshot.risk.post_period_average_risk
                        or snapshot.risk.average_risk,
                        snapshot.risk.pre_period_average_risk,
                    )[1],
                    current_value=snapshot.risk.post_period_average_risk
                    or snapshot.risk.average_risk,
                    previous_value=snapshot.risk.pre_period_average_risk,
                    explanation="Risk trend from provided period averages.",
                )
            )
        trends.append(
            TrustTrend(
                name="trust",
                direction=TrendDirection.FLAT,
                change_ratio=0.0,
                current_value=snapshot.trust.average_trust,
                previous_value=None,
                explanation="Trust distribution snapshot (no recalculation).",
            )
        )
        trends.append(
            RemediationTrend(
                name="remediation_mttr",
                direction=TrendDirection.UNKNOWN,
                change_ratio=0.0,
                current_value=snapshot.remediation.mean_time_to_remediate_hours,
                previous_value=None,
                explanation="MTTR from remediation metrics snapshot.",
            )
        )
        return trends

    @staticmethod
    def _direction(
        current: float, previous: Optional[float]
    ) -> tuple[TrendDirection, float]:
        if previous is None:
            return TrendDirection.UNKNOWN, 0.0
        if abs(previous) < 1e-9:
            change = 0.0 if abs(current) < 1e-9 else 1.0
        else:
            change = (current - previous) / abs(previous)
        if abs(change) < 1e-9:
            return TrendDirection.FLAT, 0.0
        return (TrendDirection.UP if change > 0 else TrendDirection.DOWN), change
