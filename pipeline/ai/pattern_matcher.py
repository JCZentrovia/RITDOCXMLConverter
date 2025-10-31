"""Pattern matcher that applies AI formatting rules to text blocks."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PatternMatcher:
    """Applies formatting patterns to text blocks."""
    
    def __init__(self, patterns: List, metadata: Dict):
        """
        Initialize with formatting patterns from AI.
        
        Args:
            patterns: List of FormattingPattern objects
            metadata: Document metadata dict
        """
        self.patterns = patterns
        self.metadata = metadata
        logger.info("Initialized PatternMatcher with %d patterns", len(patterns))
    
    def match_pattern(self, text: str, block: Dict) -> Optional[Dict]:
        """
        Find the best matching pattern for given text and block.
        
        Args:
            text: The text content to match
            block: The block dict from heuristics (contains label, bbox, etc.)
        
        Returns:
            Formatting dict if match found, None otherwise
        """
        if not text or not text.strip():
            return None
        
        # Try patterns in priority order (already sorted)
        for pattern in self.patterns:
            if self._check_conditions(text, block, pattern.conditions):
                logger.debug(
                    "Pattern matched: %s for text: %s",
                    pattern.description,
                    text[:50] + "..." if len(text) > 50 else text
                )
                return pattern.formatting
        
        return None
    
    def _check_conditions(self, text: str, block: Dict, conditions: Dict) -> bool:
        """Check if text and block match all conditions."""
        
        # Check starts_with
        if "starts_with" in conditions:
            pattern = conditions["starts_with"]
            if not text.strip().startswith(pattern):
                return False
        
        # Check contains
        if "contains" in conditions:
            pattern = conditions["contains"]
            if pattern not in text:
                return False
        
        # Check all_caps
        if "all_caps" in conditions:
            expected = conditions["all_caps"]
            # Consider text all caps if most alpha chars are uppercase
            alpha_chars = [c for c in text if c.isalpha()]
            if alpha_chars:
                is_all_caps = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.8
                if is_all_caps != expected:
                    return False
        
        # Check has_number
        if "has_number" in conditions:
            expected = conditions["has_number"]
            has_num = any(c.isdigit() for c in text)
            if has_num != expected:
                return False
        
        # Check length constraints
        text_len = len(text.strip())
        if "min_length" in conditions and text_len < conditions["min_length"]:
            return False
        if "max_length" in conditions and text_len > conditions["max_length"]:
            return False
        
        # Check regex pattern
        if "regex_pattern" in conditions:
            pattern = conditions["regex_pattern"]
            try:
                if not re.search(pattern, text):
                    return False
            except re.error as exc:
                logger.warning("Invalid regex pattern '%s': %s", pattern, exc)
                return False
        
        # Check position (if we have bbox info)
        if "position" in conditions:
            expected_pos = conditions["position"]
            if expected_pos != "any":
                # Could use bbox to determine position, for now skip
                pass
        
        return True
    
    def enhance_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """
        Enhance blocks with AI formatting patterns.
        
        Args:
            blocks: List of blocks from heuristics (with labels)
        
        Returns:
            Enhanced blocks with formatting information added
        """
        enhanced = []
        
        for block in blocks:
            enhanced_block = block.copy()
            text = block.get("text", "").strip()
            
            if text:
                # Try to match AI pattern
                formatting = self.match_pattern(text, block)
                if formatting:
                    enhanced_block["ai_formatting"] = formatting
                    logger.debug("Applied AI formatting to block: %s", text[:50])
            
            enhanced.append(enhanced_block)
        
        logger.info("Enhanced %d blocks with AI formatting patterns", len(enhanced))
        return enhanced


def map_pattern_to_heuristic_label(pattern_type: str) -> str:
    """
    Map AI pattern type to heuristic label for consistency.
    
    Args:
        pattern_type: Pattern type from AI (e.g., "chapter_heading")
    
    Returns:
        Corresponding heuristic label (e.g., "chapter")
    """
    mapping = {
        "chapter_heading": "chapter",
        "section_heading": "section",
        "paragraph": "para",
        "list_item": "list_item",
        "quote": "para",  # Quotes are paragraphs with special formatting
        "caption": "caption",
        "header": "para",
        "footer": "para",
        "special_text": "para",
    }
    return mapping.get(pattern_type, "para")


def merge_heuristic_and_ai_labels(heuristic_label: str, ai_pattern_type: str) -> str:
    """
    Merge heuristic label with AI pattern type to get best label.
    
    Heuristics are generally more reliable for structure (chapters, sections),
    while AI is better for formatting details (bold, italic, alignment).
    
    Args:
        heuristic_label: Label from heuristics (e.g., "chapter")
        ai_pattern_type: Pattern type from AI (e.g., "chapter_heading")
    
    Returns:
        The best label to use
    """
    # Trust heuristics for structural elements
    if heuristic_label in ["chapter", "section", "toc", "book_title", "list_item", "table", "figure"]:
        return heuristic_label
    
    # For generic "para", use AI if it has more specific info
    if heuristic_label == "para" and ai_pattern_type in ["chapter_heading", "section_heading"]:
        return map_pattern_to_heuristic_label(ai_pattern_type)
    
    # Default to heuristic label
    return heuristic_label
