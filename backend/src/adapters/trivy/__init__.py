"""Trivy adapter package."""

from src.adapters.trivy.adapter import TrivyAdapter
from src.adapters.trivy.config import TrivyAdapterConfig

__all__ = ["TrivyAdapter", "TrivyAdapterConfig"]
