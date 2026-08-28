"""
Normalization package — raw scanner JSON → canonical SecurityFindingObject.

Not integrated with AI framework modules.
"""

from normalization.base_normalizer import BaseNormalizer
from normalization.context import (
    NormalizationContext,
    NormalizationIssue,
    NormalizationResult,
)
from normalization.exceptions import (
    MalformedInputError,
    NormalizationError,
    NormalizationItemError,
    UnknownToolError,
)
from normalization.service import NormalizationService

__all__ = [
    "BaseNormalizer",
    "MalformedInputError",
    "NormalizationContext",
    "NormalizationError",
    "NormalizationIssue",
    "NormalizationItemError",
    "NormalizationResult",
    "NormalizationService",
    "UnknownToolError",
]

__version__ = "1.0.0"
