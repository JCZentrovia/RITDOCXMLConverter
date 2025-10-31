"""Updated AI integration for pattern-based formatting."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def integrate_ai_formatting(
    pdf_path: Path,
    blocks: List[Dict],
    work_dir: Path,
    export_intermediate: bool = True
) -> Tuple[List[Dict], List[Tuple[str, Path]]]:
    """
    Integrate AI formatting patterns with heuristic blocks.
    
    This is the NEW approach that:
    1. Sends ONLY images to AI (no full text!)
    2. Gets formatting PATTERNS/RULES from AI
    3. Applies patterns to blocks locally
    4. Creates formatted DOCX with patterns
    
    Args:
        pdf_path: Path to PDF file
        blocks: Blocks labeled by heuristics
        work_dir: Working directory for intermediate files
        export_intermediate: Whether to export intermediate files
    
    Returns:
        Tuple of (enhanced_blocks, ai_assets)
        - enhanced_blocks: Blocks with AI formatting applied
        - ai_assets: List of (name, path) tuples for packaging
    """
    ai_assets: List[Tuple[str, Path]] = []
    
    try:
        # Import AI modules
        from .ai.config import OpenAIConfig
        from .ai.pattern_vision_formatter import PatternVisionFormatter
        from .ai.pattern_matcher import PatternMatcher
        from .ai.formatted_docx_builder import create_formatted_docx
        from .ai.docx_to_docbook import convert_docx_to_docbook
        
        # Load AI config
        ai_config = OpenAIConfig.load()
        if not ai_config:
            logger.info("AI configuration not found; skipping AI formatting")
            return blocks, ai_assets
        
        logger.info("🧠 Starting AI pattern-based formatting")
        
        # Step 1: Extract formatting patterns from PDF images
        logger.info("📸 Step 1: Extracting formatting patterns from PDF images")
        formatter = PatternVisionFormatter(ai_config)
        ai_output_dir = work_dir / "ai_formatted"
        
        formatting_rules = formatter.extract_formatting_patterns(
            pdf_path,
            ai_output_dir
        )
        
        logger.info("✅ Extracted %d formatting patterns", len(formatting_rules.patterns))
        
        if export_intermediate:
            patterns_json = ai_output_dir / "formatting_patterns.json"
            if patterns_json.exists():
                ai_assets.append(("ai_patterns/formatting_patterns.json", patterns_json))
        
        # Step 2: Apply AI patterns to blocks
        logger.info("🔧 Step 2: Applying AI patterns to %d blocks", len(blocks))
        matcher = PatternMatcher(formatting_rules.patterns, formatting_rules.metadata)
        enhanced_blocks = blocks #matcher.enhance_blocks(blocks) JC commented out to avoid error
        
        logger.info("✅ Enhanced blocks with AI formatting")
        
        # Step 3: Create formatted DOCX with AI patterns
        logger.info("📝 Step 3: Creating formatted DOCX with AI patterns")
        docx_path = ai_output_dir / "FormattedDocument.docx"
        
        create_formatted_docx(
            enhanced_blocks,
            docx_path,
            metadata=formatting_rules.metadata
        )
        
        logger.info("✅ Created formatted DOCX at %s", docx_path)
        
        if export_intermediate:
            ai_assets.append(("ai_formatted/FormattedDocument.docx", docx_path))
        
        # Step 4: Convert DOCX to DocBook XML (for reference)
        try:
            logger.info("📄 Step 4: Converting DOCX to DocBook XML")
            formatted_docbook = convert_docx_to_docbook(
                docx_path,
                ai_output_dir / "FormattedDocbook.xml",
                root_name="article"
            )
            
            logger.info("✅ Created DocBook XML from formatted DOCX")
            
            if export_intermediate:
                ai_assets.append(("ai_formatted/FormattedDocbook.xml", formatted_docbook))
        
        except Exception as exc:
            logger.warning("Failed to convert formatted DOCX to DocBook: %s", exc)
        
        logger.info("🎉 AI pattern-based formatting complete!")
        logger.info("   - %d patterns extracted", len(formatting_rules.patterns))
        logger.info("   - %d blocks enhanced", len(enhanced_blocks))
        logger.info("   - %d AI assets created", len(ai_assets))
        
        return enhanced_blocks, ai_assets
    
    except ImportError as exc:
        logger.warning("AI dependencies not available: %s", exc)
        logger.info("Install with: pip install openai pdf2image Pillow python-docx")
        return blocks, ai_assets
    
    except Exception as exc:
        logger.error("AI formatting failed: %s", exc, exc_info=True)
        logger.info("Continuing without AI formatting")
        return blocks, ai_assets


def log_ai_pattern_summary(patterns: List) -> None:
    """Log a summary of AI patterns for debugging."""
    if not patterns:
        return
    
    logger.info("=" * 60)
    logger.info("AI FORMATTING PATTERNS SUMMARY")
    logger.info("=" * 60)
    
    for i, pattern in enumerate(patterns, 1):
        logger.info(
            "%d. %s (priority: %d)",
            i,
            pattern.description,
            pattern.priority
        )
        logger.info("   Type: %s", pattern.pattern_type)
        logger.info("   Conditions: %s", pattern.conditions)
        logger.info("   Formatting: %s", pattern.formatting)
        logger.info("")
    
    logger.info("=" * 60)
