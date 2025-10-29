from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from statistics import median
from typing import Iterable, List, Sequence

from lxml import etree

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


CHAPTER_RE = re.compile(r"^(chapter|chap\.|unit|lesson|module)\b", re.IGNORECASE)
SECTION_RE = re.compile(r"^(section|sec\.|part)\b", re.IGNORECASE)
CAPTION_RE = re.compile(r"^(figure|fig\.|table)\s+\d+", re.IGNORECASE)
ORDERED_LIST_RE = re.compile(r"^(?:\(?\d+[\.\)]|[A-Za-z][\.)])\s+")

HEADING_FONT_TOLERANCE = 1.0


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


def _looks_like_chapter_heading(line: Line, body_size: float) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if CHAPTER_RE.match(text):
        return True
    if line.font_size >= body_size + 3:
        if line.page_height and line.top <= line.page_height * 0.45:
            return True
        if len(text.split()) <= 10:
            return True
    return False


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
    text = " ".join(line.text.strip() for line in lines).strip()
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


def label_blocks(pdfxml_path: str, mapping: dict) -> List[dict]:
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
        entries.extend(sorted(_iter_page_entries(page, fontspecs), key=lambda item: (
            item["line"].top if item["kind"] == "line" else item["image"]["top"],
            item["line"].left if item["kind"] == "line" else item["image"]["left"],
        )))

    lines = [item["line"] for item in entries if item["kind"] == "line"]
    body_size = _body_font_size(lines)
    logger.debug("Estimated body font size: %.2f", body_size)

    blocks: List[dict] = []
    current_para: List[Line] = []
    saw_book_title = False
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

        text = line.text.strip()
        list_match, list_type, list_text = _is_list_item(text, mapping)

        if not saw_book_title and _looks_like_book_title(line, body_size):
            if current_para:
                blocks.append(_finalize_paragraph(current_para))
                current_para = []

            heading_lines, next_idx = _collect_multiline_book_title(entries, idx, body_size)
            combined_text = " ".join(
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
                        heading_line.font_size for heading_line in heading_lines if heading_line.font_size
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

            heading_lines = [line]
            lookahead_idx = idx + 1
            while lookahead_idx < len(entries):
                next_entry = entries[lookahead_idx]
                if next_entry["kind"] != "line":
                    break
                next_line = next_entry["line"]
                if _is_header_footer(next_line):
                    break
                if not _looks_like_chapter_heading(next_line, body_size):
                    break
                heading_lines.append(next_line)
                lookahead_idx += 1

            combined_text = " ".join(
                heading_line.text.strip() for heading_line in heading_lines if heading_line.text.strip()
            )
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

    logger.info("Labeled %s blocks", len(blocks))
    return blocks
