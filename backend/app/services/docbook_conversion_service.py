
"""
DocBook XML Conversion Service

PoC approach:
PDF -> DOCX (existing pdf2docx pipeline) -> DocBook 5 XML (via pandoc)

This service wraps the existing PDFConversionService to reuse its robust
PDF->DOCX logic, then converts that DOCX to DocBook XML using pypandoc.
"""

import logging
import os
import tempfile
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import pypandoc


from app.services.pdf_conversion_service import pdf_conversion_service, ConversionQuality
from app.services.storage_service import s3_service
from pathlib import Path
from app.utils.docbook_postprocess import postprocess_docbook_file

from lxml import etree

DOCBOOK_NS = "http://docbook.org/ns/docbook"
DB = "{%s}" % DOCBOOK_NS

def _ensure_docbook5_root(xml_path: Path, root_tag: str = "article", title: str = None):
    """
    Ensure the XML at xml_path has a DocBook 5 root with namespace.
    If it is a fragment, wrap it inside <article>.
    """
    parser = etree.XMLParser(remove_blank_text=False)
    with open(xml_path, "rb") as f:
        data = f.read()

    # Try parse as-is
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError:
        # Wrap raw text into a container
        wrapper = etree.Element(f"{{{DOCBOOK_NS}}}{root_tag}", nsmap={None: DOCBOOK_NS})
        # Insert as raw text; then reparse to avoid double-escaping
        wrapper.append(etree.Element(f"{{{DOCBOOK_NS}}}para"))
        wrapper[-1].text = data.decode("utf-8", errors="ignore")
        tree = etree.ElementTree(wrapper)
    else:
        # If root has no namespace or not a DocBook element, wrap it
        if root.tag.startswith("{"+DOCBOOK_NS+"}"):
            tree = etree.ElementTree(root)
        else:
            wrapper = etree.Element(f"{{{DOCBOOK_NS}}}{root_tag}", nsmap={None: DOCBOOK_NS})
            wrapper.append(root)
            tree = etree.ElementTree(wrapper)

    # Ensure <info><title>...</title>
    root = tree.getroot()
    has_info = root.find(f"{DB}info") is not None
    if not has_info or (title and not root.find(f"{DB}info/{DB}title")):
        info = root.find(f"{DB}info") or etree.SubElement(root, f"{DB}info")
        if title and not info.find(f"{DB}title"):
            t = etree.SubElement(info, f"{DB}title")
            t.text = title

    # Write back
    tree.write(str(xml_path), encoding="utf-8", xml_declaration=True, pretty_print=False)


logger = logging.getLogger(__name__)

class DocBookConversionService:
    def __init__(self):
        pass

    async def convert_pdf_to_docbook(
        self,
        pdf_s3_key: str,
        output_filename: str,
        quality: str = ConversionQuality.STANDARD,
        include_metadata: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Convert a PDF (stored in S3) to DocBook 5 XML and upload to S3.

        Steps:
          1) Use the existing PDF->DOCX converter to get a temporary .docx
          2) Use pandoc to convert DOCX->DocBook5 (.xml)
          3) Upload the XML to S3 and return the S3 key + metadata

        Returns:
          (xml_s3_key, metadata_dict)
        """
        # 1) Run the existing converter to DOCX into a temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Force a .docx temp output (we won't keep it)
            docx_name = Path(output_filename).with_suffix('.docx').name
            xml_name  = Path(output_filename).with_suffix('.xml').name

            logger.info(f"[DocBook] Starting PDF->DOCX for {pdf_s3_key}")
            docx_s3_key, docx_meta = await pdf_conversion_service.convert_pdf_to_docx(
                pdf_s3_key=pdf_s3_key,
                output_filename=docx_name,
                quality=quality,
                include_metadata=include_metadata
            )

            # Download the just-produced DOCX to local tmp
            local_docx = tmpdir_path / docx_name
            logger.info(f"[DocBook] Downloading DOCX {docx_s3_key} to {local_docx}")
            s3_service.download_file(docx_s3_key, str(local_docx))

            # 2) Convert DOCX -> DocBook5 XML (pandoc)
            local_xml = tmpdir_path / xml_name
            logger.info(f"[DocBook] Converting DOCX to DocBook5 XML at {local_xml}")
            try:
                pypandoc.convert_file(
                    source_file=str(local_docx),
                    to='docbook5',
                    outputfile=str(local_xml),
                    extra_args=[
                    '--standalone',                       # <— ensures root element + namespace
                    '--wrap=none',
                    '--top-level-division=chapter',       # or 'section' or 'part' (choose what you want your root to be)
                    f'--metadata=title:{Path(local_docx).stem}',  # gives <info><title>...</title>
                   ],
                )
            # NEW: enforce proper root + namespace (belt-and-suspenders)
            _ensure_docbook5_root(local_xml, root_tag="article", title=Path(local_docx).stem)

            except Exception as e:
                logger.exception("Pandoc conversion DOCX->DocBook5 failed")
                raise

            # 3) Upload XML to S3
            xml_s3_key = docx_s3_key.replace('/docx/', '/xml/').rsplit('.', 1)[0] + '.xml'
            xml_s3_key = xml_s3_key.replace('manuscripts/', 'manuscripts/')  # placeholder for future path rules

            logger.info(f"[DocBook] Uploading XML {local_xml} to S3 at {xml_s3_key}")
            s3_service.upload_file(str(local_xml), xml_s3_key, content_type='application/xml')

            # Build metadata
            metadata: Dict[str, Any] = {
                "source_pdf_s3_key": pdf_s3_key,
                "intermediate_docx_s3_key": docx_s3_key,
                "xml_s3_key": xml_s3_key,
                "conversion_quality": quality,
                "tool": "pandoc (docx->docbook5)",
                "include_metadata": include_metadata
            }

            logger.info(f"[DocBook] Completed conversion -> {xml_s3_key}")
            return xml_s3_key, metadata


# Global service instance
docbook_conversion_service = DocBookConversionService()
