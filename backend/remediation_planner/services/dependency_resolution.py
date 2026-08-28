"""DependencyResolutionService — build acyclic step dependency graph."""

from __future__ import annotations

from typing import List

from remediation_planner.domain.enums import DependencyType, StepKind
from remediation_planner.domain.models import (
    DependencyEdge,
    DependencyGraph,
    RemediationStep,
)


class DependencyResolutionService:
    """Derive REQUIRES edges from sequential step order (deterministic)."""

    def resolve(self, steps: List[RemediationStep]) -> DependencyGraph:
        ordered = sorted(steps, key=lambda s: s.sequence)
        edges: List[DependencyEdge] = []
        for prev, curr in zip(ordered, ordered[1:]):
            # Validation depends on prior remediation/mitigation.
            if curr.kind == StepKind.VALIDATION and prev.kind in {
                StepKind.REMEDIATION,
                StepKind.MITIGATION,
                StepKind.PREREQUISITE,
            }:
                edges.append(
                    DependencyEdge(
                        from_step_id=prev.id,
                        to_step_id=curr.id,
                        dependency_type=DependencyType.REQUIRES,
                        rationale=f"Validation requires completion of '{prev.action}'.",
                    )
                )
            elif curr.kind in {
                StepKind.REMEDIATION,
                StepKind.MITIGATION,
            } and prev.kind == StepKind.PREREQUISITE:
                edges.append(
                    DependencyEdge(
                        from_step_id=prev.id,
                        to_step_id=curr.id,
                        dependency_type=DependencyType.REQUIRES,
                        rationale=f"Remediation requires prerequisite '{prev.action}'.",
                    )
                )
            else:
                edges.append(
                    DependencyEdge(
                        from_step_id=prev.id,
                        to_step_id=curr.id,
                        dependency_type=DependencyType.REQUIRES,
                        rationale="Sequential execution order.",
                    )
                )

        graph = DependencyGraph(
            edges=edges,
            topological_order=[s.id for s in ordered],
        )
        graph.assert_acyclic()
        return graph
