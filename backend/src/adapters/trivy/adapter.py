"""Trivy security tool adapter."""

from __future__ import annotations

import logging
from typing import Any, List

from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.raw_result import RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.trivy.config import TrivyAdapterConfig
from src.adapters.trivy.parser import TrivyParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("trivy")
class TrivyAdapter(BaseToolAdapter):
    """Adapter for Aqua Trivy vulnerability / misconfiguration / secret scans."""

    tool_name = "trivy"

    def __init__(self, config: TrivyAdapterConfig, **kwargs: Any) -> None:
        super().__init__(config, **kwargs)
        self._trivy_config = config
        self._parser = TrivyParser()

    def build_command(self, context: AdapterExecutionContext) -> List[str]:
        if not context.targets:
            raise ValueError("Trivy requires at least one target")
        command = [
            self._config.binary_path,
            self._trivy_config.scan_type,
            "--format",
            self._trivy_config.format,
            "--quiet",
        ]
        if self._trivy_config.severity:
            command.extend(["--severity", self._trivy_config.severity])
        if self._trivy_config.scanners:
            command.extend(["--scanners", ",".join(self._trivy_config.scanners)])
        command.extend(self._config.default_args)
        command.extend(context.arguments)
        # Trivy accepts a single primary target per invocation.
        command.append(context.targets[0])
        if len(context.targets) > 1:
            self.add_warning(
                "Trivy adapter executes the first target only; "
                f"ignored={context.targets[1:]}"
            )
        return command

    def parse(self, stdout: str, stderr: str, exit_code: int) -> Any:
        return self._parser.parse(stdout, stderr, exit_code)

    def map_status(self, result: CommandResult) -> RawResultStatus:
        if result.exit_code in {0, 1}:
            return RawResultStatus.SUCCEEDED
        return RawResultStatus.FAILED

    def version(self) -> str:
        try:
            result = self.run_command([self._config.binary_path, "--version"])
            text = (result.stdout or result.stderr or "").strip()
            return text.splitlines()[0][:128] if text else "trivy"
        except Exception:  # noqa: BLE001
            logger.debug("Trivy version probe failed", exc_info=True)
            return "trivy"
