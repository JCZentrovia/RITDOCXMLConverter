from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List

from ..common import PageText

logger = logging.getLogger(__name__)


def _word_count(text: str) -> int:
    return len([token for token in text.strip().split() if token])


def _special_chars(text: str) -> Counter:
    return Counter(ch for ch in text if ord(ch) > 127)


def compute_metrics(pre: List[PageText], post: List[PageText]) -> Dict:
    post_map = {p.page_num: p for p in post}
    pages = []
    overall_special = Counter()
    overall_flags: List[str] = []

    for page in pre:
        target = post_map.get(page.page_num)
        flags: List[str] = []
        chars_in = len(page.norm_text)
        words_in = _word_count(page.norm_text)
        chars_out = len(target.norm_text) if target else 0
        words_out = _word_count(target.norm_text) if target else 0
        if target is None:
            flags.append("missing_output_page")
        else:
            if page.norm_text != target.norm_text:
                flags.append("text_mismatch")
            if chars_in != chars_out:
                flags.append("char_count_diff")
        page_special_in = _special_chars(page.norm_text)
        page_special_out = _special_chars(target.norm_text if target else "")
        overall_special.update(page_special_in)
        overall_special.update(page_special_out)
        pages.append(
            {
                "page": page.page_num,
                "chars_in": chars_in,
                "chars_out": chars_out,
                "words_in": words_in,
                "words_out": words_out,
                "checksum_in": page.checksum,
                "checksum_out": target.checksum if target else "",
                "flags": flags,
                "has_ocr": target.has_ocr if target else False,
            }
        )
        overall_flags.extend(flags)

    summary = {
        "total_pages": len(pre),
        "flags": overall_flags,
        "special_chars": overall_special,
    }
    logger.info(
        "Metrics computed for %s pages; %s flagged pages",
        len(pre),
        sum(1 for p in pages if p["flags"]),
    )
    return {"pages": pages, "summary": summary}
