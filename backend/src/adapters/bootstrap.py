"""
Import side-effects that register built-in adapters with ``AdapterRegistry``.
"""

from src.adapters.checkov.adapter import CheckovAdapter
from src.adapters.grype.adapter import GrypeAdapter
from src.adapters.nuclei.adapter import NucleiAdapter
from src.adapters.prowler.adapter import ProwlerAdapter
from src.adapters.trivy.adapter import TrivyAdapter

__all__ = [
    "CheckovAdapter",
    "GrypeAdapter",
    "NucleiAdapter",
    "ProwlerAdapter",
    "TrivyAdapter",
]
