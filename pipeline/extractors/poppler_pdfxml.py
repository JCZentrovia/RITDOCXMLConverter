from __future__ import annotations

import logging
from pathlib import Path

from ..common import run_cmd

logger = logging.getLogger(__name__)


def pdftohtml_xml(pdf_path: str, out_xml: str) -> None:
    pdf = Path(pdf_path)
    out = Path(out_xml)
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "pdftohtml",
        "-xml",
        "-enc",
        "UTF-8",
        "-nodrm",
        "-zoom",
        "1.0",
        str(pdf),
        str(out),
    ]
    logger.info("Generating Poppler PDFXML for %s", pdf)
    run_cmd(args)
