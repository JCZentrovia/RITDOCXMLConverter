"""
EPUB conversion service: EPUB -> DocBook (V4) -> packaged ZIP.
"""
from pathlib import Path
from typing import Tuple, Dict, Any
import tempfile
import logging

from app.services.docbook_conversion_service import docbook_conversion_service
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)


class EPUBConversionService:
    async def convert_epub_to_package(self, epub_s3_key: str, output_basename: str) -> Tuple[str, Dict[str, Any]]:
        # Delegate to docbook service method; wrapper kept for symmetry
        return await docbook_conversion_service.convert_epub_to_docbook_package(
            epub_s3_key=epub_s3_key,
            output_filename=output_basename
        )


epub_conversion_service = EPUBConversionService()
