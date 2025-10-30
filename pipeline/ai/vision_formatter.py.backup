from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

try:  # pragma: no cover - optional dependency
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:  # pragma: no cover
    Document = None
    WD_ALIGN_PARAGRAPH = None

from .config import OpenAIConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FormattingResult:
    """Structured output from the formatting stage."""

    docx_path: Path
    instructions_path: Optional[Path]


def _normalise_tokens(text: str) -> list[str]:
    return text.split()


def _docx_text(docx_path: Path) -> str:
    if Document is None:
        raise RuntimeError("python-docx is required to validate DOCX output")

    document = Document(str(docx_path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)


def _extract_json_payload(response: object) -> Dict:
    """Extract the JSON payload from a Responses API result."""

    text_payload: Optional[str] = None

    if hasattr(response, "output_text") and response.output_text:  # type: ignore[attr-defined]
        text_payload = response.output_text
    else:  # pragma: no cover - defensive fallback for future SDK versions
        try:
            output = response.output  # type: ignore[attr-defined]
            if output:
                content = output[0].content[0]
                text_payload = content.text  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - best effort
            logger.debug("Unable to extract structured response; falling back to raw repr")

    if not text_payload:
        text_payload = str(response)

    try:
        return json.loads(text_payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - depends on remote service
        raise RuntimeError(f"Failed to parse model response: {exc}") from exc


class VisionFormatter:
    """Apply PDF visual formatting to plain text using the GPT-4o Vision model."""

    def __init__(self, settings: OpenAIConfig):
        if OpenAI is None:  # pragma: no cover - import guard
            raise RuntimeError(
                "The `openai` package is required for the AI formatting workflow. "
                "Install the optional dependencies listed in tools/requirements.txt."
            )

        client_kwargs = {"api_key": settings.api_key}
        if settings.base_url:
            client_kwargs["base_url"] = settings.base_url
        self._client = OpenAI(**client_kwargs)
        self._model = settings.model

    def apply_formatting(
        self,
        pdf_path: Path,
        plain_text: str,
        output_dir: Path,
    ) -> FormattingResult:
        """Create a formatted DOCX file from JSON instructions returned by the model."""

        if Document is None:  # pragma: no cover - import guard
            raise RuntimeError("python-docx is required to materialise formatting instructions")

        output_dir.mkdir(parents=True, exist_ok=True)

        pdf_bytes = Path(pdf_path).read_bytes()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")
        logger.info("Requesting GPT-4o vision formatting instructions for %s", pdf_path)

        schema = {
            "name": "FormattingInstructions",
            "schema": {
                "type": "object",
                "properties": {
                    "paragraphs": {
                        "type": "array",
                        "description": "Line-oriented formatting directives.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "line": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "1-indexed line number in the supplied plain text.",
                                },
                                "style": {
                                    "type": "string",
                                    "description": "Paragraph style name to apply.",
                                },
                                "alignment": {
                                    "type": "string",
                                    "enum": ["left", "right", "center", "justify"],
                                    "description": "Paragraph alignment to apply.",
                                },
                                "bold": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    "description": "Inclusive-exclusive character ranges to render bold.",
                                },
                                "italic": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    "description": "Inclusive-exclusive character ranges to render italic.",
                                },
                                "underline": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    "description": "Inclusive-exclusive character ranges to underline.",
                                },
                            },
                            "required": ["line"],
                        },
                    },
                    "notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional diagnostic notes.",
                    },
                },
                "required": ["paragraphs"],
            },
        }

        request_payload = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a meticulous document formatter. Use the reference PDF "
                            "to replicate visual styling in the supplied plain text without "
                            "altering any characters. Preserve the text exactly as provided; "
                            "do not add, remove, or rephrase words. Identify formatting "
                            "instructions only—do not return the formatted document itself. "
                            "Respond with JSON that references plain-text line numbers "
                            "(1-indexed) and provides paragraph style, alignment, and "
                            "character ranges requiring bold, italic, or underline styling."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": plain_text},
                    {
                        "type": "input_file",
                        "mime_type": "application/pdf",
                        "data": pdf_base64,
                    },
                ],
            },
        ]

        request_kwargs = {
            "model": self._model,
            "input": request_payload,
        }

        try:
            client_response = self._client.responses.create(
                **request_kwargs,
                response_format={"type": "json_schema", "json_schema": schema},
            )
        except TypeError as exc:  # pragma: no cover - depends on SDK version
            if "response_format" not in str(exc):
                raise
            logger.warning(
                "OpenAI SDK does not support 'response_format'; falling back to text parsing."
            )
            client_response = self._client.responses.create(**request_kwargs)

        payload = _extract_json_payload(client_response)
        instructions_path = output_dir / "formatting_instructions.json"
        instructions_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        docx_path = output_dir / "formatted_document.docx"
        _materialise_docx_from_instructions(plain_text, payload, docx_path)

        original_tokens = _normalise_tokens(plain_text)
        formatted_tokens = _normalise_tokens(_docx_text(docx_path))
        if original_tokens != formatted_tokens:
            raise ValueError(
                "Formatted document text diverges from source content; "
                "discarding AI output to honour fidelity requirements."
            )

        logger.info("AI formatting instructions materialised at %s", docx_path)
        return FormattingResult(docx_path=docx_path, instructions_path=instructions_path)


def _materialise_docx_from_instructions(
    plain_text: str,
    instructions: Dict,
    destination: Path,
) -> None:
    """Apply JSON formatting instructions to plain text and save a DOCX file."""

    if Document is None:  # pragma: no cover - handled earlier
        raise RuntimeError("python-docx is required to build DOCX files")

    lines = plain_text.splitlines()
    instructions_map = _build_instruction_map(instructions.get("paragraphs", []))

    document = Document()

    if lines:
        _populate_paragraph(document.paragraphs[0], lines[0], instructions_map.get(1))
        for index, line in enumerate(lines[1:], start=2):
            para = document.add_paragraph()
            _populate_paragraph(para, line, instructions_map.get(index))
    else:
        paragraph = document.paragraphs[0]
        _populate_paragraph(paragraph, "", None)

    document.save(destination)


def _build_instruction_map(entries: Iterable[Dict]) -> Dict[int, Dict]:
    mapping: Dict[int, Dict] = {}
    for entry in entries:
        try:
            line_number = int(entry.get("line"))
        except Exception:  # pragma: no cover - defensive guard
            logger.debug("Skipping malformed instruction without line number: %s", entry)
            continue
        if line_number < 1:
            logger.debug("Ignoring instruction with invalid line number %s", line_number)
            continue
        mapping[line_number] = entry
    return mapping


def _populate_paragraph(paragraph, text: str, entry: Optional[Dict]) -> None:
    paragraph.text = ""
    _apply_style(paragraph, entry)
    _apply_alignment(paragraph, entry)
    _apply_inline_styles(paragraph, text, entry)


def _apply_style(paragraph, entry: Optional[Dict]) -> None:
    if not entry:
        return
    style_name = entry.get("style")
    if not style_name:
        return
    try:
        paragraph.style = style_name
    except Exception:  # pragma: no cover - depends on available styles
        logger.debug("Unknown paragraph style requested: %s", style_name)


def _apply_alignment(paragraph, entry: Optional[Dict]) -> None:
    if not entry or not entry.get("alignment"):
        return
    if WD_ALIGN_PARAGRAPH is None:  # pragma: no cover - import guard
        return
    alignment_value = entry["alignment"].lower()
    mapping = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    target = mapping.get(alignment_value)
    if target is None:
        logger.debug("Unsupported alignment requested: %s", alignment_value)
        return
    paragraph.alignment = target


def _apply_inline_styles(paragraph, text: str, entry: Optional[Dict]) -> None:
    ranges = _collect_ranges(entry)
    segments = _segment_text(text, ranges)
    for segment_text, styles in segments:
        run = paragraph.add_run(segment_text)
        run.bold = "bold" in styles or None
        run.italic = "italic" in styles or None
        run.underline = "underline" in styles or None


def _collect_ranges(entry: Optional[Dict]) -> Dict[str, List[Tuple[int, int]]]:
    def _normalise(items: Optional[Iterable[Iterable[int]]]) -> List[Tuple[int, int]]:
        normalised: List[Tuple[int, int]] = []
        if not items:
            return normalised
        for pair in items:
            try:
                start, end = int(pair[0]), int(pair[1])
            except Exception:  # pragma: no cover - malformed instructions
                logger.debug("Skipping malformed inline range: %s", pair)
                continue
            if end <= start:
                continue
            normalised.append((start, end))
        return normalised

    ranges = {
        "bold": _normalise(entry.get("bold") if entry else None),
        "italic": _normalise(entry.get("italic") if entry else None),
        "underline": _normalise(entry.get("underline") if entry else None),
    }
    return ranges


def _segment_text(text: str, ranges: Dict[str, List[Tuple[int, int]]]) -> List[Tuple[str, set[str]]]:
    if not text:
        return [("", set())]

    boundaries = {0, len(text)}
    for style_ranges in ranges.values():
        for start, end in style_ranges:
            start = max(0, min(len(text), start))
            end = max(0, min(len(text), end))
            if start >= end:
                continue
            boundaries.add(start)
            boundaries.add(end)

    sorted_points = sorted(boundaries)
    segments: List[Tuple[str, set[str]]] = []
    for idx in range(len(sorted_points) - 1):
        start, end = sorted_points[idx], sorted_points[idx + 1]
        if start == end:
            continue
        segment_styles = {
            style
            for style, style_ranges in ranges.items()
            if _range_contains(style_ranges, start, end)
        }
        segments.append((text[start:end], segment_styles))

    if not segments:
        segments.append((text, set()))
    return segments


def _range_contains(ranges: Iterable[Tuple[int, int]], start: int, end: int) -> bool:
    for candidate_start, candidate_end in ranges:
        if candidate_start <= start and end <= candidate_end:
            return True
    return False
