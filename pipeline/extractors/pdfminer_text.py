from __future__ import annotations

import io
import logging
from typing import List

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage

from ..common import PageText, checksum

logger = logging.getLogger(__name__)


def pdfminer_pages(pdf_path: str) -> List[PageText]:
    pages: List[PageText] = []
    logger.info("Extracting pdfminer text for %s", pdf_path)
    with open(pdf_path, "rb") as fh:
        for page_num, page in enumerate(PDFPage.get_pages(fh), start=1):
            output = io.StringIO()
            rsrc = PDFResourceManager()
            laparams = LAParams()
            with TextConverter(rsrc, output, laparams=laparams) as device:
                interpreter = PDFPageInterpreter(rsrc, device)
                interpreter.process_page(page)
            text = output.getvalue()
            pages.append(
                PageText(
                    page_num=page_num,
                    raw_text=text,
                    norm_text=text,
                    checksum=checksum(text),
                )
            )
    return pages
