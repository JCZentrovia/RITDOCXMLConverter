from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Dict, List

from lxml import etree

from .common import PageText, checksum, load_mapping, normalize_text
from .extractors.pdfminer_text import pdfminer_pages
from .extractors.poppler_pdfxml import pdftohtml_xml
from .extractors.poppler_text import pdftotext_pages
from .ocr.ocrmypdf_runner import ocr_pages
from .structure.classifier import classify_blocks
from .structure.heuristics import label_blocks
from .validators.counters import compute_metrics
from .validators.dtd_validator import validate_dtd

logger = logging.getLogger(__name__)


def _normalize_pages(pages: List[PageText], config: dict) -> None:
    for page in pages:
        events = []
        page.norm_text = normalize_text(page.raw_text, config, events)
        page.events = events
        page.checksum = checksum(page.norm_text)


def _detect_mismatches(primary: List[PageText], secondary: List[PageText], tolerances: Dict) -> List[int]:
    secondary_map = {p.page_num: p for p in secondary}
    mismatches: List[int] = []
    for page in primary:
        other = secondary_map.get(page.page_num)
        if other is None:
            mismatches.append(page.page_num)
            continue
        if page.norm_text != other.norm_text:
            mismatches.append(page.page_num)
            continue
        char_diff = abs(len(page.norm_text) - len(other.norm_text))
        if char_diff > tolerances.get("char_diff_per_page", 0):
            mismatches.append(page.page_num)
            continue
    return mismatches


def _image_only_pages(pages_a: List[PageText], pages_b: List[PageText]) -> List[int]:
    b_map = {p.page_num: p for p in pages_b}
    result = []
    for page in pages_a:
        other = b_map.get(page.page_num)
        if page.norm_text.strip():
            continue
        if other and other.norm_text.strip():
            continue
        result.append(page.page_num)
    return result


def _build_block_document(blocks: List[dict]) -> etree._Element:
    root = etree.Element("document")
    for block in blocks:
        element = etree.SubElement(root, "block", label=block.get("classifier_label") or block.get("label", "para"))
        element.text = block.get("text", "")
    return root


def _write_docbook(tree: etree._ElementTree, root_name: str, dtd_system: str, out_path: Path) -> None:
    xml_bytes = etree.tostring(tree, encoding="UTF-8", pretty_print=True, xml_declaration=False)
    header = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE {root_name} SYSTEM \"{dtd_system}\">\n"
    out_path.write_text(header + xml_bytes.decode("utf-8"), encoding="utf-8")


def convert_pdf(
    pdf_path: str,
    out_path: str,
    publisher: str,
    *,
    config_dir: str = "config",
    ocr_on_image_only: bool = False,
    strict: bool = False,
    catalog: str = "validation/catalog.xml",
) -> Dict:
    config = load_mapping(Path(config_dir), publisher)
    tolerances = config.get("tolerances", {})
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists():
        raise FileNotFoundError(pdf_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        working_pdf = pdf_path_obj

        poppler_pages = pdftotext_pages(str(working_pdf))
        pdfminer_pages_list = pdfminer_pages(str(working_pdf))
        _normalize_pages(poppler_pages, config)
        _normalize_pages(pdfminer_pages_list, config)

        mismatches = _detect_mismatches(poppler_pages, pdfminer_pages_list, tolerances)
        image_pages = _image_only_pages(poppler_pages, pdfminer_pages_list)

        if ocr_on_image_only and image_pages:
            ocr_pdf_path = tmp / "ocr.pdf"
            working_pdf = Path(ocr_pages(str(working_pdf), image_pages, str(ocr_pdf_path)))
            poppler_pages = pdftotext_pages(str(working_pdf))
            pdfminer_pages_list = pdfminer_pages(str(working_pdf))
            _normalize_pages(poppler_pages, config)
            _normalize_pages(pdfminer_pages_list, config)
            for page in poppler_pages:
                if page.page_num in image_pages:
                    page.has_ocr = True

        if strict and mismatches:
            raise ValueError(f"Extractor mismatch on pages: {mismatches}")

        pdfxml_path = tmp / "pdfxml.xml"
        pdftohtml_xml(str(working_pdf), str(pdfxml_path))

        blocks = label_blocks(str(pdfxml_path), config)
        classifier_cfg = config.get("classifier", {})
        if classifier_cfg.get("enabled"):
            blocks = classify_blocks(
                blocks,
                threshold=classifier_cfg.get("threshold", 0.85),
                abstain_label=classifier_cfg.get("abstain_label", "abstain"),
            )
        else:
            blocks = [
                {
                    **block,
                    "classifier_label": block.get("label", "para"),
                    "classifier_confidence": 1.0,
                }
                for block in blocks
            ]

        intermediate = _build_block_document(blocks)
        xslt_path = Path(__file__).parent / "transform" / "pdfxml_to_docbook.xsl"
        transform = etree.XSLT(etree.parse(str(xslt_path)))
        root_name = config.get("docbook", {}).get("root", "book")
        result_tree = transform(intermediate, **{"root-element": etree.XSLT.strparam(root_name)})
        docbook_tree = result_tree.getroot()
        out_file = Path(out_path)
        _write_docbook(docbook_tree, root_name, config.get("docbook", {}).get("dtd_system", "dtd/v1.1/docbookx.dtd"), out_file)

        validate_dtd(str(out_file), config.get("docbook", {}).get("dtd_system", "dtd/v1.1/docbookx.dtd"), catalog)

        post_pages = [
            PageText(
                page_num=page.page_num,
                raw_text=page.norm_text,
                norm_text=page.norm_text,
                checksum=page.checksum,
                has_ocr=page.has_ocr,
            )
            for page in poppler_pages
        ]
        metrics = compute_metrics(poppler_pages, post_pages)
        metrics["mismatches"] = mismatches
        metrics["image_only_pages"] = image_pages
        return metrics
