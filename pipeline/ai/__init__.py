"""Utilities for AI-assisted formatting workflows."""

from .config import OpenAIConfig, export_intermediate_artifacts_enabled
from .docx_to_docbook import convert_docx_to_docbook

# New pattern-based imports
try:
    from .pattern_vision_formatter import PatternVisionFormatter, FormattingRules
    from .pattern_matcher import PatternMatcher
    from .formatted_docx_builder import FormattedDocxBuilder, create_formatted_docx
except ImportError:
    # Gracefully handle missing dependencies
    PatternVisionFormatter = None
    FormattingRules = None
    PatternMatcher = None
    FormattedDocxBuilder = None
    create_formatted_docx = None

__all__ = [
    "OpenAIConfig",
    "export_intermediate_artifacts_enabled",
    "convert_docx_to_docbook",
    # New exports
    "PatternVisionFormatter",
    "FormattingRules",
    "PatternMatcher",
    "FormattedDocxBuilder",
    "create_formatted_docx",
]