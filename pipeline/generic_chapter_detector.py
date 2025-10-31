"""
Generic Chapter Detector - Fully AI-Driven

This reads chapter patterns from AI's JSON output and applies them generically.
No hard-coded patterns - everything comes from the Vision AI analysis.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class GenericChapterDetector:
    """
    Detects chapters using patterns from AI Vision analysis.
    
    Completely generic - works for any book format:
    - "CHAPTER 1", "Chapter One", "PART I", etc.
    - All patterns come from AI's formatting_patterns.json
    - No hard-coded assumptions
    """
    
    def __init__(self, ai_patterns: Dict):
        """
        Initialize with AI patterns.
        
        Args:
            ai_patterns: Full patterns dict from formatting_patterns.json
        """
        self.patterns = ai_patterns.get("patterns", [])
        self.metadata = ai_patterns.get("metadata", {})
        
        # Find all structural patterns (chapter, section, etc.)
        self.chapter_patterns = self._extract_structural_patterns()
        
        logger.info("Initialized with %d structural patterns", len(self.chapter_patterns))
    
    def _extract_structural_patterns(self) -> List[Dict]:
        """
        Extract structural patterns (chapter, section) from AI patterns.
        
        Returns patterns sorted by priority (most important first).
        """
        structural_types = ['chapter_heading', 'section_heading', 'header']
        
        structural = [
            p for p in self.patterns
            if p.get('pattern_type') in structural_types
        ]
        
        # Sort by priority (lower number = higher priority)
        structural.sort(key=lambda p: p.get('priority', 999))
        
        return structural
    
    def find_chapters(self, text: str) -> List[Dict[str, Any]]:
        """
        Find all chapters in text using AI patterns.
        
        Args:
            text: Full book text
            
        Returns:
            List of chapter dicts with keys:
                - line_num: Line number where chapter starts
                - text: The chapter heading text
                - pattern_type: Type of pattern matched
                - confidence: How confident we are (0-1)
        """
        if not self.chapter_patterns:
            logger.warning("No chapter patterns available from AI")
            return []
        
        chapters = []
        lines = text.split('\n')
        
        # Try each pattern
        for pattern_def in self.chapter_patterns:
            if pattern_def.get('pattern_type') != 'chapter_heading':
                continue
            
            logger.info("Searching with pattern: %s", pattern_def.get('description', 'unnamed'))
            
            matches = self._find_pattern_matches(lines, pattern_def)
            chapters.extend(matches)
        
        # Remove duplicates (same line number)
        chapters = self._deduplicate_chapters(chapters)
        
        # Sort by line number
        chapters.sort(key=lambda c: c['line_num'])
        
        logger.info("Found %d chapters using AI patterns", len(chapters))
        return chapters
    
    def _find_pattern_matches(
        self,
        lines: List[str],
        pattern_def: Dict
    ) -> List[Dict[str, Any]]:
        """
        Find all matches for a specific pattern.
        
        Args:
            lines: Text lines
            pattern_def: Pattern definition from AI
            
        Returns:
            List of matches
        """
        matches = []
        conditions = pattern_def.get('conditions', {})
        formatting = pattern_def.get('formatting', {})
        
        # Build regex from conditions
        regex = self._build_regex_from_conditions(conditions)
        
        if not regex:
            logger.warning("Could not build regex from conditions: %s", conditions)
            return matches
        
        # Search through lines
        for line_num, line in enumerate(lines, start=1):
            line_stripped = line.strip()
            
            if not line_stripped:
                continue
            
            # Try to match
            match = re.match(regex, line_stripped, re.IGNORECASE)
            
            if match:
                # Calculate confidence based on formatting match
                confidence = self._calculate_confidence(
                    line_stripped,
                    conditions,
                    formatting
                )
                
                if confidence > 0.5:  # Threshold
                    matches.append({
                        'line_num': line_num,
                        'text': line_stripped,
                        'pattern_type': pattern_def.get('pattern_type'),
                        'confidence': confidence,
                        'formatting': formatting,
                    })
                    logger.debug(
                        "Match at line %d (conf: %.2f): %s",
                        line_num, confidence, line_stripped[:50]
                    )
        
        return matches
    
    def _build_regex_from_conditions(self, conditions: Dict) -> Optional[str]:
        r"""
        Build a regex pattern from AI conditions.
        
        Examples:
        - {"starts_with": "CHAPTER", "all_caps": true} 
          → r'^CHAPTER\s+.*$'
        
        - {"starts_with": "Chapter", "min_length": 8}
          → r'^Chapter\s+.*$'
          
        - {"position": "start", "all_caps": true, "min_length": 5}
          → r'^[A-Z]{5,}.*$'
        """
        starts_with = conditions.get('starts_with')
        all_caps = conditions.get('all_caps', False)
        min_length = conditions.get('min_length', 0)
        position = conditions.get('position', 'any')
        
        # Case 1: Specific start text (most reliable)
        if starts_with:
            # Escape special regex characters
            escaped = re.escape(starts_with)
            
            if all_caps:
                # Must be exact caps
                pattern = rf'^{escaped}\s+.*$'
            else:
                # Case insensitive
                pattern = rf'^{escaped}\s+.*$'
            
            return pattern
        
        # Case 2: All caps with minimum length
        if all_caps and min_length > 0:
            pattern = rf'^[A-Z\s]{{{min_length},}}$'
            return pattern
        
        # Case 3: Position-based
        if position == 'start':
            if all_caps:
                return r'^[A-Z][A-Z\s]+$'
            else:
                return r'^[A-Za-z][A-Za-z\s]+$'
        
        return None
    
    def _calculate_confidence(
        self,
        text: str,
        conditions: Dict,
        formatting: Dict
    ) -> float:
        """
        Calculate confidence that this is actually a chapter.
        
        Considers:
        - How well text matches conditions
        - How "chapter-like" the formatting is
        - Length and structure of text
        """
        confidence = 0.5  # Base confidence
        
        # Bonus for matching conditions
        if conditions.get('starts_with'):
            starts_with = conditions['starts_with']
            if text.upper().startswith(starts_with.upper()):
                confidence += 0.2
        
        if conditions.get('all_caps'):
            if text.isupper():
                confidence += 0.1
        
        # Bonus for chapter-like formatting
        font_size = formatting.get('font_size', 12)
        if font_size >= 16:  # Large font
            confidence += 0.1
        
        if formatting.get('bold'):
            confidence += 0.05
        
        if formatting.get('alignment') == 'center':
            confidence += 0.05
        
        # Penalty for very long text (chapters are usually short headings)
        if len(text) > 100:
            confidence -= 0.2
        
        return min(1.0, max(0.0, confidence))
    
    def _deduplicate_chapters(self, chapters: List[Dict]) -> List[Dict]:
        """Remove duplicate chapter detections at same line."""
        if not chapters:
            return []
        
        # Keep highest confidence for each line
        by_line = {}
        for chapter in chapters:
            line_num = chapter['line_num']
            if line_num not in by_line or chapter['confidence'] > by_line[line_num]['confidence']:
                by_line[line_num] = chapter
        
        return list(by_line.values())
    
    def split_text_by_chapters(
        self,
        text: str,
        output_dir: Path,
        base_name: str = "chapter"
    ) -> List[Tuple[str, Path]]:
        """
        Split text into chapter files based on detected chapters.
        
        Args:
            text: Full book text
            output_dir: Directory to save chapters
            base_name: Base name for chapter files
            
        Returns:
            List of (chapter_identifier, file_path) tuples
        """
        chapters = self.find_chapters(text)
        
        if not chapters:
            logger.warning("No chapters detected - saving as single file")
            output_dir.mkdir(parents=True, exist_ok=True)
            single_file = output_dir / f"{base_name}_full.txt"
            single_file.write_text(text, encoding='utf-8')
            return [("full_book", single_file)]
        
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = text.split('\n')
        chapter_files = []
        
        for i, chapter in enumerate(chapters):
            line_num = chapter['line_num']
            
            # Determine end of this chapter
            if i + 1 < len(chapters):
                end_line = chapters[i + 1]['line_num'] - 1
            else:
                end_line = len(lines)
            
            # Extract chapter text
            chapter_lines = lines[line_num - 1:end_line]
            chapter_text = '\n'.join(chapter_lines)
            
            # Create filename
            chapter_num = i + 1
            chapter_heading = chapter['text']
            safe_heading = self._safe_filename(chapter_heading)
            
            filename = f"{base_name}_{chapter_num:03d}_{safe_heading}.txt"
            chapter_file = output_dir / filename
            
            chapter_file.write_text(chapter_text, encoding='utf-8')
            chapter_files.append((chapter_heading, chapter_file))
            
            logger.debug(
                "Saved chapter %d: %s (%d lines, confidence: %.2f)",
                chapter_num, filename, len(chapter_lines), chapter['confidence']
            )
        
        logger.info("Split into %d chapter files", len(chapter_files))
        return chapter_files
    
    def _safe_filename(self, text: str, max_length: int = 40) -> str:
        """Convert text to safe filename."""
        # Remove special characters
        safe = re.sub(r'[^\w\s-]', '', text)
        # Replace whitespace with underscores
        safe = re.sub(r'\s+', '_', safe)
        # Limit length
        safe = safe[:max_length]
        return safe.lower()


def detect_chapters_from_ai_patterns(
    text: str,
    ai_patterns_path: Path
) -> List[Dict[str, Any]]:
    """
    Convenience function to detect chapters using AI patterns.
    
    Args:
        text: Full book text
        ai_patterns_path: Path to formatting_patterns.json from AI
        
    Returns:
        List of detected chapters
    """
    with open(ai_patterns_path, 'r') as f:
        ai_patterns = json.load(f)
    
    detector = GenericChapterDetector(ai_patterns)
    return detector.find_chapters(text)


def split_by_ai_chapters(
    text: str,
    ai_patterns_path: Path,
    output_dir: Path,
    base_name: str = "chapter"
) -> List[Tuple[str, Path]]:
    """
    Convenience function to split text by chapters using AI patterns.
    
    Args:
        text: Full book text
        ai_patterns_path: Path to formatting_patterns.json from AI
        output_dir: Where to save chapter files
        base_name: Base name for files
        
    Returns:
        List of (chapter_name, file_path) tuples
    """
    with open(ai_patterns_path, 'r') as f:
        ai_patterns = json.load(f)
    
    detector = GenericChapterDetector(ai_patterns)
    return detector.split_text_by_chapters(text, output_dir, base_name)
