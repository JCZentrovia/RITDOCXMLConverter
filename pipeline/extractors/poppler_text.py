from __future__ import annotations

import logging
from typing import List

from ..common import PageText, checksum, run_cmd

logger = logging.getLogger(__name__)


def pdftotext_pages(pdf_path: str) -> List[PageText]:
    args = ["pdftotext", "-enc", "UTF-8", "-layout", str(pdf_path), "-"]
    logger.info("Extracting Poppler text for %s", pdf_path)
    output = run_cmd(args)
    pages = []
    for idx, page_text in enumerate(output.split("\f"), start=1):
        pages.append(
            PageText(
                page_num=idx,
                raw_text=page_text,
                norm_text=page_text,
                checksum=checksum(page_text),
            )
        )
    return pages
