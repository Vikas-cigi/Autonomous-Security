"""Search filters for Reporting & Analytics."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from reporting_analytics.domain.enums import (
    DashboardType,
    ReportStatus,
    ReportType,
)


class ReportSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    report_types: Optional[List[ReportType]] = None
    statuses: Optional[List[ReportStatus]] = None
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class DashboardSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    dashboard_types: Optional[List[DashboardType]] = None


class AnalyticsSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    label: Optional[str] = Field(default=None, max_length=128)


class KPISearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    snapshot_id: Optional[UUID] = None
    names: Optional[List[str]] = None


class AuditReportingSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    report_id: Optional[UUID] = None
    dashboard_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
