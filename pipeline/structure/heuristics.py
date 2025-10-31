from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Iterable, List, Optional, Sequence

from lxml import etree

# Import PyPDF2 for bookmark extraction (fallback to older name if needed)
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None

logger = logging.getLogger(__name__)


@dataclass
class TextSegment:
    text: str
    left: float
    width: float
    font_size: float


@dataclass
class Line:
    page_num: int
    page_width: float
    page_height: float
    top: float
    left: float
    height: float
    font_size: float
    text: str = ""
    segments: List[TextSegment] = field(default_factory=list)

    @property
    def right(self) -> float:
        return max((seg.left + seg.width) for seg in self.segments) if self.segments else self.left

    @property
    def column_positions(self) -> List[float]:
        """Return the canonical left positions for text columns within the line."""

        positions: List[float] = []
        tolerance = 6.0
        for segment in sorted(self.segments, key=lambda s: s.left):
            placed = False
            for idx, value in enumerate(positions):
                if abs(value - segment.left) <= tolerance:
                    # Smooth the column position to absorb minor jitter
                    positions[idx] = (positions[idx] + segment.left) / 2.0
                    placed = True
                    break
            if not placed:
                positions.append(segment.left)
        return sorted(positions)


def _clean_join(segments: Sequence[TextSegment]) -> str:
    parts: List[str] = []
    for segment in sorted(segments, key=lambda s: s.left):
        text = segment.text
        if not text:
            continue
        if parts and not parts[-1].endswith(" ") and not text.startswith(" "):
            parts.append(" ")
        parts.append(text)
    return "".join(parts)


def _parse_lines(page: etree._Element, fontspecs: dict) -> List[Line]:
    nodes = sorted(
        [
            (
                float(node.get("top", "0")),
                float(node.get("left", "0")),
                node,
            )
            for node in page.findall("text")
        ],
        key=lambda item: (item[0], item[1]),
    )

    lines: List[Line] = []
    tolerance = 2.0
    for top, left, node in nodes:
        content = "".join(node.itertext())
        if not content.strip():
            continue
        font_id = node.get("font")
        fontspec = fontspecs.get(font_id, {})
        font_size = float(fontspec.get("size", node.get("size", 0)) or 0)
        width = float(node.get("width", "0"))
        height = float(node.get("height", "0"))
        segment = TextSegment(text=content, left=left, width=width, font_size=font_size)

        if lines and abs(lines[-1].top - top) <= tolerance:
            line = lines[-1]
            line.segments.append(segment)
            line.left = min(line.left, left)
            line.height = max(line.height, height)
            if segment.font_size:
                line.font_size = max(line.font_size, segment.font_size)
        else:
            lines.append(
                Line(
                    page_num=int(page.get("number", "0") or 0),
                    page_width=float(page.get("width", "0") or 0),
                    page_height=float(page.get("height", "0") or 0),
                    top=top,
                    left=left,
                    height=height,
                    font_size=font_size,
                    segments=[segment],
                )
            )

    for line in lines:
        line.text = _clean_join(line.segments)
        if not line.font_size and line.segments:
            line.font_size = max(seg.font_size for seg in line.segments if seg.font_size)
    return [line for line in lines if line.text.strip()]


def _line_gap(prev_line: Line, next_line: Line) -> float:
    return next_line.top - prev_line.top


def _is_header_footer(line: Line) -> bool:
    text = line.text.strip()
    if not text:
        return True
    if len(text) <= 4 and text.isdigit():
        # Page number centred near bottom/top
        if line.page_height and (
            line.top < line.page_height * 0.08 or line.top > line.page_height * 0.9
        ):
            return True
    if len(text) <= 30 and text.lower().startswith("copyright"):
        return True
    return False


def _body_font_size(lines: Sequence[Line]) -> float:
    if not lines:
        return 12.0
    samples = [line.font_size for line in lines if len(line.text.strip()) >= 30 and line.font_size]
    if not samples:
        samples = [line.font_size for line in lines if line.font_size]
    if not samples:
        return 12.0
    return float(median(samples))


CHAPTER_KEYWORD_RE = re.compile(r"\bchapter\b", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^(chapter|chap\.|unit|lesson|module)\b", re.IGNORECASE)
TOC_RE = re.compile(r"^table of contents$", re.IGNORECASE)
INDEX_RE = re.compile(r"^index\b", re.IGNORECASE)
SECTION_RE = re.compile(r"^(section|sec\.|part)\b", re.IGNORECASE)
CAPTION_RE = re.compile(r"^(figure|fig\.|table)\s+\d+", re.IGNORECASE)
ORDERED_LIST_RE = re.compile(r"^(?:\(?\d+[\.\)]|[A-Za-z][\.)])\s+")

HEADING_FONT_TOLERANCE = 1.0


def _get_bookmark_page_number(bookmark, reader) -> Optional[int]:
    """
    Try multiple methods to extract page number from a bookmark.
    
    Different PDFs and PyPDF2 versions store bookmark destinations differently.
    This function tries all known methods to maximize compatibility.
    
    Args:
        bookmark: Bookmark object from PyPDF2
        reader: PdfReader instance
    
    Returns:
        Page number (0-indexed) or None if not found
    """
    # Method 1: Try the .page attribute (most common)
    try:
        if hasattr(bookmark, 'page') and bookmark.page is not None:
            return reader.pages.index(bookmark.page)
    except Exception:
        pass
    
    # Method 2: Try accessing as dictionary with '/Page' key
    try:
        if isinstance(bookmark, dict) and '/Page' in bookmark:
            page_obj = bookmark['/Page']
            return reader.pages.index(page_obj)
    except Exception:
        pass
    
    # Method 3: Try get_destination() method (older PyPDF2 versions)
    try:
        if hasattr(bookmark, 'get_destination'):
            dest = bookmark.get_destination()
            if dest and hasattr(dest, 'page'):
                return reader.pages.index(dest.page)
    except Exception:
        pass
    
    # Method 4: Try dictionary-style access for destination
    try:
        if hasattr(bookmark, '__getitem__'):
            dest = bookmark['/Dest']
            if dest:
                # Destination can be an array [page, /XYZ, left, top, zoom]
                if isinstance(dest, list) and len(dest) > 0:
                    page_ref = dest[0]
                    return reader.pages.index(page_ref)
    except Exception:
        pass
    
    # Method 5: Try named destinations
    try:
        if hasattr(reader, 'named_destinations'):
            # Some bookmarks reference named destinations
            if hasattr(bookmark, 'title'):
                for name, dest in reader.named_destinations.items():
                    if hasattr(dest, 'page'):
                        # This is a guess - named destinations don't always match titles
                        return reader.pages.index(dest.page)
    except Exception:
        pass
    
    return None

"""
def _extract_bookmark_page_ranges(pdf_path: str) -> Optional[List[dict]]:
"""
"""
    Extract level 0 (top-level) bookmarks from PDF with their page ranges.
    
    This is the PRIMARY method for chapter detection - only falls back to 
    heuristics if bookmarks are not available.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        List of bookmark dictionaries with 'title', 'start_page', 'end_page'
        Returns None if bookmarks cannot be extracted
"""
"""
    if PdfReader is None:
        logger.info("📚 PyPDF2/pypdf not available - skipping bookmark extraction")
        return None
    
    try:
        reader = PdfReader(pdf_path)
        outlines = reader.outline
        total_pages = len(reader.pages)
        
        if not outlines:
            logger.info("📚 No bookmarks found in PDF - will use heuristic detection")
            return None
        
        # Collect level 0 (top-level) bookmarks only
        level_0_bookmarks = []
        
        for item in outlines:
            # Level 0 bookmarks are NOT nested in lists
            # If item is a list, it contains nested sub-bookmarks - skip it
            if isinstance(item, list):
                continue
            
            # This is a level 0 bookmark
            if not hasattr(item, 'title'):
                continue
                
            title = item.title
            
            # Get the starting page number using robust method
            start_page = _get_bookmark_page_number(item, reader)
            
            if start_page is not None:
                level_0_bookmarks.append({
                    'title': title,
                    'start_page': start_page,  # 0-indexed
                })
            else:
                logger.warning(f"Could not extract page for bookmark '{title}': no valid page reference found")
                continue
        
        if not level_0_bookmarks:
            logger.info("📚 No valid level 0 bookmarks found - will use heuristic detection")
            return None
        
        # ═══════════════════════════════════════════════════════════════
        # FILTER: Only keep bookmarks that look like actual chapters
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"📚 Found {len(level_0_bookmarks)} level 0 bookmarks total")
        
        # Filter to only keep bookmarks starting with "Chapter" (case-insensitive)
        chapter_bookmarks = []
        non_chapter_bookmarks = []
        
        for bm in level_0_bookmarks:
            title = bm['title'].strip()
            # Check if this looks like a chapter heading
            if re.match(r'^Chapter\s+\d+', title, re.IGNORECASE):
                chapter_bookmarks.append(bm)
            else:
                non_chapter_bookmarks.append(title)
        
        if not chapter_bookmarks:
            logger.warning("⚠️  No chapter bookmarks found after filtering")
            logger.warning("   (Looking for bookmarks starting with 'Chapter N:')")
            logger.warning("   Falling back to heuristic chapter detection")
            return None
        
        logger.info(f"✅ Filtered to {len(chapter_bookmarks)} CHAPTER bookmarks only")
        logger.info(f"   (Ignored {len(non_chapter_bookmarks)} non-chapter bookmarks)")
        
        # Show a few examples of what was filtered out
        if non_chapter_bookmarks:
            logger.info("   📝 Examples of ignored bookmarks:")
            for title in non_chapter_bookmarks[:5]:
                logger.info(f"      • {title}")
            if len(non_chapter_bookmarks) > 5:
                logger.info(f"      ... and {len(non_chapter_bookmarks) - 5} more")
        
        # Use the filtered chapter bookmarks from here on
        level_0_bookmarks = chapter_bookmarks
        
        # Calculate ending pages
        # Each bookmark ends where the next one starts (minus 1)
        for i in range(len(level_0_bookmarks)):
            if i < len(level_0_bookmarks) - 1:
                # Not the last bookmark - ends where next one starts
                level_0_bookmarks[i]['end_page'] = level_0_bookmarks[i + 1]['start_page'] - 1
            else:
                # Last bookmark - ends at the end of the document
                level_0_bookmarks[i]['end_page'] = total_pages - 1
        
        logger.info(f"✅ Successfully extracted {len(level_0_bookmarks)} bookmarks from PDF")
        for bm in level_0_bookmarks:
            logger.info(f"   📖 '{bm['title']}': pages {bm['start_page']+1}-{bm['end_page']+1}")
        
        return level_0_bookmarks
    
    except Exception as e:
        logger.warning(f"❌ Error extracting bookmarks from PDF: {e}")
        logger.info("📚 Will use heuristic detection instead")
        return None
"""

def _create_blocks_from_bookmarks(
    bookmark_ranges: List[dict],
    pdfxml_path: str,
    config: dict
) -> Optional[List[dict]]:
    """
    Create chapter blocks based on PDF bookmarks.
    
    This converts bookmark page ranges into the block structure expected
    by the rest of the pipeline.
    
    Args:
        bookmark_ranges: List of bookmarks with start_page and end_page
        pdfxml_path: Path to the PDF XML file (to get page dimensions)
        config: Configuration dict
    
    Returns:
        List of blocks with chapter labels, or None if conversion fails
    """
    try:
        tree = etree.parse(pdfxml_path)
        root = tree.getroot()
        
        # Build a mapping of page numbers to page elements (for dimensions)
        pages = {}
        for page in root.findall(".//page"):
            page_num = int(page.get("number", "0"))
            pages[page_num] = page
        
        blocks = []
        
        for bm in bookmark_ranges:
            title = bm['title']
            start_page = bm['start_page']
            end_page = bm['end_page']
            
            # Get page dimensions from the first page of this chapter
            page_elem = pages.get(start_page)
            if page_elem is not None:
                page_width = float(page_elem.get("width", "612") or "612")
                page_height = float(page_elem.get("height", "792") or "792")
            else:
                page_width = 612.0
                page_height = 792.0
            
            # Create a chapter block
            # Note: We use page_num as the start page where this chapter begins
            block = {
                "label": "chapter",
                "text": title,
                "page_num": start_page,  # 0-indexed page number
                "bbox": {
                    "top": 0.0,
                    "left": 0.0,
                    "width": page_width,
                    "height": 72.0,  # Approximate heading height
                },
                "font_size": 18.0,  # Default chapter heading size
                "bookmark_based": True,  # Flag to indicate this came from bookmarks
                "end_page": end_page,  # Store the ending page for reference
            }
            blocks.append(block)
        
        logger.info(f"✅ Created {len(blocks)} chapter blocks from bookmarks")
        return blocks
    
    except Exception as e:
        logger.error(f"❌ Error creating blocks from bookmarks: {e}")
        return None


def _inject_bookmark_chapters(blocks: List[dict], bookmark_ranges: List[dict]) -> List[dict]:
    """
    Inject bookmark-based chapter headings into the blocks at appropriate positions.
    
    This function:
    1. Removes heuristically-detected chapter headings (to avoid duplicates)
    2. Inserts bookmark-based chapter headings at the correct page numbers
    3. Preserves all other content blocks (paragraphs, figures, etc.)
    
    Args:
        blocks: List of all content blocks (from heuristic extraction)
        bookmark_ranges: List of bookmark dictionaries with title, start_page, end_page
    
    Returns:
        Updated list of blocks with bookmark-based chapter headings
    """
    logger.info(f"🔄 Injecting {len(bookmark_ranges)} bookmark-based chapters into {len(blocks)} blocks")
    
    # Step 1: Remove heuristically-detected chapter headings
    # Keep everything else (paragraphs, sections, figures, etc.)
    filtered_blocks = []
    removed_chapters = 0
    
    for block in blocks:
        if block.get("label") == "chapter":
            # Remove heuristic chapter headings - we'll replace with bookmark-based ones
            removed_chapters += 1
            logger.debug(f"   Removing heuristic chapter: '{block.get('text', '')[:50]}'")
            continue
        filtered_blocks.append(block)
    
    if removed_chapters > 0:
        logger.info(f"   📝 Removed {removed_chapters} heuristically-detected chapter headings")
    
    # Step 2: Create chapter heading blocks from bookmarks
    bookmark_chapter_blocks = []
    
    for bm in bookmark_ranges:
        title = bm['title']
        start_page = bm['start_page']
        end_page = bm['end_page']
        
        # Create a chapter heading block
        chapter_block = {
            "label": "chapter",
            "text": title,
            "page_num": start_page,  # 0-indexed
            "bbox": {
                "top": 0.0,
                "left": 0.0,
                "width": 612.0,
                "height": 72.0,
            },
            "font_size": 18.0,  # Default chapter heading size
            "bookmark_based": True,  # Flag to indicate source
            "end_page": end_page,  # Store ending page
        }
        bookmark_chapter_blocks.append(chapter_block)
    
    # Step 3: Merge blocks - insert chapter headings at correct positions
    # Sort all blocks by page number first
    all_blocks_to_sort = filtered_blocks + bookmark_chapter_blocks
    
    # Sort by page number, then by vertical position (top)
    # Chapter headings should come first on their page (top=0.0)
    sorted_blocks = sorted(
        all_blocks_to_sort,
        key=lambda b: (
            b.get("page_num", 0),
            b.get("bbox", {}).get("top", 0.0)
        )
    )
    
    logger.info(f"   ✅ Merged {len(filtered_blocks)} content blocks with {len(bookmark_chapter_blocks)} bookmark chapters")
    logger.info(f"   📖 Result: {len(sorted_blocks)} total blocks")
    
    return sorted_blocks


def _looks_like_book_title(line: Line, body_size: float) -> bool:
    text = line.text.strip()
    if not text or line.page_num > 2:
        return False
    if line.top > line.page_height * 0.45 if line.page_height else line.top > 400:
        return False
    if line.font_size >= body_size + 6:
        return True
    if line.font_size >= body_size + 4 and len(text.split()) <= 12:
        return True
    return False


def _collect_multiline_book_title(
    entries: Sequence[dict], start_idx: int, body_size: float
) -> tuple[list[Line], int]:
    """Collect consecutive lines that belong to the book title block."""

    first_entry = entries[start_idx]
    assert first_entry["kind"] == "line"
    first_line = first_entry["line"]
    heading_lines = [first_line]
    lookahead_idx = start_idx + 1

    while lookahead_idx < len(entries):
        next_entry = entries[lookahead_idx]
        if next_entry["kind"] != "line":
            break
        next_line = next_entry["line"]
        if _is_header_footer(next_line):
            break
        text = next_line.text.strip()
        if not text:
            break
        if text.lower() == "table of contents":
            break

        same_page = next_line.page_num == first_line.page_num
        similar_font = False
        if first_line.font_size and next_line.font_size:
            similar_font = (
                abs(next_line.font_size - first_line.font_size) <= HEADING_FONT_TOLERANCE
            )

        if same_page and (similar_font or _looks_like_book_title(next_line, body_size)):
            heading_lines.append(next_line)
            lookahead_idx += 1
            continue

        break

    return heading_lines, lookahead_idx
def _has_heading_font(line: Line, body_size: float) -> bool:
    if not line.font_size:
        return False
    return line.font_size >= body_size + 2.0


def _looks_like_chapter_heading(line: Line, body_size: float) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if CHAPTER_KEYWORD_RE.search(text):
        return _has_heading_font(line, body_size)
    if CHAPTER_RE.match(text):
        return _has_heading_font(line, body_size)
    if not _has_heading_font(line, body_size):
        return False
    if line.page_height and line.top <= line.page_height * 0.45:
        return True
    if len(text.split()) <= 10:
        return True
    return False


def _collect_multiline_heading(
    entries: Sequence[dict], start_idx: int, body_size: float
) -> tuple[list[Line], int]:
    first_entry = entries[start_idx]
    assert first_entry["kind"] == "line"
    first_line = first_entry["line"]
    base_font = first_line.font_size
    heading_lines = [first_line]
    lookahead_idx = start_idx + 1

    while lookahead_idx < len(entries):
        next_entry = entries[lookahead_idx]
        if next_entry["kind"] != "line":
            break
        next_line = next_entry["line"]
        if _is_header_footer(next_line):
            break
        text = next_line.text.strip()
        if not text:
            break
        if base_font and next_line.font_size:
            if abs(next_line.font_size - base_font) <= HEADING_FONT_TOLERANCE:
                heading_lines.append(next_line)
                lookahead_idx += 1
                continue
        break

    return heading_lines, lookahead_idx


def _is_index_heading(line: Line, body_size: float) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if not INDEX_RE.match(text):
        return False
    return _has_heading_font(line, body_size)


def _looks_like_section_heading(line: Line, body_size: float) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if SECTION_RE.match(text):
        return True
    if line.font_size >= body_size + 1.5 and len(text.split()) <= 14:
        return True
    if len(text.split()) <= 8 and text.isupper() and line.font_size >= body_size:
        return True
    return False


def _looks_like_caption(line: Line) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if CAPTION_RE.match(text):
        return True
    return False


def _is_list_item(text: str, mapping: dict) -> tuple[bool, str, str]:
    stripped = text.lstrip()
    pdf_cfg = mapping.get("pdf", {})
    markers = pdf_cfg.get("list_markers", [])
    for marker in markers:
        if stripped.startswith(marker):
            remainder = stripped[len(marker) :].strip()
            return True, "itemized", remainder or text.strip()
    if ORDERED_LIST_RE.match(stripped):
        remainder = ORDERED_LIST_RE.sub("", stripped, count=1).strip()
        return True, "ordered", remainder or stripped
    return False, "", text


def _should_merge(prev_line: Line, next_line: Line, body_size: float) -> bool:
    if prev_line.page_num != next_line.page_num:
        return False
    vertical_gap = _line_gap(prev_line, next_line)
    if vertical_gap > max(prev_line.height, next_line.height) * 1.9 + 2:
        return False
    indent_diff = abs(prev_line.left - next_line.left)
    if indent_diff > 60 and vertical_gap > min(prev_line.height, next_line.height) * 1.1:
        return False
    # Treat significant negative indent as new paragraph (hanging indent)
    if next_line.left - prev_line.left < -80:
        return False
    return True


def _finalize_paragraph(lines: Sequence[Line]) -> dict:
    text = "\n".join(line.text.strip() for line in lines).strip()
    left = min(line.left for line in lines)
    top = lines[0].top
    right = max(line.right for line in lines)
    bottom = max(line.top + line.height for line in lines)
    bbox = {"top": top, "left": left, "width": right - left, "height": bottom - top}
    font_size = max(line.font_size for line in lines if line.font_size)
    return {
        "label": "para",
        "text": text,
        "page_num": lines[0].page_num,
        "bbox": bbox,
        "font_size": font_size,
    }


def _extract_table(lines: Sequence[Line], start_idx: int) -> tuple[dict, int] | None:
    rows: List[List[str]] = []
    column_positions: List[float] = []
    idx = start_idx
    min_rows = 2
    while idx < len(lines):
        line = lines[idx]
        cols = line.column_positions
        if len(cols) < 2:
            break
        if not column_positions:
            column_positions = cols
        elif len(cols) != len(column_positions):
            break
        elif any(abs(a - b) > 25 for a, b in zip(cols, column_positions)):
            break

        cells = [""] * len(column_positions)
        for segment in sorted(line.segments, key=lambda s: s.left):
            if not segment.text.strip():
                continue
            nearest = min(
                range(len(column_positions)),
                key=lambda idx_: abs(column_positions[idx_] - segment.left),
            )
            existing = cells[nearest]
            if existing:
                if not existing.endswith(" ") and not segment.text.startswith(" "):
                    existing += " "
                cells[nearest] = existing + segment.text
            else:
                cells[nearest] = segment.text.strip()
        rows.append([cell.strip() for cell in cells])
        idx += 1
        if idx < len(lines):
            gap = _line_gap(line, lines[idx])
            if gap > max(line.height, lines[idx].height) * 1.8:
                break

    if len(rows) >= min_rows:
        table_block = {
            "label": "table",
            "rows": rows,
            "page_num": lines[start_idx].page_num,
            "bbox": {
                "top": lines[start_idx].top,
                "left": min(column_positions) if column_positions else lines[start_idx].left,
                "width": (
                    (max(column_positions) - min(column_positions)) if column_positions else 0
                ),
                "height": lines[idx - 1].top - lines[start_idx].top + lines[idx - 1].height,
            },
            "text": "\n".join(" | ".join(row) for row in rows),
        }
        return table_block, idx
    return None


def _iter_page_entries(page: etree._Element, fontspecs: dict) -> Iterable[dict]:
    lines = _parse_lines(page, fontspecs)
    for line in lines:
        yield {"kind": "line", "line": line}

    for image in page.findall("image"):
        src = image.get("src")
        if not src:
            continue
        yield {
            "kind": "image",
            "image": {
                "src": src,
                "top": float(image.get("top", "0") or 0),
                "left": float(image.get("left", "0") or 0),
                "width": float(image.get("width", "0") or 0),
                "height": float(image.get("height", "0") or 0),
                "page_num": int(page.get("number", "0") or 0),
            },
        }


def label_blocks(pdfxml_path: str, mapping: dict, pdf_path: Optional[str] = None) -> List[dict]:
    """
    Label blocks in the PDF XML.
    
    Strategy:
    1. FIRST: Try to extract bookmarks from PDF (if pdf_path provided)
    2. FALLBACK: Use heuristic-based detection if bookmarks unavailable
    
    Args:
        pdfxml_path: Path to the PDF XML file
        mapping: Configuration mapping
        pdf_path: Optional path to the original PDF file (for bookmark extraction)
    
    Returns:
        List of labeled blocks
    """
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 1: Extract ALL content blocks from PDF
    # ═══════════════════════════════════════════════════════════════
    
    tree = etree.parse(pdfxml_path)
    fontspecs = {
        node.get("id"): {
            "id": node.get("id"),
            "size": node.get("size"),
            "family": node.get("family", ""),
        }
        for node in tree.findall(".//fontspec")
    }

    entries: List[dict] = []
    for page in tree.findall(".//page"):
        entries.extend(
            sorted(
                _iter_page_entries(page, fontspecs),
                key=lambda item: (
                    item["line"].top if item["kind"] == "line" else item["image"]["top"],
                    item["line"].left if item["kind"] == "line" else item["image"]["left"],
                ),
            )
        )

    lines = [item["line"] for item in entries if item["kind"] == "line"]
    body_size = _body_font_size(lines)
    logger.debug("Estimated body font size: %.2f", body_size)

    blocks: List[dict] = []
    current_para: List[Line] = []
    saw_book_title = False
    enforce_chapter_keyword = False
    in_index_section = False
    should_enforce_chapter_keyword = any(
        line_entry["kind"] == "line"
        and CHAPTER_KEYWORD_RE.search(line_entry["line"].text.strip())
        and _has_heading_font(line_entry["line"], body_size)
        for line_entry in entries
    )
    chapter_heading_font_size: Optional[float] = None
    idx = 0
    while idx < len(entries):
        entry = entries[idx]
        if entry["kind"] == "image":
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []
            image = entry["image"]
            blocks.append(
                {
                    "label": "figure",
                    "text": "",
                    "page_num": image["page_num"],
                    "src": image["src"],
                    "bbox": {
                        "top": image["top"],
                        "left": image["left"],
                        "width": image["width"],
                        "height": image["height"],
                    },
                }
            )
            idx += 1
            continue

        line = entry["line"]
        if _is_header_footer(line):
            idx += 1
            continue

        text = line.text.strip()
        if in_index_section and _has_heading_font(line, body_size):
            if _is_index_heading(line, body_size):
                # Stay within the index section without duplicating the heading.
                idx += 1
                continue
            if len(text) > 1:
                in_index_section = False
                continue
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []
            blocks.append(_finalize_paragraph([line]))
            idx += 1
            continue

        # Table detection works on the contiguous run of lines
        remaining_lines = [item["line"] for item in entries[idx:] if item["kind"] == "line"]
        if remaining_lines:
            table_candidate = _extract_table(remaining_lines, 0)
        else:
            table_candidate = None
        if table_candidate:
            table_block, consumed = table_candidate
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []
            blocks.append(table_block)
            # Advance idx by number of table lines consumed in entries list
            consumed_lines = 0
            advanced = 0
            while idx + advanced < len(entries) and consumed_lines < consumed:
                if entries[idx + advanced]["kind"] == "line":
                    consumed_lines += 1
                advanced += 1
            idx += advanced
            continue

        list_match, list_type, list_text = _is_list_item(text, mapping)

        if _is_index_heading(line, body_size):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []

            heading_lines, next_idx = _collect_multiline_heading(entries, idx, body_size)
            combined_text = "\n".join(
                heading_line.text.strip()
                for heading_line in heading_lines
                if heading_line.text.strip()
            )
            left = min(heading_line.left for heading_line in heading_lines)
            right = max(heading_line.right for heading_line in heading_lines)
            top = heading_lines[0].top
            bottom = max(
                heading_line.top + heading_line.height for heading_line in heading_lines
            )
            blocks.append(
                {
                    "label": "chapter",
                    "text": combined_text,
                    "page_num": heading_lines[0].page_num,
                    "bbox": {
                        "top": top,
                        "left": left,
                        "width": right - left,
                        "height": bottom - top,
                    },
                    "font_size": max(
                        heading_line.font_size for heading_line in heading_lines if heading_line.font_size
                    ),
                    "chapter_role": "index",
                }
            )
            in_index_section = True
            idx = next_idx
            continue

        if TOC_RE.match(text.lower()) and _has_heading_font(line, body_size):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []

            heading_lines, next_idx = _collect_multiline_heading(entries, idx, body_size)
            combined_text = "\n".join(
                heading_line.text.strip()
                for heading_line in heading_lines
                if heading_line.text.strip()
            )
            left = min(heading_line.left for heading_line in heading_lines)
            right = max(heading_line.right for heading_line in heading_lines)
            top = heading_lines[0].top
            bottom = max(
                heading_line.top + heading_line.height for heading_line in heading_lines
            )
            blocks.append(
                {
                    "label": "toc",
                    "text": combined_text,
                    "page_num": heading_lines[0].page_num,
                    "bbox": {
                        "top": top,
                        "left": left,
                        "width": right - left,
                        "height": bottom - top,
                    },
                    "font_size": max(
                        heading_line.font_size
                        for heading_line in heading_lines
                        if heading_line.font_size
                    ),
                }
            )
            idx = next_idx
            continue

        if not saw_book_title and _looks_like_book_title(line, body_size):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []

            heading_lines, next_idx = _collect_multiline_book_title(
                entries, idx, body_size
            )
            combined_text = "\n".join(
                heading_line.text.strip()
                for heading_line in heading_lines
                if heading_line.text.strip()
            )
            left = min(heading_line.left for heading_line in heading_lines)
            right = max(heading_line.right for heading_line in heading_lines)
            top = heading_lines[0].top
            bottom = max(
                heading_line.top + heading_line.height for heading_line in heading_lines
            )
            blocks.append(
                {
                    "label": "book_title",
                    "text": combined_text,
                    "page_num": heading_lines[0].page_num,
                    "bbox": {
                        "top": top,
                        "left": left,
                        "width": right - left,
                        "height": bottom - top,
                    },
                    "font_size": max(
                        heading_line.font_size
                        for heading_line in heading_lines
                        if heading_line.font_size
                    ),
                }
            )
            saw_book_title = True
            idx = next_idx
            continue

        if _looks_like_chapter_heading(line, body_size):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []

            heading_lines, lookahead_idx = _collect_multiline_heading(
                entries, idx, body_size
            )

            combined_text = "\n".join(
                heading_line.text.strip() for heading_line in heading_lines if heading_line.text.strip()
            )
            contains_chapter_keyword = any(
                CHAPTER_KEYWORD_RE.search(heading_line.text.strip())
                for heading_line in heading_lines
                if heading_line.text.strip()
            )
            demote_to_section = False

            allow_heading = True
            first_line = heading_lines[0]
            base_font = first_line.font_size or 0.0
            if (
                should_enforce_chapter_keyword
                and enforce_chapter_keyword
                and not contains_chapter_keyword
            ):
                allow_heading = False
            if contains_chapter_keyword and base_font:
                if chapter_heading_font_size is None:
                    chapter_heading_font_size = base_font
                elif abs(base_font - chapter_heading_font_size) > HEADING_FONT_TOLERANCE:
                    allow_heading = False
                else:
                    chapter_heading_font_size = base_font
            elif (
                chapter_heading_font_size is not None
                and should_enforce_chapter_keyword
                and enforce_chapter_keyword
            ):
                allow_heading = False
            if not allow_heading:
                demote_to_section = True

            if demote_to_section:
                blocks.append(
                    {
                        "label": "section",
                        "text": combined_text,
                        "page_num": heading_lines[0].page_num,
                        "bbox": {
                            "top": heading_lines[0].top,
                            "left": min(heading_line.left for heading_line in heading_lines),
                            "width": max(heading_line.right for heading_line in heading_lines)
                            - min(heading_line.left for heading_line in heading_lines),
                            "height": max(
                                heading_line.top + heading_line.height for heading_line in heading_lines
                            )
                            - heading_lines[0].top,
                        },
                        "font_size": max(
                            heading_line.font_size for heading_line in heading_lines if heading_line.font_size
                        ),
                    }
                )
                idx = lookahead_idx
                continue

            left = min(heading_line.left for heading_line in heading_lines)
            right = max(heading_line.right for heading_line in heading_lines)
            top = heading_lines[0].top
            bottom = max(heading_line.top + heading_line.height for heading_line in heading_lines)
            blocks.append(
                {
                    "label": "chapter",
                    "text": combined_text,
                    "page_num": heading_lines[0].page_num,
                    "bbox": {
                        "top": top,
                        "left": left,
                        "width": right - left,
                        "height": bottom - top,
                    },
                    "font_size": max(heading_line.font_size for heading_line in heading_lines),
                }
            )
            if contains_chapter_keyword:
                enforce_chapter_keyword = True
            idx = lookahead_idx
            continue

        if _looks_like_section_heading(line, body_size):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []
            blocks.append(
                {
                    "label": "section",
                    "text": text,
                    "page_num": line.page_num,
                    "bbox": {
                        "top": line.top,
                        "left": line.left,
                        "width": line.right - line.left,
                        "height": line.height,
                    },
                    "font_size": line.font_size,
                }
            )
            idx += 1
            continue

        if _looks_like_caption(line):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []
            blocks.append(
                {
                    "label": "caption",
                    "text": text,
                    "page_num": line.page_num,
                    "bbox": {
                        "top": line.top,
                        "left": line.left,
                        "width": line.right - line.left,
                        "height": line.height,
                    },
                    "font_size": line.font_size,
                }
            )
            idx += 1
            continue

        if list_match:
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []
            blocks.append(
                {
                    "label": "list_item",
                    "text": list_text,
                    "page_num": line.page_num,
                    "bbox": {
                        "top": line.top,
                        "left": line.left,
                        "width": line.right - line.left,
                        "height": line.height,
                    },
                    "font_size": line.font_size,
                    "list_type": list_type,
                }
            )
            idx += 1
            continue

        if not current_para:
            current_para = [line]
        elif _should_merge(current_para[-1], line, body_size):
            current_para.append(line)
        else:
            blocks.append(_finalize_paragraph(current_para))
            current_para = [line]
        idx += 1

    if current_para:
        blocks.append(_finalize_paragraph(current_para))


    # ═══════════════════════════════════════════════════════════════
    # STEP 2: If bookmarks exist, use them to mark chapter boundaries
    # ═══════════════════════════════════════════════════════════════
    # if pdf_path:
    #    bookmark_ranges = _extract_bookmark_page_ranges(pdf_path)
    #    
    #   if bookmark_ranges:
    #        logger.info("✅ Found bookmarks - using them to define chapter boundaries")
    #       blocks = _inject_bookmark_chapters(blocks, bookmark_ranges)
    #        logger.info("Labeled %s blocks (with bookmark-based chapters)", len(blocks))
    #        return blocks
    
    logger.info("Labeled %s blocks", len(blocks))
    return blocks

    