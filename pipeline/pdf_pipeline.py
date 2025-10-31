from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lxml import etree

# Import library for reading PDF bookmarks
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None

from .ai.config import export_intermediate_artifacts_enabled
from .common import PageText, checksum, load_mapping, normalize_text
from .extractors.pdfminer_text import pdfminer_pages
from .extractors.poppler_pdfxml import pdftohtml_xml
from .extractors.poppler_text import pdftotext_pages
from .ocr.ocrmypdf_runner import ocr_pages
from .package import make_file_fetcher, package_docbook
from .structure.classifier import classify_blocks
from .structure.docbook import build_docbook_tree
from .structure.heuristics import label_blocks
from .structure.ner import annotate_blocks_with_entities
from .transform import RittDocTransformResult, transform_docbook_to_rittdoc
from .validators.counters import compute_metrics
from .validators.dtd_validator import validate_dtd
# DISABLED: These modules are missing and were causing issues
# from .ai_integration import integrate_ai_formatting
# from .smart_label_enhancer import enhance_labels_with_ai_formatting

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


def _write_docbook(
    tree: etree._ElementTree,
    root_name: str,
    dtd_system: str,
    out_path: Path,
    *,
    processing_instructions: Sequence[Tuple[str, str]] = (),
) -> None:
    xml_bytes = etree.tostring(tree, encoding="UTF-8", pretty_print=True, xml_declaration=False)
    header_lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    for target, data in processing_instructions:
        header_lines.append(f"<?{target} {data}?>")
    header_lines.append(f"<!DOCTYPE {root_name} SYSTEM \"{dtd_system}\">")
    header = "\n".join(header_lines) + "\n"
    out_path.write_text(header + xml_bytes.decode("utf-8"), encoding="utf-8")


def _write_plain_text_assets(
    pages: Sequence[PageText],
    base_dir: Path,
    *,
    export: bool = True,
) -> Tuple[List[Tuple[str, Path]], Optional[Path], str]:
    combined_parts: List[str] = [page.raw_text for page in pages]
    combined_text = "\n".join(combined_parts)

    if not export:
        return [], None, combined_text

    plain_text_dir = base_dir / "plain_text"
    plain_text_dir.mkdir(parents=True, exist_ok=True)

    assets: List[Tuple[str, Path]] = []
    for page in pages:
        page_path = plain_text_dir / f"page_{page.page_num:04d}.txt"
        page_path.write_text(page.raw_text, encoding="utf-8")
        assets.append((f"plain_text/{page_path.name}", page_path))

    combined_path = plain_text_dir / "full_text.txt"
    combined_path.write_text(combined_text, encoding="utf-8")
    assets.append(("plain_text/full_text.txt", combined_path))
    return assets, combined_path, combined_text


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

        # Pass the PDF path to enable bookmark-based chapter detection
        blocks = label_blocks(str(pdfxml_path), config, pdf_path=str(working_pdf))
        classifier_cfg = config.get("classifier", {})
        if classifier_cfg.get("enabled"):
            logger.info("Applying model-based block classification")
            blocks = classify_blocks(blocks, classifier_cfg)
        else:
            logger.info("Classifier disabled in configuration; using heuristic labels")
            blocks = [
                {
                    **block,
                    "classifier_label": block.get("label", "para"),
                    "classifier_confidence": 1.0,
                }
                for block in blocks
            ]

        ner_cfg = config.get("ner", {})
        if ner_cfg.get("enabled"):
            try:
                blocks = annotate_blocks_with_entities(blocks, ner_cfg)
                logger.info("Applied named entity recognition to %d blocks", len(blocks))
            except Exception as exc:
                logger.warning("Named entity recognition failed: %s", exc, exc_info=True)
        else:
            logger.info("Named entity recognition disabled in configuration; skipping")

        root_name = config.get("docbook", {}).get("root", "book")
        
        # ==================================================================
        # DEBUGGING: Let's see what blocks we have BEFORE any AI processing
        # ==================================================================
        logger.info("=" * 70)
        logger.info("📊 BLOCKS AFTER CLASSIFIER (Before AI enhancement)")
        logger.info("=" * 70)
        logger.info(f"Total blocks: {len(blocks)}")
        
        # Count blocks by label
        label_counts = {}
        para_blocks_with_text = 0
        para_blocks_without_text = 0
        
        for block in blocks:
            label = block.get("classifier_label") or block.get("label", "para")
            label_counts[label] = label_counts.get(label, 0) + 1
            
            if label == "para":
                text = block.get("text", "").strip()
                if text:
                    para_blocks_with_text += 1
                else:
                    para_blocks_without_text += 1
        
        logger.info(f"Block label counts: {label_counts}")
        logger.info(f"Para blocks WITH text: {para_blocks_with_text}")
        logger.info(f"Para blocks WITHOUT text: {para_blocks_without_text}")
        
        # Show first few blocks as samples
        logger.info("\n🔍 Sample of first 3 blocks:")
        for i, block in enumerate(blocks[:3]):
            label = block.get("classifier_label") or block.get("label", "para")
            text = (block.get("text", "") or "")[:80]
            page = block.get("page_num", "?")
            logger.info(f"  Block {i+1}: [{label}] Page {page}: {text}...")
        
        logger.info("=" * 70)
        
        # ==================================================================
        # DISABLED: AI enhancement temporarily disabled to debug content loss
        # The AI functions were removing text from blocks!
        # ==================================================================
        
        # Still need to check if we should export intermediate artifacts
        # (even though AI enhancement is disabled, this is used for plain text export)
        export_intermediate = export_intermediate_artifacts_enabled()
        
        # AI enhancement is disabled:
        # export_intermediate = export_intermediate_artifacts_enabled()
        # enhanced_blocks, ai_assets = integrate_ai_formatting(
        #     pdf_path_obj,
        #     blocks,
        #     tmp,
        #     export_intermediate=export_intermediate
        # )
        # logger.info("🎯 Enhancing labels using AI formatting patterns")
        # enhanced_blocks = enhance_labels_with_ai_formatting(enhanced_blocks)
        
        # Using original blocks directly (no AI enhancement)
        enhanced_blocks = blocks
        ai_assets = []
        
        logger.info("✅ Building DocBook tree with %d blocks (AI enhancement disabled)", len(enhanced_blocks))
        docbook_tree = build_docbook_tree(enhanced_blocks, root_name)
        rittdoc: RittDocTransformResult = transform_docbook_to_rittdoc(docbook_tree)
        rittdoc_tree = etree.ElementTree(rittdoc.root)

        tmp_doc = tmp / "full_book.xml"
        dtd_system = config.get("docbook", {}).get(
            "dtd_system", "RITTDOCdtd/v1.1/RittDocBook.dtd"
        )
        _write_docbook(
            rittdoc_tree,
            root_name,
            dtd_system,
            tmp_doc,
            processing_instructions=rittdoc.processing_instructions,
        )

        # Temporarily skip DTD validation to inspect raw conversion output.
        # validate_dtd(str(tmp_doc), dtd_system, catalog)

        plain_text_assets, _plain_text_path, plain_text_text = _write_plain_text_assets(
            pdfminer_pages_list, tmp, export=export_intermediate
        )

        media_fetcher = make_file_fetcher([tmp, pdf_path_obj.parent])
        zip_path = package_docbook(
            rittdoc.root,
            root_name,
            dtd_system,
            out_path,
            processing_instructions=rittdoc.processing_instructions,
            assets=[*rittdoc.assets, *plain_text_assets, *ai_assets],
            media_fetcher=media_fetcher,
        )

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
        metrics["output_path"] = str(zip_path)
        return metrics