"""Pagination primitives for Asset Inventory."""

from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import Field, field_validator

from models.common import FortiBaseModel

T = TypeVar("T")


class PageRequest(FortiBaseModel):
    """1-based page request with bounded page size."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class Page(FortiBaseModel, Generic[T]):
    """Page of results with total count."""

    items: List[T]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)

    @field_validator("total_pages")
    @classmethod
    def non_negative_pages(cls, value: int) -> int:
        if value < 0:
            raise ValueError("total_pages must be >= 0")
        return value

    @classmethod
    def from_items(
        cls,
        items: List[T],
        *,
        request: PageRequest,
        total_items: int,
    ) -> Page[T]:
        total_pages = (
            (total_items + request.page_size - 1) // request.page_size
            if total_items > 0
            else 0
        )
        return cls(
            items=items,
            page=request.page,
            page_size=request.page_size,
            total_items=total_items,
            total_pages=total_pages,
        )
