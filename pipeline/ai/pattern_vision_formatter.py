"""Pattern-based AI formatter that extracts formatting rules from PDF images."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional
from io import BytesIO

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from pdf2image import convert_from_path
    from PIL import Image
except ImportError:
    convert_from_path = None
    Image = None

from .config import OpenAIConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FormattingPattern:
    """A single formatting pattern/rule."""
    
    pattern_type: str  # 'text_match', 'position', 'style_detection'
    description: str  # Human-readable description
    conditions: Dict  # Conditions to match (e.g., starts_with, all_caps, etc.)
    formatting: Dict  # Formatting to apply (bold, italic, font_size, alignment, etc.)
    priority: int = 0  # Higher priority patterns are checked first


@dataclass(frozen=True)
class FormattingRules:
    """Collection of formatting patterns extracted from PDF."""
    
    patterns: List[FormattingPattern]
    metadata: Dict  # General info about the document style


def _convert_pdf_to_images(pdf_path: Path, max_pages: int = 7) -> List[str]:
    """
    Convert sample PDF pages to base64-encoded JPEG images.
    
    Uses smart sampling and compression:
    - Low DPI (72) for smaller file sizes
    - Resizes to max 1024px width
    - JPEG format with 85% quality
    - Samples from beginning, middle, and end
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum pages to sample (default 7)
    
    Returns:
        List of base64-encoded JPEG images
    """
    if convert_from_path is None or Image is None:
        raise RuntimeError(
            "pdf2image and Pillow are required. "
            "Install with: pip install pdf2image Pillow"
        )
    
    logger.info("Converting PDF sample pages to images for %s", pdf_path)
    
    # Get total page count
    from pdf2image.pdf2image import pdfinfo_from_path
    pdf_info = pdfinfo_from_path(pdf_path)
    total_pages = pdf_info.get("Pages", 0)
    
    logger.info("PDF has %d total pages", total_pages)
    
    # Smart sampling based on PDF size
    if total_pages <= max_pages:
        pages_to_sample = list(range(1, total_pages + 1))
    else:
        # Sample from beginning, middle, and end
        num_start = min(3, max_pages // 2)
        num_end = min(2, max_pages - num_start)
        num_middle = max_pages - num_start - num_end
        
        pages_to_sample = list(range(1, num_start + 1))
        
        if num_middle > 0:
            middle_start = total_pages // 3
            middle_end = (2 * total_pages) // 3
            step = (middle_end - middle_start) // num_middle if num_middle > 0 else 1
            for i in range(num_middle):
                page_num = middle_start + (i * step)
                if page_num not in pages_to_sample:
                    pages_to_sample.append(page_num)
        
        pages_to_sample.extend(range(total_pages - num_end + 1, total_pages + 1))
    
    pages_to_sample = sorted(set(pages_to_sample))
    logger.info("Sampling %d pages: %s", len(pages_to_sample), pages_to_sample)
    
    # Convert to compressed JPEG images
    TARGET_WIDTH = 1024
    JPEG_QUALITY = 85
    DPI = 72
    
    base64_images = []
    for page_num in pages_to_sample:
        images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=DPI)
        
        if images:
            image = images[0]
            
            # Resize if needed
            if image.width > TARGET_WIDTH:
                ratio = TARGET_WIDTH / image.width
                new_height = int(image.height * ratio)
                image = image.resize((TARGET_WIDTH, new_height), Image.Resampling.LANCZOS)
            
            # Convert to JPEG
            buffer = BytesIO()
            if image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = rgb_image
            
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.read()).decode("ascii")
            base64_images.append(img_base64)
            logger.debug("Converted page %d to JPEG", page_num)
    
    total_size_kb = sum(len(base64.b64decode(img)) / 1024 for img in base64_images)
    logger.info("Converted %d pages to images (%.1f KB total)", len(base64_images), total_size_kb)
    
    return base64_images


class PatternVisionFormatter:
    """Extract formatting patterns from PDF images using GPT-4o Vision."""
    
    def __init__(self, settings: OpenAIConfig):
        if OpenAI is None:
            raise RuntimeError(
                "The `openai` package is required. "
                "Install with: pip install openai"
            )
        
        client_kwargs = {"api_key": settings.api_key}
        if settings.base_url:
            client_kwargs["base_url"] = settings.base_url
        self._client = OpenAI(**client_kwargs)
        self._model = settings.model
    
    def extract_formatting_patterns(
        self,
        pdf_path: Path,
        output_dir: Path,
    ) -> FormattingRules:
        """
        Extract formatting patterns from PDF images.
        
        Returns a set of rules that can be applied to ANY text, not just specific lines.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save the formatting rules JSON
        
        Returns:
            FormattingRules object containing patterns
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert PDF pages to images
        logger.info("Extracting formatting patterns from %s", pdf_path)
        image_base64_list = _convert_pdf_to_images(pdf_path, max_pages=7)
        
        # Build content for API call (images only, no full text!)
        content = [
            {
                "type": "text",
                "text": (
                    "Analyze these PDF pages and identify FORMATTING PATTERNS and RULES.\n\n"
                    "Your task is to identify patterns that can be applied to format ANY similar document, "
                    "such as:\n"
                    "- Chapter headings (e.g., lines starting with 'Chapter' + number)\n"
                    "- Section headings (e.g., all caps lines, numbered sections)\n"
                    "- Regular paragraphs (alignment, indentation)\n"
                    "- Special text (bold, italic patterns)\n"
                    "- Lists (bulleted, numbered)\n"
                    "- Quotes or special blocks\n\n"
                    "Focus on PATTERNS that repeat throughout the document, not specific text content."
                ),
            }
        ]
        
        # Add images
        for img_base64 in image_base64_list:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
            })
        
        # Define the schema for pattern-based response
        schema = {
            "name": "FormattingPatterns",
            "schema": {
                "type": "object",
                "properties": {
                    "patterns": {
                        "type": "array",
                        "description": "List of formatting patterns/rules identified in the document",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pattern_type": {
                                    "type": "string",
                                    "enum": ["chapter_heading", "section_heading", "paragraph", "list_item", 
                                            "quote", "caption", "header", "footer", "special_text"],
                                    "description": "Type of content this pattern applies to"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Human-readable description of this pattern"
                                },
                                "conditions": {
                                    "type": "object",
                                    "description": "Conditions that identify when this pattern applies",
                                    "properties": {
                                        "starts_with": {"type": "string"},
                                        "contains": {"type": "string"},
                                        "all_caps": {"type": "boolean"},
                                        "has_number": {"type": "boolean"},
                                        "position": {"type": "string", "enum": ["start", "middle", "end", "any"]},
                                        "min_length": {"type": "integer"},
                                        "max_length": {"type": "integer"},
                                        "regex_pattern": {"type": "string"}
                                    }
                                },
                                "formatting": {
                                    "type": "object",
                                    "description": "Formatting to apply when pattern matches",
                                    "properties": {
                                        "bold": {"type": "boolean"},
                                        "italic": {"type": "boolean"},
                                        "underline": {"type": "boolean"},
                                        "font_size": {"type": "number"},
                                        "alignment": {"type": "string", "enum": ["left", "center", "right", "justify"]},
                                        "indent_first_line": {"type": "number"},
                                        "indent_left": {"type": "number"},
                                        "spacing_before": {"type": "number"},
                                        "spacing_after": {"type": "number"},
                                        "font_family": {"type": "string"}
                                    }
                                },
                                "priority": {
                                    "type": "integer",
                                    "description": "Priority (higher = check first). Default 0.",
                                    "default": 0
                                }
                            },
                            "required": ["pattern_type", "description", "conditions", "formatting"]
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "description": "General information about document style",
                        "properties": {
                            "default_font": {"type": "string"},
                            "default_font_size": {"type": "number"},
                            "default_alignment": {"type": "string"},
                            "has_page_numbers": {"type": "boolean"},
                            "has_headers": {"type": "boolean"},
                            "has_footers": {"type": "boolean"},
                            "general_style": {"type": "string"}
                        }
                    }
                },
                "required": ["patterns", "metadata"]
            }
        }
        
        # Call OpenAI API
        logger.info("Requesting formatting patterns from GPT-4o Vision")
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert document formatter analyzing PDF layouts. "
                        "Identify formatting PATTERNS and RULES that can be applied to similar documents. "
                        "Focus on repeating patterns like chapter headings, section titles, paragraph styles, etc. "
                        "Return patterns that are general enough to apply to any text matching the conditions, "
                        "not specific to individual lines of text. "
                        f"\n\nExpected JSON format:\n{json.dumps(schema['schema'], indent=2)}"
                    ),
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
            response_format={"type": "json_object"},
        )
        
        # Extract and parse response
        payload = self._extract_json_payload(response)
        
        # Save the raw JSON
        rules_path = output_dir / "formatting_patterns.json"
        rules_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved formatting patterns to %s", rules_path)
        
        # Convert to FormattingRules object
        patterns = []
        for p in payload.get("patterns", []):
            pattern = FormattingPattern(
                pattern_type=p.get("pattern_type", "paragraph"),
                description=p.get("description", ""),
                conditions=p.get("conditions", {}),
                formatting=p.get("formatting", {}),
                priority=p.get("priority", 0)
            )
            patterns.append(pattern)
        
        # Sort by priority (highest first)
        patterns.sort(key=lambda p: p.priority, reverse=True)
        
        rules = FormattingRules(
            patterns=patterns,
            metadata=payload.get("metadata", {})
        )
        
        logger.info("Extracted %d formatting patterns", len(patterns))
        return rules
    
    def _extract_json_payload(self, response: object) -> Dict:
        """Extract JSON from API response."""
        try:
            if hasattr(response, 'choices') and response.choices:
                message = response.choices[0].message
                if hasattr(message, 'content') and message.content:
                    return json.loads(message.content)
        except Exception as exc:
            logger.error("Failed to extract JSON from response: %s", exc)
            raise
        
        raise RuntimeError("Could not extract valid JSON from API response")
