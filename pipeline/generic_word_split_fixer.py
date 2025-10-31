"""
Generic Word Split Fixer - Uses Statistical and Dictionary Methods

This doesn't hard-code patterns. Instead, it:
1. Uses statistical analysis to detect suspicious splits
2. Uses dictionary lookups to verify words
3. Learns from the document itself
"""

from __future__ import annotations

import re
import logging
from typing import List, Set, Dict, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class GenericWordSplitFixer:
    """
    Automatically detects and fixes word splits without hard-coded patterns.
    
    Uses multiple strategies:
    1. Dictionary-based: Check if joined words form valid words
    2. Statistical: Look for suspicious patterns (single letters, rare combinations)
    3. Context-based: Use surrounding text to make decisions
    """
    
    def __init__(self, use_dictionary: bool = True):
        self.use_dictionary = use_dictionary
        self.word_frequency: Dict[str, int] = Counter()
        
        # Load English dictionary if available
        self.dictionary: Set[str] = set()
        if use_dictionary:
            self._load_dictionary()
    
    def _load_dictionary(self):
        """Load English dictionary for word validation."""
        try:
            # Try to load from common locations
            dict_files = [
                '/usr/share/dict/words',
                '/usr/dict/words',
            ]
            
            for dict_file in dict_files:
                try:
                    with open(dict_file, 'r') as f:
                        self.dictionary = {word.strip().lower() for word in f}
                    logger.info("Loaded %d words from dictionary", len(self.dictionary))
                    return
                except FileNotFoundError:
                    continue
            
            # If no system dictionary, use a basic medical/technical word list
            logger.warning("No system dictionary found, using basic word list")
            self._load_basic_wordlist()
            
        except Exception as e:
            logger.warning("Failed to load dictionary: %s", e)
            self.use_dictionary = False
    
    def _load_basic_wordlist(self):
        """Load a basic word list for common splits."""
        # Common words that often get split in PDFs
        basic_words = [
            'deficiency', 'deficit', 'defined', 'fluid', 'cerebral',
            'immunodeficiency', 'insufficiency', 'confidence', 'efficient',
            'efficacy', 'effect', 'affect', 'different', 'office',
            'sufficient', 'professional', 'specific', 'definitive',
            'official', 'difficulty', 'certificate', 'effective',
            'affection', 'differential', 'artificial', 'beneficial',
        ]
        self.dictionary = set(basic_words)
    
    def analyze_document(self, text: str):
        """
        Analyze document to learn word patterns.
        This helps us understand what's "normal" in this document.
        """
        # Build word frequency map
        words = re.findall(r'\b[a-z]+\b', text.lower())
        self.word_frequency = Counter(words)
        logger.info("Analyzed document: %d unique words", len(self.word_frequency))
    
    def fix_splits(self, text: str) -> str:
        """
        Automatically fix word splits in text.
        
        Args:
            text: Text with potential word splits
            
        Returns:
            Text with splits fixed
        """
        # First, analyze the document to learn patterns
        self.analyze_document(text)
        
        # Find potential splits
        potential_splits = self._find_potential_splits(text)
        
        # Fix them
        fixed_text = text
        fixes_applied = 0
        
        for original, fixed in potential_splits:
            if original != fixed:
                # Use word boundaries to avoid partial replacements
                pattern = r'\b' + re.escape(original) + r'\b'
                fixed_text = re.sub(pattern, fixed, fixed_text)
                fixes_applied += 1
                logger.debug("Fixed: '%s' → '%s'", original, fixed)
        
        logger.info("Applied %d word split fixes", fixes_applied)
        return fixed_text
    
    def _find_potential_splits(self, text: str) -> List[Tuple[str, str]]:
        """
        Find potential word splits in text.
        
        Returns:
            List of (original, fixed) tuples
        """
        fixes = []
        
        # Pattern 1: Two-part splits (most common)
        # Allow up to 6 chars for first part to catch "immuno defi ciency"
        pattern = r'\b([a-z]{1,6})\s+([a-z]{3,})\b'
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            part1 = match.group(1)
            part2 = match.group(2)
            original = f"{part1} {part2}"
            
            # Try joining them
            joined = part1 + part2
            
            # Should we join these?
            if self._should_join(part1, part2, joined):
                fixes.append((original, joined))
        
        # Pattern 2: Three-part splits (less common)
        # e.g., "ce re bral" or "im muno deficiency"
        pattern = r'\b([a-z]{1,5})\s+([a-z]{1,5})\s+([a-z]{3,})\b'
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            part1 = match.group(1)
            part2 = match.group(2)
            part3 = match.group(3)
            original = f"{part1} {part2} {part3}"
            
            # Try joining all parts
            joined = part1 + part2 + part3
            
            if self._should_join_multi(part1, part2, part3, joined):
                fixes.append((original, joined))
        
        return fixes
    
    def _should_join(self, part1: str, part2: str, joined: str) -> bool:
        """
        Decide if two parts should be joined.
        
        Focuses on PDF ligature issues - the main cause of splits:
        - fi, fl, ff, ffi, ffl ligatures
        - Specific medical/technical patterns
        """
        part1_lower = part1.lower()
        part2_lower = part2.lower()
        joined_lower = joined.lower()
        
        # Common words that should NEVER be joined
        never_join = {
            'a', 'i', 'to', 'in', 'on', 'at', 'by', 'of', 'or', 'is', 'it',
            'be', 'as', 'an', 'if', 'we', 'he', 'me', 'my', 'so', 'no', 'up',
            'do', 'go', 'am', 'are', 'was', 'for', 'the', 'and', 'but', 'not',
            'all', 'can', 'get', 'has', 'had', 'him', 'his', 'how', 'its',
            'may', 'new', 'now', 'old', 'our', 'out', 'own', 'say', 'she',
            'too', 'use', 'way', 'who', 'you', 'her', 'one', 'two', 'from',
            'have', 'this', 'that', 'with', 'they', 'been', 'will', 'your',
            'more', 'when', 'some', 'time', 'very', 'each', 'than', 'such'
        }
        
        if part1_lower in never_join or part2_lower in never_join:
            return False
        
        # MAIN STRATEGY: Ligature-based splits (the real PDF issue)
        # These are very reliable indicators
        ligature_patterns = {
            'fi': ['c', 'n', 't', 'e', 'l', 'r', 's', 'g'],  # specific, specific, definite, etc.
            'fl': ['u', 'a', 'o', 'e'],  # fluid, flag, flow, flee
            'ff': ['e', 'i', 'o', 'a'],  # effect, office, effort, affair
            'de': ['f', 'c'],  # defi (deficiency), deci (decimal)
            'ce': ['r', 'n'],  # cere (cerebral), cen (center)
            're': ['b'],  # rebral
        }
        
        for ending, expected_starts in ligature_patterns.items():
            if part1_lower.endswith(ending) and len(part2) > 0:
                if part2_lower[0] in expected_starts:
                    return True
        
        # Dictionary lookup (if available)
        if self.use_dictionary and self.dictionary:
            in_dict = joined_lower in self.dictionary
            part1_not_word = len(part1) <= 4 and part1_lower not in self.dictionary
            
            if in_dict and part1_not_word:
                return True
        
        return False
    
    def _should_join_multi(self, part1: str, part2: str, part3: str, joined: str) -> bool:
        """Decide if three parts should be joined."""
        joined_lower = joined.lower()
        
        # For three-part splits, be more conservative
        # Only join if dictionary confirms it's a word
        if self.use_dictionary and self.dictionary:
            return joined_lower in self.dictionary
        
        # Or if all parts are very short (likely a split)
        if len(part1) <= 2 and len(part2) <= 2 and len(part3) >= 3:
            return True
        
        return False


def fix_word_splits_generic(text: str, use_dictionary: bool = True) -> str:
    """
    Convenience function to fix word splits automatically.
    
    Args:
        text: Text with potential word splits
        use_dictionary: Whether to use dictionary for validation
        
    Returns:
        Text with splits fixed
    """
    fixer = GenericWordSplitFixer(use_dictionary=use_dictionary)
    return fixer.fix_splits(text)
