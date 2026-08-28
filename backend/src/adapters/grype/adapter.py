"""Grype security tool adapter."""

from __future__ import annotations

import logging
from typing import Any, List

from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.raw_result import RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.grype.config import GrypeAdapterConfig
from src.adapters.grype.parser import GrypeParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("grype")
class GrypeAdapter(BaseToolAdapter):
    """
    Adapter for Anchore Grype container/image vulnerability scanner.

    Returns ``RawResult`` only — never ``SecurityFindingObject``.
    """

    tool_name = "grype"

    def __init__(self, config: GrypeAdapterConfig, **kwargs: Any) -> None:
        super().__init__(config, **kwargs)
        self._grype_config = config
        self._parser = GrypeParser()

    def build_command(self, context: AdapterExecutionContext) -> List[str]:
        if not context.targets:
            raise ValueError("Grype requires at least one target (image, dir, sbom)")
        command = [
            self._config.binary_path,
            context.targets[0],
            "-o",
            self._grype_config.output_format,
        ]
        if self._grype_config.only_fixed:
            command.append("--only-fixed")
        if self._grype_config.fail_on:
            command.extend(["--fail-on", self._grype_config.fail_on])
        if self._grype_config.add_cpes_if_none:
            command.append("--add-cpes-if-none")
        command.extend(self._config.default_args)
        command.extend(context.arguments)
        if len(context.targets) > 1:
            self.add_warning(
                "Grype adapter scans the first target only; "
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
            result = self.run_command([self._config.binary_path, "version"])
            text = (result.stdout or result.stderr or "").strip()
            return text.splitlines()[0][:128] if text else "grype"
        except Exception:  # noqa: BLE001
            logger.debug("Grype version probe failed", exc_info=True)
            return "grype"
