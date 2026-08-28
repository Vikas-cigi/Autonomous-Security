"""PlanGenerationService — deterministic step / task / validation generation."""

from __future__ import annotations

from typing import List, Tuple

from remediation_planner.domain.enums import ExecutionType, StepKind
from remediation_planner.domain.inputs import RemediationPlanRequest
from remediation_planner.domain.models import (
    ExecutionTask,
    Prerequisite,
    RemediationStep,
    ValidationCheck,
)


class PlanGenerationService:
    """
    Generate ordered remediation steps, execution tasks, and validation checks.

    No AI. No infrastructure mutation. Pure deterministic templates.
    """

    def generate(
        self,
        request: RemediationPlanRequest,
        execution_type: ExecutionType,
    ) -> Tuple[List[RemediationStep], List[ExecutionTask], List[ValidationCheck]]:
        target = self._target(request)
        steps = self._steps_for(execution_type, request, target)
        tasks = self._tasks_from_steps(steps, execution_type)
        validations = self._validations(steps, execution_type, request)
        return steps, tasks, validations

    def _target(self, request: RemediationPlanRequest) -> str:
        if request.asset and request.asset.hostname:
            return request.asset.hostname
        return f"asset:{request.finding.asset_id}"

    def _steps_for(
        self,
        execution_type: ExecutionType,
        request: RemediationPlanRequest,
        target: str,
    ) -> List[RemediationStep]:
        builders = {
            ExecutionType.PATCH: self._patch_steps,
            ExecutionType.PACKAGE_UPGRADE: self._package_steps,
            ExecutionType.CONFIGURATION_CHANGE: self._config_steps,
            ExecutionType.SECRET_ROTATION: self._secret_steps,
            ExecutionType.FIREWALL_UPDATE: self._firewall_steps,
            ExecutionType.IAM_POLICY_CHANGE: self._iam_steps,
            ExecutionType.NETWORK_ISOLATION: self._isolation_steps,
            ExecutionType.CONTAINER_UPDATE: self._container_steps,
            ExecutionType.MANUAL_INVESTIGATION: self._manual_steps,
        }
        return builders[execution_type](request, target)

    def _patch_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        cve = ",".join(request.finding.cve_ids) or "n/a"
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.PATCH,
                "Verify backup / snapshot exists",
                target,
                "Confirm restore point before patching.",
                duration=120,
                destructive=False,
                prereqs=[
                    Prerequisite(
                        description="Backup or VM snapshot verified",
                        check_type="backup_verified",
                    )
                ],
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.PATCH,
                f"Apply vendor patch for {cve}",
                target,
                "Install security patch addressing the finding.",
                duration=900,
                destructive=True,
                params={"cve_ids": cve},
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.PATCH,
                "Re-scan / verify patch applied",
                target,
                "Confirm vulnerability signature cleared.",
                duration=300,
                destructive=False,
            ),
        ]

    def _package_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        pkg = request.finding.package_name or "affected-package"
        fixed = request.finding.fixed_version or "latest-secure"
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.PACKAGE_UPGRADE,
                "Inventory current package version",
                target,
                f"Record current version of {pkg}.",
                duration=60,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.PACKAGE_UPGRADE,
                f"Upgrade {pkg} to {fixed}",
                target,
                "Upgrade package to fixed version.",
                duration=600,
                destructive=True,
                params={"package": pkg, "fixed_version": fixed},
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.PACKAGE_UPGRADE,
                "Verify package version and service health",
                target,
                "Confirm package version and dependent services healthy.",
                duration=240,
            ),
        ]

    def _config_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.CONFIGURATION_CHANGE,
                "Export current configuration",
                target,
                "Capture baseline config for rollback.",
                duration=90,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.CONFIGURATION_CHANGE,
                "Apply hardened configuration change",
                target,
                request.decision.reason[:500],
                duration=300,
                destructive=True,
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.CONFIGURATION_CHANGE,
                "Validate configuration and connectivity",
                target,
                "Confirm intended config and no unintended outage.",
                duration=180,
            ),
        ]

    def _secret_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.SECRET_ROTATION,
                "Identify dependent services using credential",
                target,
                "Map consumers before rotation.",
                duration=180,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.SECRET_ROTATION,
                "Rotate secret / credential",
                target,
                "Issue new secret and revoke old material.",
                duration=300,
                destructive=True,
                requires_approval=True,
            ),
            self._step(
                3,
                StepKind.REMEDIATION,
                ExecutionType.SECRET_ROTATION,
                "Redeploy consumers with new secret",
                target,
                "Update dependent workloads.",
                duration=600,
                destructive=True,
            ),
            self._step(
                4,
                StepKind.VALIDATION,
                ExecutionType.SECRET_ROTATION,
                "Verify auth success with new secret",
                target,
                "Confirm services authenticate successfully.",
                duration=180,
            ),
        ]

    def _firewall_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.FIREWALL_UPDATE,
                "Snapshot firewall / security-group rules",
                target,
                "Preserve current allow/deny set.",
                duration=60,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.FIREWALL_UPDATE,
                "Apply firewall / security-group update",
                target,
                "Tighten network controls for the finding.",
                duration=180,
                destructive=True,
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.FIREWALL_UPDATE,
                "Verify blocked/allowed traffic paths",
                target,
                "Confirm intended connectivity matrix.",
                duration=120,
            ),
        ]

    def _iam_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.IAM_POLICY_CHANGE,
                "Export current IAM policy document",
                target,
                "Baseline IAM policy for rollback.",
                duration=60,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.IAM_POLICY_CHANGE,
                "Apply least-privilege IAM policy change",
                target,
                "Reduce excessive permissions.",
                duration=240,
                destructive=True,
                requires_approval=True,
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.IAM_POLICY_CHANGE,
                "Verify required access still works",
                target,
                "Confirm break-glass and app access paths.",
                duration=180,
            ),
        ]

    def _isolation_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.MITIGATION,
                ExecutionType.NETWORK_ISOLATION,
                "Quarantine / isolate asset network path",
                target,
                "Contain actively exploited or KEV-class risk.",
                duration=120,
                destructive=True,
                requires_approval=True,
            ),
            self._step(
                2,
                StepKind.NOTIFY,
                ExecutionType.NETWORK_ISOLATION,
                "Notify owners and incident channel",
                target,
                "Communicate isolation and next steps.",
                duration=60,
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.NETWORK_ISOLATION,
                "Verify isolation controls effective",
                target,
                "Confirm asset cannot reach untrusted networks.",
                duration=120,
            ),
        ]

    def _container_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.CONTAINER_UPDATE,
                "Identify vulnerable image digest",
                target,
                "Pin current image for rollback.",
                duration=90,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.CONTAINER_UPDATE,
                "Deploy patched container image",
                target,
                "Roll workload to fixed image tag/digest.",
                duration=600,
                destructive=True,
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.CONTAINER_UPDATE,
                "Verify rollout health and image digest",
                target,
                "Confirm pods/tasks healthy on new image.",
                duration=300,
            ),
        ]

    def _manual_steps(
        self, request: RemediationPlanRequest, target: str
    ) -> List[RemediationStep]:
        return [
            self._step(
                1,
                StepKind.PREREQUISITE,
                ExecutionType.MANUAL_INVESTIGATION,
                "Collect additional evidence",
                target,
                "Gather logs, configs, and corroborating signals.",
                duration=600,
            ),
            self._step(
                2,
                StepKind.REMEDIATION,
                ExecutionType.MANUAL_INVESTIGATION,
                "Analyst investigation playbook",
                target,
                request.decision.reason[:500],
                duration=1800,
            ),
            self._step(
                3,
                StepKind.VALIDATION,
                ExecutionType.MANUAL_INVESTIGATION,
                "Document findings and recommended follow-up",
                target,
                "Record outcome for Decision Service re-evaluation.",
                duration=300,
            ),
        ]

    def _tasks_from_steps(
        self,
        steps: List[RemediationStep],
        execution_type: ExecutionType,
    ) -> List[ExecutionTask]:
        tasks: List[ExecutionTask] = []
        for step in steps:
            if step.kind == StepKind.NOTIFY:
                continue
            tasks.append(
                ExecutionTask(
                    name=step.action,
                    execution_type=execution_type,
                    step_ids=[step.id],
                    sequence=step.sequence,
                    estimated_duration_seconds=step.estimated_duration_seconds,
                    is_destructive=step.is_destructive,
                    description=step.description,
                )
            )
        # Re-number task sequences contiguously
        for idx, task in enumerate(sorted(tasks, key=lambda t: t.sequence), start=1):
            task.sequence = idx
        return sorted(tasks, key=lambda t: t.sequence)

    def _validations(
        self,
        steps: List[RemediationStep],
        execution_type: ExecutionType,
        request: RemediationPlanRequest,
    ) -> List[ValidationCheck]:
        checks: List[ValidationCheck] = []
        for step in steps:
            if step.kind != StepKind.VALIDATION:
                continue
            checks.append(
                ValidationCheck(
                    name=step.action,
                    description=step.description,
                    after_step_sequence=step.sequence,
                    success_criteria=(
                        f"Step '{step.action}' reports success for {execution_type.value} "
                        f"on finding {request.finding.finding_id}."
                    ),
                    is_blocking=True,
                )
            )
        if not checks:
            checks.append(
                ValidationCheck(
                    name="Plan completion review",
                    description="Human review that planned outcomes were met.",
                    success_criteria="Analyst attests remediation objectives satisfied.",
                    is_blocking=True,
                )
            )
        return checks

    @staticmethod
    def _step(
        sequence: int,
        kind: StepKind,
        execution_type: ExecutionType,
        action: str,
        target: str,
        description: str,
        *,
        duration: int,
        destructive: bool = False,
        requires_approval: bool = False,
        prereqs: List[Prerequisite] | None = None,
        params: dict | None = None,
    ) -> RemediationStep:
        return RemediationStep(
            sequence=sequence,
            kind=kind,
            execution_type=execution_type,
            action=action,
            target=target,
            description=description,
            timeout_seconds=max(300, duration * 2),
            estimated_duration_seconds=duration,
            is_destructive=destructive,
            requires_approval=requires_approval,
            prerequisites=prereqs or [],
            parameters={k: str(v) for k, v in (params or {}).items()},
        )
