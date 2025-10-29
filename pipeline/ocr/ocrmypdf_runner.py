from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

from ..common import run_cmd

logger = logging.getLogger(__name__)


def _collapse_ranges(pages: Iterable[int]) -> str:
    sorted_pages = sorted(set(pages))
    ranges: List[str] = []
    start = prev = None
    for page in sorted_pages:
        if start is None:
            start = prev = page
            continue
        if page == prev + 1:
            prev = page
            continue
        if start == prev:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{prev}")
        start = prev = page
    if start is not None:
        if start == prev:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{prev}")
    return ",".join(ranges)


def ocr_pages(pdf_path: str, pages: List[int], out_path: str) -> str:
    if not pages:
        return pdf_path
    page_spec = _collapse_ranges(pages)
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ocrmypdf",
        "--force-ocr",
        "--skip-text",
        "--pages",
        page_spec,
        pdf_path,
        str(output),
    ]
    logger.info("Running OCRmyPDF on %s pages %s", pdf_path, page_spec)
    run_cmd(args)
    return str(output)
