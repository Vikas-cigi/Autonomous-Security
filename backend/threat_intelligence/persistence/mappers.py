"""Map between domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from threat_intelligence.domain.enums import AuditAction
from threat_intelligence.domain.history import ThreatIntelHistory, ThreatIntelVersion
from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.domain.models import (
    CVERecord,
    ThreatFeedMetadata,
    ThreatIntelligence,
)
from threat_intelligence.persistence.orm import (
    CVERecordORM,
    IOCRecordORM,
    ThreatFeedORM,
    ThreatIntelHistoryORM,
    ThreatIntelVersionORM,
    ThreatIntelligenceORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def intel_to_orm(intel: ThreatIntelligence, *, version: int) -> ThreatIntelligenceORM:
    return ThreatIntelligenceORM(
        id=intel.id,
        tenant_id=intel.tenant_id,
        finding_id=intel.finding_id,
        confidence_score=intel.confidence_score,
        actively_exploited=intel.exploit.actively_exploited,
        in_cisa_kev=intel.exploit.in_cisa_kev,
        current_version=version,
        payload=intel.model_dump(mode="json"),
        first_seen_at=intel.first_seen_at,
        last_updated_at=intel.last_updated_at,
        created_at=intel.created_at,
        updated_at=intel.updated_at,
    )


def apply_intel_to_orm(
    row: ThreatIntelligenceORM,
    intel: ThreatIntelligence,
    *,
    version: int,
) -> None:
    row.finding_id = intel.finding_id
    row.confidence_score = intel.confidence_score
    row.actively_exploited = intel.exploit.actively_exploited
    row.in_cisa_kev = intel.exploit.in_cisa_kev
    row.current_version = version
    row.payload = intel.model_dump(mode="json")
    row.first_seen_at = intel.first_seen_at
    row.last_updated_at = intel.last_updated_at
    row.updated_at = intel.updated_at


def orm_to_intel(row: ThreatIntelligenceORM) -> ThreatIntelligence:
    return ThreatIntelligence.model_validate(row.payload)


def cve_to_orm(record: CVERecord, *, version: int) -> CVERecordORM:
    return CVERecordORM(
        id=record.id,
        tenant_id=record.tenant_id,
        cve_id=record.cve_id,
        in_cisa_kev=record.exploit.in_cisa_kev,
        actively_exploited=record.exploit.actively_exploited,
        epss_score=record.epss.score if record.epss else None,
        confidence_score=record.confidence_score,
        current_version=version,
        payload=record.model_dump(mode="json"),
        first_seen_at=record.first_seen_at,
        last_updated_at=record.last_updated_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def apply_cve_to_orm(row: CVERecordORM, record: CVERecord, *, version: int) -> None:
    row.cve_id = record.cve_id
    row.tenant_id = record.tenant_id
    row.in_cisa_kev = record.exploit.in_cisa_kev
    row.actively_exploited = record.exploit.actively_exploited
    row.epss_score = record.epss.score if record.epss else None
    row.confidence_score = record.confidence_score
    row.current_version = version
    row.payload = record.model_dump(mode="json")
    row.first_seen_at = record.first_seen_at
    row.last_updated_at = record.last_updated_at
    row.updated_at = record.updated_at


def orm_to_cve(row: CVERecordORM) -> CVERecord:
    return CVERecord.model_validate(row.payload)


def ioc_to_orm(ioc: IndicatorOfCompromise, *, version: int) -> IOCRecordORM:
    return IOCRecordORM(
        id=ioc.id,
        tenant_id=ioc.tenant_id,
        ioc_type=ioc.ioc_type.value,
        value=ioc.value,
        normalized_value=ioc.normalized_value,
        confidence_score=ioc.confidence_score,
        is_active=ioc.is_active,
        current_version=version,
        payload=ioc.model_dump(mode="json"),
        first_seen_at=ioc.first_seen_at,
        last_seen_at=ioc.last_seen_at,
        last_updated_at=ioc.last_updated_at,
        created_at=ioc.created_at,
        updated_at=ioc.updated_at,
    )


def apply_ioc_to_orm(
    row: IOCRecordORM,
    ioc: IndicatorOfCompromise,
    *,
    version: int,
) -> None:
    row.ioc_type = ioc.ioc_type.value
    row.value = ioc.value
    row.normalized_value = ioc.normalized_value
    row.confidence_score = ioc.confidence_score
    row.is_active = ioc.is_active
    row.current_version = version
    row.payload = ioc.model_dump(mode="json")
    row.first_seen_at = ioc.first_seen_at
    row.last_seen_at = ioc.last_seen_at
    row.last_updated_at = ioc.last_updated_at
    row.updated_at = ioc.updated_at


def orm_to_ioc(row: IOCRecordORM) -> IndicatorOfCompromise:
    return IndicatorOfCompromise.model_validate(row.payload)


def feed_to_orm(feed: ThreatFeedMetadata, *, version: int) -> ThreatFeedORM:
    return ThreatFeedORM(
        id=feed.id,
        tenant_id=feed.tenant_id,
        provider=feed.provider.value,
        name=feed.name,
        enabled=feed.enabled,
        last_sync_status=feed.last_sync_status,
        current_version=version,
        payload=feed.model_dump(mode="json"),
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


def apply_feed_to_orm(
    row: ThreatFeedORM,
    feed: ThreatFeedMetadata,
    *,
    version: int,
) -> None:
    row.provider = feed.provider.value
    row.name = feed.name
    row.enabled = feed.enabled
    row.last_sync_status = feed.last_sync_status
    row.current_version = version
    row.payload = feed.model_dump(mode="json")
    row.updated_at = feed.updated_at


def orm_to_feed(row: ThreatFeedORM) -> ThreatFeedMetadata:
    return ThreatFeedMetadata.model_validate(row.payload)


def version_from_orm(row: ThreatIntelVersionORM) -> ThreatIntelVersion:
    return ThreatIntelVersion(
        id=row.id,
        intel_id=row.intel_id,
        tenant_id=row.tenant_id,
        version=row.version,
        snapshot=ThreatIntelligence.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at),
    )


def history_from_orm(row: ThreatIntelHistoryORM) -> ThreatIntelHistory:
    return ThreatIntelHistory(
        id=row.id,
        intel_id=row.intel_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        created_at=_as_utc(row.created_at),
    )
