from __future__ import annotations

import logging
from typing import List

from lxml import etree

logger = logging.getLogger(__name__)


def _match_font(fontspec: dict, rule: dict) -> bool:
    if fontspec is None:
        return False
    family = fontspec.get("family", "").lower()
    if "family" in rule and rule["family"].lower() not in family:
        return False
    size = float(fontspec.get("size", 0))
    if "min_size" in rule and size < rule["min_size"]:
        return False
    if "max_size" in rule and size > rule["max_size"]:
        return False
    return True


def _infer_heading(block: dict, mapping: dict) -> str | None:
    pdf_cfg = mapping.get("pdf", {})
    heading_fonts = pdf_cfg.get("heading_fonts", {})
    for level, rules in heading_fonts.items():
        for rule in rules:
            if _match_font(block.get("fontspec"), rule):
                return "title" if level.upper() == "H1" else "section"
    return None


def _infer_list(block: dict, mapping: dict) -> str | None:
    text = block["text"].strip()
    markers = mapping.get("pdf", {}).get("list_markers", [])
    for marker in markers:
        if text.startswith(marker):
            return "list_item"
    return None


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

    blocks: List[dict] = []
    for idx, text_node in enumerate(tree.findall(".//text")):
        content = "".join(text_node.itertext())
        if not content.strip():
            continue
        font_id = text_node.get("font")
        fontspec = fontspecs.get(font_id)
        block = {
            "index": idx,
            "text": content,
            "bbox": {
                "top": float(text_node.get("top", "0")),
                "left": float(text_node.get("left", "0")),
                "width": float(text_node.get("width", "0")),
                "height": float(text_node.get("height", "0")),
            },
            "font_id": font_id,
            "fontspec": fontspec,
        }
        label = _infer_heading(block, mapping)
        if label is None:
            label = _infer_list(block, mapping)
        if label is None:
            label = "para"
        block["label"] = label
        blocks.append(block)
    logger.info("Labeled %s blocks", len(blocks))
    return blocks
