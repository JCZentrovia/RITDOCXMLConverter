"""Smart Label Enhancer - Uses AI formatting to improve block labels."""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class SmartLabelEnhancer:
    """
    Uses AI formatting patterns to enhance heuristic labels.
    
    This is the missing piece that makes AI formatting actually improve
    chapter detection and XML structure!
    """
    
    def __init__(self):
        # Thresholds for identifying structural elements by formatting
        self.CHAPTER_INDICATORS = {
            "min_font_size": 16,  # Chapters usually 16pt+
            "requires_bold": True,
            "common_alignment": "center",
            "min_spacing_before": 20,  # Points
        }
        
        self.SECTION_INDICATORS = {
            "min_font_size": 13,  # Sections usually 13-15pt
            "max_font_size": 17,
            "requires_bold": True,
            "common_alignment": "left",
        }
        
        self.TITLE_INDICATORS = {
            "min_font_size": 18,  # Titles are biggest
            "requires_bold": True,
            "requires_center": True,
        }
    
    def enhance_labels(self, blocks: List[Dict]) -> List[Dict]:
        """
        Enhance block labels using AI formatting information.
        
        Args:
            blocks: Blocks with ai_formatting field
        
        Returns:
            Same blocks with improved labels
        """
        enhanced_count = 0
        
        for block in blocks:
            ai_formatting = block.get("ai_formatting", {})
            if not ai_formatting:
                continue
            
            # Get current label
            current_label = block.get("classifier_label") or block.get("label", "para")
            
            # Skip if already confident in certain labels
            if current_label in {"book_title", "toc", "figure", "table"}:
                continue
            
            # Try to enhance the label based on AI formatting
            enhanced_label = self._determine_better_label(
                current_label,
                ai_formatting,
                block.get("text", "")
            )
            
            if enhanced_label != current_label:
                logger.debug(
                    "Enhanced label '%s' → '%s' based on formatting: %s",
                    current_label,
                    enhanced_label,
                    self._format_summary(ai_formatting)
                )
                block["classifier_label"] = enhanced_label
                block["label_enhanced_by_ai"] = True
                enhanced_count += 1
        
        if enhanced_count > 0:
            logger.info("🎯 Enhanced %d block labels using AI formatting", enhanced_count)
        
        return blocks
    
    def _determine_better_label(
        self,
        current_label: str,
        formatting: Dict,
        text: str
    ) -> str:
        """
        Determine if AI formatting suggests a better label.
        
        Priority order:
        1. Book title (largest, bold, centered)
        2. Chapter (large, bold, often centered)
        3. Section (medium-large, bold, left aligned)
        4. Keep original label if formatting doesn't strongly suggest otherwise
        """
        font_size = formatting.get("font_size", 0)
        bold = formatting.get("bold", False)
        alignment = formatting.get("alignment", "")
        spacing_before = formatting.get("spacing_before", 0)
        
        # Check for book title indicators
        if self._matches_title(font_size, bold, alignment):
            # Only upgrade to book_title if it's at the very beginning
            # (we'll check position separately)
            if current_label in {"para", "chapter"}:
                return "book_title"
        
        # Check for chapter indicators
        if self._matches_chapter(font_size, bold, alignment, spacing_before):
            if current_label in {"para", "section"}:
                return "chapter"
        
        # Check for section indicators  
        if self._matches_section(font_size, bold, alignment):
            if current_label == "para":
                return "section"
        
        # Check for TOC based on content
        if self._looks_like_toc(text):
            return "toc"
        
        return current_label
    
    def _matches_title(self, font_size: float, bold: bool, alignment: str) -> bool:
        """Check if formatting matches book title."""
        return (
            font_size >= self.TITLE_INDICATORS["min_font_size"] and
            bold and
            alignment == "center"
        )
    
    def _matches_chapter(
        self,
        font_size: float,
        bold: bool,
        alignment: str,
        spacing_before: float
    ) -> bool:
        """Check if formatting matches chapter heading."""
        # Strong indicators: large font + bold
        if font_size >= self.CHAPTER_INDICATORS["min_font_size"] and bold:
            # Even stronger if also centered
            if alignment == "center":
                return True
            # Or has large spacing before
            if spacing_before >= self.CHAPTER_INDICATORS["min_spacing_before"]:
                return True
            # Bold + large font is pretty strong even without other indicators
            return True
        
        return False
    
    def _matches_section(self, font_size: float, bold: bool, alignment: str) -> bool:
        """Check if formatting matches section heading."""
        indicators = self.SECTION_INDICATORS
        
        return (
            indicators["min_font_size"] <= font_size <= indicators["max_font_size"] and
            bold
        )
    
    def _looks_like_toc(self, text: str) -> bool:
        """Check if text looks like a table of contents entry."""
        text_lower = text.lower().strip()
        
        # Common TOC patterns
        toc_keywords = [
            "table of contents",
            "contents",
            "chapter 1",
            "chapter 2",
            "chapter i",
            "chapter ii",
        ]
        
        return any(keyword in text_lower for keyword in toc_keywords)
    
    def _format_summary(self, formatting: Dict) -> str:
        """Create a readable summary of formatting."""
        parts = []
        
        if formatting.get("font_size"):
            parts.append(f"{formatting['font_size']}pt")
        
        if formatting.get("bold"):
            parts.append("bold")
        
        if formatting.get("italic"):
            parts.append("italic")
        
        if formatting.get("alignment"):
            parts.append(formatting["alignment"])
        
        return ", ".join(parts) if parts else "default"


def enhance_labels_with_ai_formatting(blocks: List[Dict]) -> List[Dict]:
    """
    Convenience function to enhance block labels using AI formatting.
    
    This is the key function that should be called AFTER AI integration
    and BEFORE building DocBook tree.
    
    Args:
        blocks: Blocks with ai_formatting field
    
    Returns:
        Same blocks with enhanced labels
    """
    enhancer = SmartLabelEnhancer()
    return enhancer.enhance_labels(blocks)
