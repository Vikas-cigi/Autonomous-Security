"""
Abstract security tool adapter (Template Method + Strategy).

Lifecycle enforced by ``run()``:

    initialize → authenticate → validate_scope → validate_policy →
    prepare → execute → collect_metadata → parse → build_raw_result → cleanup
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from models.common import utc_now
from models.enums import PolicyVerdict
from policy_engine import PolicyEngine, PolicyInput, ResourceRef
from policy_engine.models import PolicyDecision

from src.adapters.base.adapter_config import AdapterConfig
from src.adapters.base.adapter_exception import (
    AdapterAuthenticationError,
    AdapterConfigurationError,
    AdapterExecutionError,
    AdapterPolicyViolationError,
    AdapterScopeViolationError,
    AdapterTimeoutError,
)
from src.adapters.base.raw_result import RawResult, RawResultStatus
from src.adapters.common.authentication import Authenticator, NoopAuthenticator
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.common.metadata_collector import MetadataCollector
from src.adapters.common.retry import retry_call
from src.adapters.common.scope_validator import ScopeValidator

logger = logging.getLogger(__name__)


class CommandResult:
    """Internal capture of a subprocess invocation."""

    __slots__ = ("exit_code", "stdout", "stderr", "timed_out")

    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        *,
        timed_out: bool = False,
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


class BaseToolAdapter(ABC):
    """
    Hexagonal port for security scanners.

    Concrete adapters implement tool-specific prepare/execute/parse while
    inheriting cross-cutting policy, scope, auth, metrics, and RawResult assembly.
    """

    tool_name: str = "base"

    def __init__(
        self,
        config: AdapterConfig,
        *,
        policy_engine: Optional[PolicyEngine] = None,
        scope_validator: Optional[ScopeValidator] = None,
        authenticator: Optional[Authenticator] = None,
        metadata_collector: Optional[MetadataCollector] = None,
    ) -> None:
        self._config = config
        self._policy_engine = policy_engine or PolicyEngine()
        self._scope_validator = scope_validator or ScopeValidator()
        self._authenticator = authenticator or NoopAuthenticator()
        self._metadata_collector = metadata_collector or MetadataCollector()
        self._context: Optional[AdapterExecutionContext] = None
        self._policy_decision: Optional[PolicyDecision] = None
        self._command: List[str] = []
        self._tool_version: str = "unknown"
        self._started_at: Optional[datetime] = None
        self._command_result: Optional[CommandResult] = None
        self._parsed_output: Any = None
        self._metadata: Dict[str, Any] = {}
        self._warnings: List[str] = []

    def run(self, context: AdapterExecutionContext) -> RawResult:
        """
        Execute the full adapter lifecycle and return ``RawResult`` only.

        Never returns ``SecurityFindingObject``.
        """

        self._context = context
        self._warnings = []
        self._parsed_output = None
        self._command_result = None
        self._policy_decision = None
        self._started_at = utc_now()

        try:
            self.initialize()
            self.authenticate()
            self.validate_scope()
            self.validate_policy()
            self.prepare()
            self._command_result = self._execute_with_retry()
            self._metadata = self.collect_metadata()
            self._parsed_output = self.parse(
                self._command_result.stdout,
                self._command_result.stderr,
                self._command_result.exit_code,
            )
            return self.build_raw_result()
        except AdapterPolicyViolationError as exc:
            return self._failure_result(RawResultStatus.POLICY_DENIED, str(exc))
        except AdapterScopeViolationError as exc:
            return self._failure_result(RawResultStatus.SCOPE_DENIED, str(exc))
        except AdapterAuthenticationError as exc:
            return self._failure_result(RawResultStatus.AUTH_FAILED, str(exc))
        except AdapterTimeoutError as exc:
            return self._failure_result(RawResultStatus.TIMEOUT, str(exc))
        except Exception:
            logger.exception(
                "Adapter run failed tool=%s execution_id=%s",
                self.tool_name,
                context.execution_id,
            )
            raise
        finally:
            self.cleanup()

    def initialize(self) -> None:
        """Validate configuration and resolve binary."""

        if not self._config.enabled:
            raise AdapterConfigurationError(
                f"Adapter '{self.tool_name}' is disabled",
                tool_name=self.tool_name,
            )
        binary = shutil.which(self._config.binary_path) or self._config.binary_path
        self._config = self._config.model_copy(update={"binary_path": binary})
        self._tool_version = self.version()
        logger.info(
            "Adapter initialized tool=%s version=%s binary=%s",
            self.tool_name,
            self._tool_version,
            self._config.binary_path,
        )

    def authenticate(self) -> None:
        """Delegate to injected authenticator strategy."""

        assert self._context is not None
        self._authenticator.authenticate(self._config, self._context)

    def validate_scope(self) -> None:
        """Validate tenant/asset/targets/engagement window."""

        assert self._context is not None
        self._scope_validator.validate(self._context, tool_name=self.tool_name)

    def validate_policy(self) -> None:
        """
        Mandatory PolicyEngine evaluation before execution.

        Only ``ALLOW`` permits the scanner to run. ``ESCALATE`` and ``DENY``
        raise ``AdapterPolicyViolationError`` (never execute without approval).
        """

        assert self._context is not None
        context = self._context
        policy_input = PolicyInput(
            tenant_id=context.tenant_id,
            user=context.user,
            scope=context.scope,
            action_class=context.action_class,
            resource=ResourceRef(
                resource_type="asset",
                resource_id=context.asset_id,
                environment=context.environment,
                labels={"tool": self.tool_name},
            ),
            roles=context.roles,
            attributes={
                "tool_name": self.tool_name,
                "targets": list(context.targets),
                "correlation_id": str(context.correlation_id),
            },
        )
        decision = self._policy_engine.evaluate(policy_input)
        self._policy_decision = decision
        logger.info(
            "Policy decision tool=%s verdict=%s",
            self.tool_name,
            decision.verdict.value,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise AdapterPolicyViolationError(
                f"Policy {decision.verdict.value}: {decision.reason}",
                tool_name=self.tool_name,
                details={
                    "verdict": decision.verdict.value,
                    "decision_id": str(decision.decision_id),
                    "requires_approval": decision.requires_approval,
                },
            )

    def prepare(self) -> None:
        """Build the command line; subclasses usually override."""

        assert self._context is not None
        self._command = self.build_command(self._context)

    def execute(self) -> CommandResult:
        """Run the prepared command once."""

        if not self._command:
            raise AdapterExecutionError(
                "Command not prepared",
                tool_name=self.tool_name,
            )
        return self.run_command(self._command)

    def collect_metadata(self) -> Dict[str, Any]:
        """Collect execution telemetry."""

        assert self._context is not None and self._started_at is not None
        extra: Dict[str, Any] = {}
        if self._policy_decision is not None:
            extra["policy_decision_id"] = str(self._policy_decision.decision_id)
            extra["policy_verdict"] = self._policy_decision.verdict.value
            extra["policy_version"] = self._policy_decision.policy_version
        return self._metadata_collector.collect(
            context=self._context,
            tool_name=self.tool_name,
            tool_version=self._tool_version,
            arguments=self._command,
            started_at=self._started_at,
            completed_at=utc_now(),
            extra=extra,
        )

    @abstractmethod
    def parse(self, stdout: str, stderr: str, exit_code: int) -> Any:
        """Parse vendor output into a JSON-compatible structure (not findings)."""

    def build_raw_result(self) -> RawResult:
        """Assemble the outbound ``RawResult`` contract."""

        assert self._context is not None and self._started_at is not None
        assert self._command_result is not None
        completed = utc_now()
        elapsed_ms = (completed - self._started_at).total_seconds() * 1000.0
        status = self.map_status(self._command_result)
        errors: List[str] = []
        if status != RawResultStatus.SUCCEEDED:
            errors.append(
                self._command_result.stderr.strip()
                or f"Scanner exited with code {self._command_result.exit_code}"
            )
        return RawResult(
            execution_id=self._context.execution_id,
            tenant_id=self._context.tenant_id,
            tool_name=self.tool_name,
            tool_version=self._tool_version,
            execution_time_ms=round(elapsed_ms, 2),
            started_at=self._started_at,
            completed_at=completed,
            status=status,
            exit_code=self._command_result.exit_code,
            stdout=self._command_result.stdout,
            stderr=self._command_result.stderr,
            raw_output=self._parsed_output,
            metadata=self._metadata,
            scope={
                "policy_scope": self._context.scope.value,
                "action_class": self._context.action_class.value,
                "environment": self._context.environment,
                "targets": list(self._context.targets),
            },
            asset={
                "asset_id": str(self._context.asset_id),
                "tenant_id": str(self._context.tenant_id),
            },
            tags=list(self._context.tags),
            errors=[e for e in errors if e],
            warnings=list(self._warnings),
        )

    def cleanup(self) -> None:
        """Release temporary resources; default is a no-op."""

        logger.debug("Adapter cleanup tool=%s", self.tool_name)

    def health(self) -> bool:
        """Return True when the scanner binary is resolvable on PATH."""

        return shutil.which(self._config.binary_path) is not None

    def version(self) -> str:
        """Return tool version string; subclasses should override."""

        return "unknown"

    @abstractmethod
    def build_command(self, context: AdapterExecutionContext) -> List[str]:
        """Construct the argv vector for the scanner."""

    def run_command(
        self,
        command: Sequence[str],
        *,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        """Execute a subprocess with timeout and captured pipes."""

        logger.info("Executing tool=%s command=%s", self.tool_name, list(command))
        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                timeout=self._config.timeout_seconds,
                cwd=self._config.working_directory,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterTimeoutError(
                f"Tool '{self.tool_name}' timed out after "
                f"{self._config.timeout_seconds}s",
                tool_name=self.tool_name,
                details={"command": list(command)},
            ) from exc
        except FileNotFoundError as exc:
            raise AdapterExecutionError(
                f"Binary not found for tool '{self.tool_name}': "
                f"{self._config.binary_path}",
                tool_name=self.tool_name,
            ) from exc
        except OSError as exc:
            raise AdapterExecutionError(
                f"Failed to execute '{self.tool_name}': {exc}",
                tool_name=self.tool_name,
            ) from exc

        return CommandResult(
            exit_code=int(completed.returncode),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    def map_status(self, result: CommandResult) -> RawResultStatus:
        """Map process outcome to ``RawResultStatus`` (override if needed)."""

        if result.timed_out:
            return RawResultStatus.TIMEOUT
        if result.exit_code == 0:
            return RawResultStatus.SUCCEEDED
        return RawResultStatus.FAILED

    def add_warning(self, message: str) -> None:
        """Record a non-fatal warning on the eventual RawResult."""

        self._warnings.append(message)

    def _execute_with_retry(self) -> CommandResult:
        return retry_call(
            self.execute,
            max_retries=self._config.max_retries,
            backoff_seconds=self._config.retry_backoff_seconds,
            tool_name=self.tool_name,
            retry_on=(AdapterExecutionError,),
        )

    def _failure_result(self, status: RawResultStatus, error: str) -> RawResult:
        assert self._context is not None and self._started_at is not None
        completed = utc_now()
        elapsed_ms = (completed - self._started_at).total_seconds() * 1000.0
        metadata = self._metadata_collector.collect(
            context=self._context,
            tool_name=self.tool_name,
            tool_version=self._tool_version,
            arguments=self._command,
            started_at=self._started_at,
            completed_at=completed,
        )
        return RawResult(
            execution_id=self._context.execution_id,
            tenant_id=self._context.tenant_id,
            tool_name=self.tool_name,
            tool_version=self._tool_version,
            execution_time_ms=round(elapsed_ms, 2),
            started_at=self._started_at,
            completed_at=completed,
            status=status,
            exit_code=None,
            stdout="",
            stderr="",
            raw_output=None,
            metadata=metadata,
            scope={
                "policy_scope": self._context.scope.value,
                "action_class": self._context.action_class.value,
                "targets": list(self._context.targets),
            },
            asset={
                "asset_id": str(self._context.asset_id),
                "tenant_id": str(self._context.tenant_id),
            },
            tags=list(self._context.tags),
            errors=[error],
            warnings=list(self._warnings),
        )
