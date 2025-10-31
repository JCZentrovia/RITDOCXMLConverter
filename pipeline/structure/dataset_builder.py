"""Utilities for building a supervised layout dataset from DocBook outputs.

This module inspects ConversionExamples and validated DocBook XML archives to
produce block-level examples that include text, geometry, styling heuristics and
DocBook (DCT) labels.  It is designed to be orchestrated by the
``tools/dataset/build_block_dataset.py`` CLI but is separated for unit testing
and reuse.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple
from zipfile import ZipFile

from lxml import etree

from .heuristics import label_blocks
from ..common import load_mapping
from ..extractors.poppler_pdfxml import pdftohtml_xml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocbookBlock:
    """Representation of a labelled DocBook block."""

    text: str
    label: str
    hierarchy: Tuple[str, ...]
    attrs: Dict[str, str]
    source: str


@dataclass(frozen=True)
class AlignedBlock:
    """Block example that combines PDF geometry with DocBook labels."""

    source_id: str
    page_num: int
    text: str
    geometry: Dict[str, float]
    styles: Dict[str, float]
    classifier_label: str
    classifier_confidence: Optional[float]
    dct_label: str
    hierarchy: Tuple[str, ...]
    docbook_attrs: Dict[str, str]


DOCBOOK_SECTION_TAGS = {
    "book",
    "chapter",
    "sect1",
    "sect2",
    "sect3",
    "sect4",
    "sect5",
    "section",
    "preface",
    "article",
}

DOCBOOK_BLOCK_TAGS = {
    "para",
    "simpara",
    "title",
    "listitem",
    "figure",
    "table",
    "informaltable",
    "equation",
    "blockquote",
}

# ``pdftohtml`` emits values in PDF points.  When we normalise bounding boxes we
# clamp to a sane range that LayoutLM models expect (0–1000).
class DatasetBuildError(RuntimeError):
    """Raised when an unrecoverable failure occurs while building the dataset."""


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _extract_text(node: etree._Element) -> str:
    text = " ".join(part.strip() for part in node.itertext()).strip()
    return re.sub(r"\s+", " ", text)


def _hierarchy_key(node: etree._Element) -> Tuple[str, ...]:
    segments: List[str] = []
    current = node
    while current is not None:
        if not isinstance(current.tag, str):
            current = current.getparent()  # type: ignore[attr-defined]
            continue
        tag = _strip_ns(current.tag)
        if tag in DOCBOOK_SECTION_TAGS:
            ident = current.get("id") or current.get("label") or _extract_text(current.find("title"))
            if ident:
                segments.append(f"{tag}:{ident}")
            else:
                segments.append(tag)
        current = current.getparent()  # type: ignore[attr-defined]
    return tuple(reversed(segments))


def _title_label(node: etree._Element) -> str:
    parent = node.getparent()  # type: ignore[attr-defined]
    parent_tag = _strip_ns(parent.tag) if parent is not None else "root"
    return f"{parent_tag}.title"


def _listitem_label(node: etree._Element) -> str:
    parent = node.getparent()  # type: ignore[attr-defined]
    parent_tag = _strip_ns(parent.tag) if parent is not None else "list"
    return f"{parent_tag}.item"


def _docbook_label(node: etree._Element) -> Optional[str]:
    if not isinstance(node.tag, str):
        return None
    tag = _strip_ns(node.tag)
    if tag not in DOCBOOK_BLOCK_TAGS:
        return None
    if tag == "title":
        return _title_label(node)
    if tag == "listitem":
        return _listitem_label(node)
    return tag


def _collect_docbook_blocks(tree: etree._ElementTree, source_name: str) -> List[DocbookBlock]:
    blocks: List[DocbookBlock] = []
    for node in tree.iter():
        label = _docbook_label(node)
        if not label:
            continue
        text = _extract_text(node)
        if not text:
            continue
        attrs = {key: value for key, value in node.attrib.items() if value}
        hierarchy = _hierarchy_key(node)
        blocks.append(
            DocbookBlock(
                text=text,
                label=label,
                hierarchy=hierarchy,
                attrs=attrs,
                source=source_name,
            )
        )
    return blocks


def load_docbook_blocks(zip_path: Path) -> List[DocbookBlock]:
    """Read DocBook XML files from an archive and return labelled blocks."""

    if not zip_path.exists():
        raise DatasetBuildError(f"DocBook archive missing: {zip_path}")

    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, recover=True)
    blocks: List[DocbookBlock] = []
    with ZipFile(zip_path) as zf:
        xml_names = [name for name in zf.namelist() if name.lower().endswith(".xml")]
        for name in sorted(xml_names):
            with zf.open(name) as fh:
                try:
                    tree = etree.parse(fh, parser=parser)
                except etree.XMLSyntaxError as exc:  # pragma: no cover - defensive
                    logger.warning("Skipping %s in %s due to XML syntax error: %s", name, zip_path, exc)
                    continue
            blocks.extend(_collect_docbook_blocks(tree, source_name=name))
    return blocks


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _align_single_block(
    pdf_block: dict,
    candidates: List[DocbookBlock],
    consumed: set[int],
    *,
    fuzzy_threshold: float,
) -> Tuple[Optional[DocbookBlock], float]:
    key = _normalize_for_match(pdf_block.get("text", ""))
    if not key:
        return None, 0.0

    for idx, candidate in enumerate(candidates):
        if idx in consumed:
            continue
        if _normalize_for_match(candidate.text) == key:
            consumed.add(idx)
            return candidate, 1.0

    # Fallback: try fuzzy matching
    best_ratio = 0.0
    best_idx: Optional[int] = None
    for idx, candidate in enumerate(candidates):
        if idx in consumed:
            continue
        candidate_key = _normalize_for_match(candidate.text)
        if not candidate_key:
            continue
        ratio = SequenceMatcher(None, key, candidate_key).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = idx
    if best_idx is not None and best_ratio >= fuzzy_threshold:
        consumed.add(best_idx)
        return candidates[best_idx], best_ratio
    return None, best_ratio


def _derive_styles(pdf_block: dict) -> Dict[str, float]:
    text = pdf_block.get("text", "")
    style = {
        "font_size": float(pdf_block.get("font_size") or 0.0),
        "char_count": float(len(text)),
        "line_count": float(text.count("\n") + 1 if text else 0),
    }
    return style


def _normalise_geometry(geometry: Optional[dict]) -> Dict[str, float]:
    if not geometry:
        return {"left": 0.0, "top": 0.0, "width": 0.0, "height": 0.0}
    left = float(geometry.get("left") or 0.0)
    top = float(geometry.get("top") or 0.0)
    width = float(geometry.get("width") or 0.0)
    height = float(geometry.get("height") or 0.0)
    return {"left": left, "top": top, "width": width, "height": height}


def align_blocks(
    pdf_blocks: Sequence[dict],
    docbook_blocks: Sequence[DocbookBlock],
    *,
    source_id: str,
    fuzzy_threshold: float = 0.84,
) -> List[AlignedBlock]:
    """Align heuristic PDF blocks with DocBook labels using text matching."""

    aligned: List[AlignedBlock] = []
    consumed: set[int] = set()
    for block in pdf_blocks:
        candidate, score = _align_single_block(block, list(docbook_blocks), consumed, fuzzy_threshold=fuzzy_threshold)
        if candidate is None:
            label = "unlabeled"
            hierarchy: Tuple[str, ...] = ()
            attrs: Dict[str, str] = {}
        else:
            label = candidate.label
            hierarchy = candidate.hierarchy
            attrs = candidate.attrs
        geometry = _normalise_geometry(block.get("bbox"))
        aligned.append(
            AlignedBlock(
                source_id=source_id,
                page_num=int(block.get("page_num") or 0),
                text=str(block.get("text", "")),
                geometry=geometry,
                styles=_derive_styles(block),
                classifier_label=str(block.get("label", "")),
                classifier_confidence=block.get("classifier_confidence"),
                dct_label=label,
                hierarchy=hierarchy,
                docbook_attrs=attrs,
            )
        )
    logger.debug("Aligned %s PDF blocks for %s", len(aligned), source_id)
    return aligned


def _ensure_pdfxml(pdf_path: Path, tmp_dir: Path) -> Path:
    pdfxml_path = tmp_dir / f"{pdf_path.stem}.pdfxml.xml"
    if pdfxml_path.exists():
        return pdfxml_path
    pdftohtml_xml(str(pdf_path), str(pdfxml_path))
    return pdfxml_path


def extract_pdf_blocks(pdf_path: Path, *, config_dir: Path, publisher: Optional[str] = None) -> List[dict]:
    """Run the PDF heuristics to obtain layout blocks."""

    if not pdf_path.exists():
        raise DatasetBuildError(f"PDF missing: {pdf_path}")

    mapping = load_mapping(config_dir, publisher)
    with TemporaryDirectoryPath(prefix="ritdoc_dataset_") as tmp_dir:
        pdfxml_path = _ensure_pdfxml(pdf_path, tmp_dir)
        blocks = label_blocks(str(pdfxml_path), mapping, pdf_path=str(pdf_path))
    return blocks


from tempfile import TemporaryDirectory


class TemporaryDirectoryPath:
    """Context manager returning a ``pathlib.Path`` instead of a string."""

    def __init__(self, prefix: str = "tmp") -> None:
        self._tmp = TemporaryDirectory(prefix=prefix)
        self.path = Path(self._tmp.name)

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tmp.cleanup()


def iter_conversion_examples(conversion_root: Path) -> Iterator[Tuple[str, Path, Path]]:
    """Yield (example_id, pdf_path, docbook_zip_path) tuples."""

    for directory in sorted(conversion_root.iterdir()):
        if not directory.is_dir():
            continue
        input_dir = directory / "Input"
        output_dir = directory / "Output"
        pdfs = sorted(input_dir.glob("*.pdf"))
        zips = sorted(output_dir.glob("*.zip"))
        if not pdfs or not zips:
            logger.debug("Skipping %s; expected PDF and ZIP output", directory)
            continue
        yield directory.name, pdfs[0], zips[0]


def build_dataset(
    conversion_root: Path,
    *,
    config_dir: Path,
    publisher: Optional[str] = None,
    fuzzy_threshold: float = 0.84,
    limit: Optional[int] = None,
    pdf_block_provider: Optional[callable] = None,
) -> List[AlignedBlock]:
    """Construct the aligned dataset for all conversion examples."""

    dataset: List[AlignedBlock] = []
    for idx, (example_id, pdf_path, zip_path) in enumerate(iter_conversion_examples(conversion_root)):
        if limit is not None and idx >= limit:
            break
        logger.info("Processing %s", example_id)
        docbook_blocks = load_docbook_blocks(zip_path)
        if pdf_block_provider is not None:
            pdf_blocks = pdf_block_provider(pdf_path, example_id)
        else:
            try:
                pdf_blocks = extract_pdf_blocks(pdf_path, config_dir=config_dir, publisher=publisher)
            except Exception as exc:  # pragma: no cover - depends on external tools
                logger.warning("Falling back to DocBook-only blocks for %s: %s", example_id, exc)
                pdf_blocks = [{
                    "text": block.text,
                    "bbox": None,
                    "page_num": 0,
                    "font_size": 0.0,
                    "label": block.label,
                    "classifier_confidence": None,
                } for block in docbook_blocks]
        dataset.extend(
            align_blocks(
                pdf_blocks,
                docbook_blocks,
                source_id=example_id,
                fuzzy_threshold=fuzzy_threshold,
            )
        )
    return dataset


def save_dataset_jsonl(examples: Sequence[AlignedBlock], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for example in examples:
            fh.write(json.dumps(example.__dict__, ensure_ascii=False) + "\n")
    logger.info("Wrote %s examples to %s", len(examples), output_path)


def summarise_dataset(examples: Sequence[AlignedBlock]) -> Dict[str, object]:
    label_counts: Dict[str, int] = {}
    for example in examples:
        label_counts[example.dct_label] = label_counts.get(example.dct_label, 0) + 1
    total = len(examples)
    entropy = 0.0
    for count in label_counts.values():
        p = count / max(total, 1)
        if p > 0:
            entropy -= p * math.log(p, 2)
    return {
        "total_examples": total,
        "label_distribution": label_counts,
        "label_entropy": entropy,
    }


def save_summary(summary: Dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


__all__ = [
    "AlignedBlock",
    "DatasetBuildError",
    "DocbookBlock",
    "align_blocks",
    "build_dataset",
    "iter_conversion_examples",
    "load_docbook_blocks",
    "save_dataset_jsonl",
    "summarise_dataset",
    "save_summary",
]
