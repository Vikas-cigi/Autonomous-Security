"""Deterministic export serializers (JSON / CSV / Excel-tsv / PDF-text)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, Optional

from models.common import new_id, utc_now
from reporting_analytics.domain.enums import AuditAction, ExportFormat, ExportStatus
from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.domain.inputs import ExportGenerationRequest
from reporting_analytics.domain.models import ExportRequest, ExportResult, Report
from reporting_analytics.exceptions import ExportError, InvalidReportingRequestError
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)
from reporting_analytics.persistence.stores import ExportStore


class ExportService:
    """
    Produce export payloads without mutating platform source data.

    PDF/Excel are deterministic textual representations suitable for downstream
    renderers — no binary PDF library required in-core.
    """

    CONTENT_TYPES = {
        ExportFormat.JSON: "application/json",
        ExportFormat.CSV: "text/csv",
        ExportFormat.EXCEL: "text/tab-separated-values",
        ExportFormat.PDF: "text/plain",
    }

    def __init__(
        self,
        export_store: Optional[ExportStore] = None,
        audit_repository: Optional[AuditReportingRepository] = None,
    ) -> None:
        self._store = export_store
        self._audit = audit_repository

    def export(
        self,
        request: ExportGenerationRequest,
        *,
        report: Optional[Report] = None,
        payload: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> ExportResult:
        try:
            fmt = ExportFormat(request.format.lower())
        except ValueError as exc:
            raise InvalidReportingRequestError(
                f"Unsupported export format: {request.format}",
                details={"format": request.format},
            ) from exc

        tenant_id = None
        if report is not None:
            tenant_id = report.tenant_id
            payload = payload or {
                "report_id": str(report.id),
                "title": report.title,
                "type": report.report_type.value,
                "status": report.status.value,
                "result": report.result.model_dump(mode="json") if report.result else {},
            }
        elif request.snapshot is not None:
            tenant_id = request.snapshot.tenant_id
            payload = payload or request.snapshot.model_dump(mode="json")
        else:
            raise InvalidReportingRequestError(
                "Export requires report or snapshot payload"
            )

        assert tenant_id is not None
        export_req = ExportRequest(
            tenant_id=tenant_id,
            format=fmt,
            title=request.title,
            report_id=request.report_id or (report.id if report else None),
            dashboard_id=request.dashboard_id,
            actor=request.actor,
        )

        try:
            content = self._serialize(fmt, payload, title=request.title)
            result = ExportResult(
                id=new_id(),
                request_id=export_req.id,
                tenant_id=tenant_id,
                format=fmt,
                status=ExportStatus.COMPLETED,
                title=request.title,
                content_type=self.CONTENT_TYPES[fmt],
                content=content,
                byte_length=len(content.encode("utf-8")),
                completed_at=utc_now(),
            )
            action = AuditAction.EXPORT_CREATED
            success = True
        except Exception as exc:  # noqa: BLE001 — convert to domain error
            result = ExportResult(
                id=new_id(),
                request_id=export_req.id,
                tenant_id=tenant_id,
                format=fmt,
                status=ExportStatus.FAILED,
                title=request.title,
                content_type="text/plain",
                content="",
                byte_length=0,
                error_message=str(exc)[:4000],
                completed_at=utc_now(),
            )
            action = AuditAction.EXPORT_FAILED
            success = False

        if persist and self._store is not None:
            result = self._store.save(result)
        if self._audit is not None:
            self._audit.append(
                ReportingAuditRecord(
                    tenant_id=tenant_id,
                    report_id=export_req.report_id,
                    export_id=result.id,
                    action=action,
                    actor=request.actor,
                    message=f"Export {fmt.value}: {result.status.value}",
                    status=result.status.value,
                    details={"byte_length": result.byte_length},
                )
            )
        if not success:
            raise ExportError(
                result.error_message or "Export failed",
                details={"export_id": str(result.id)},
            )
        return result

    def _serialize(
        self, fmt: ExportFormat, payload: Dict[str, Any], *, title: str
    ) -> str:
        if fmt == ExportFormat.JSON:
            return json.dumps(
                {"title": title, "generated_at": utc_now().isoformat(), "data": payload},
                indent=2,
                default=str,
            )
        flat = self._flatten(payload)
        if fmt == ExportFormat.CSV:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["key", "value"])
            for k, v in flat:
                writer.writerow([k, v])
            return buf.getvalue()
        if fmt == ExportFormat.EXCEL:
            # TSV representation for Excel-compatible import
            lines = ["key\tvalue", f"title\t{title}"]
            lines.extend(f"{k}\t{v}" for k, v in flat)
            return "\n".join(lines) + "\n"
        # PDF textual layout
        lines = [
            "XOLARIS REPORT EXPORT",
            "=" * 40,
            f"Title: {title}",
            f"Generated: {utc_now().isoformat()}",
            "-" * 40,
        ]
        for k, v in flat:
            lines.append(f"{k}: {v}")
        lines.append("=" * 40)
        return "\n".join(lines) + "\n"

    def _flatten(
        self, data: Any, prefix: str = ""
    ) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        if isinstance(data, dict):
            for k, v in data.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                rows.extend(self._flatten(v, key))
        elif isinstance(data, list):
            for i, v in enumerate(data):
                key = f"{prefix}[{i}]"
                rows.extend(self._flatten(v, key))
        else:
            rows.append((prefix or "value", str(data)))
        return rows
