"""
Adapter registry — central catalogue of tool adapter classes.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Type

from src.adapters.base.adapter_exception import AdapterNotFoundError
from src.adapters.base.base_adapter import BaseToolAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Process-wide registry of adapter classes keyed by tool name.

    Supports decorator registration::

        @AdapterRegistry.register("nuclei")
        class NucleiAdapter(BaseToolAdapter):
            ...
    """

    _adapters: Dict[str, Type[BaseToolAdapter]] = {}

    @classmethod
    def register(cls, tool_name: str):
        """Class decorator that registers an adapter implementation."""

        key = tool_name.strip().lower()

        def decorator(adapter_cls: Type[BaseToolAdapter]) -> Type[BaseToolAdapter]:
            if not issubclass(adapter_cls, BaseToolAdapter):
                raise TypeError(
                    f"{adapter_cls.__name__} must inherit BaseToolAdapter"
                )
            cls._adapters[key] = adapter_cls
            adapter_cls.tool_name = key
            logger.info(
                "Registered adapter tool=%s class=%s",
                key,
                adapter_cls.__name__,
            )
            return adapter_cls

        return decorator

    @classmethod
    def unregister(cls, tool_name: str) -> None:
        """Remove a tool from the registry."""

        key = tool_name.strip().lower()
        removed = cls._adapters.pop(key, None)
        if removed is None:
            raise AdapterNotFoundError(
                f"Cannot unregister unknown adapter '{tool_name}'",
                tool_name=key,
            )
        logger.info("Unregistered adapter tool=%s", key)

    @classmethod
    def get(cls, tool_name: str) -> Type[BaseToolAdapter]:
        """Resolve an adapter class by tool name."""

        key = tool_name.strip().lower()
        adapter_cls = cls._adapters.get(key)
        if adapter_cls is None:
            raise AdapterNotFoundError(
                f"No adapter registered for tool '{tool_name}'",
                tool_name=key,
                details={"registered": sorted(cls._adapters.keys())},
            )
        return adapter_cls

    @classmethod
    def list(cls) -> tuple[str, ...]:
        """Return sorted registered tool names."""

        return tuple(sorted(cls._adapters.keys()))

    @classmethod
    def items(cls) -> Iterable[tuple[str, Type[BaseToolAdapter]]]:
        """Iterate (tool_name, adapter_class) pairs."""

        return tuple(sorted(cls._adapters.items(), key=lambda item: item[0]))

    @classmethod
    def clear(cls) -> None:
        """Clear the registry (tests only)."""

        cls._adapters.clear()

    @classmethod
    def contains(cls, tool_name: str) -> bool:
        """Return True when a tool is registered."""

        return tool_name.strip().lower() in cls._adapters
