"""IOCRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence
from uuid import UUID

from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.query.filters import IOCSearchFilter
from threat_intelligence.query.pagination import Page, PageRequest


class IOCRepository(ABC):
    """Persistence port for indicators of compromise."""

    @abstractmethod
    def save_ioc(
        self,
        ioc: IndicatorOfCompromise,
        *,
        actor: Optional[str] = None,
    ) -> IndicatorOfCompromise:
        ...

    @abstractmethod
    def get_ioc(
        self,
        ioc_id: UUID,
        *,
        tenant_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> IndicatorOfCompromise:
        ...

    @abstractmethod
    def find_by_value(
        self,
        *,
        ioc_type: str,
        normalized_value: str,
        tenant_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> Optional[IndicatorOfCompromise]:
        ...

    @abstractmethod
    def search_iocs(
        self,
        filters: IOCSearchFilter,
        page: PageRequest,
    ) -> Page[IndicatorOfCompromise]:
        ...

    @abstractmethod
    def match_values(
        self,
        *,
        tenant_id: UUID,
        normalized_values: Sequence[str],
        include_global: bool = True,
    ) -> List[IndicatorOfCompromise]:
        """Correlate a batch of normalized values against the IOC store."""
