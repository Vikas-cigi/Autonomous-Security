"""Checkov security tool adapter."""

from __future__ import annotations

import logging
from typing import Any, List

from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.raw_result import RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.checkov.config import CheckovAdapterConfig
from src.adapters.checkov.parser import CheckovParser
from src.adapters.common.execution_context import AdapterExecutionContext

logger = logging.getLogger(__name__)


@AdapterRegistry.register("checkov")
class CheckovAdapter(BaseToolAdapter):
    """Adapter for Bridgecrew/Prisma Checkov IaC policy scans."""

    tool_name = "checkov"

    def __init__(self, config: CheckovAdapterConfig, **kwargs: Any) -> None:
        super().__init__(config, **kwargs)
        self._checkov_config = config
        self._parser = CheckovParser()

    def build_command(self, context: AdapterExecutionContext) -> List[str]:
        if not context.targets:
            raise ValueError("Checkov requires at least one filesystem target")
        command = [
            self._config.binary_path,
            "-d",
            context.targets[0],
            "-o",
            self._checkov_config.output_format,
        ]
        if self._checkov_config.compact:
            command.append("--compact")
        if self._checkov_config.soft_fail:
            command.append("--soft-fail")
        if self._checkov_config.framework:
            command.extend(["--framework", self._checkov_config.framework])
        for skip in self._checkov_config.skip_checks:
            command.extend(["--skip-check", skip])
        command.extend(self._config.default_args)
        command.extend(context.arguments)
        if len(context.targets) > 1:
            self.add_warning(
                "Checkov adapter scans the first directory target only; "
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
            return text.splitlines()[0][:128] if text else "checkov"
        except Exception:  # noqa: BLE001
            logger.debug("Checkov version probe failed", exc_info=True)
            return "checkov"
