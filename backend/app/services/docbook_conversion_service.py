
"""
DocBook XML Conversion Service

Productionized approach:
PDF -> DOCX (existing pdf2docx pipeline) -> DocBook 4 XML (via pandoc) ->
DocBook package (book.xml + ch0001.xml + multimedia/*) zipped and uploaded.

Also supports EPUB -> DocBook 4 XML -> packaged + zipped.

This matches the example outputs with a DocBook V4 DOCTYPE and ENTITY-based
chapter includes.
"""

import logging
import os
import tempfile
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import pypandoc


from app.services.pdf_conversion_service import pdf_conversion_service, ConversionQuality
from app.services.s3_service import s3_service
from pathlib import Path
from app.utils.docbook_packager import DocbookPackager

from lxml import etree
import shutil

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
        Convert a PDF (stored in S3) to a DocBook package zip and upload to S3.

        Steps:
          1) Use the existing PDF->DOCX converter to get a temporary .docx
          2) Use pandoc to convert DOCX -> DocBook (V4) (.xml)
          3) Package into book.xml + ch000X.xml + multimedia/*
          4) Zip the package and upload to S3

        Returns: (xml_zip_s3_key, metadata_dict)
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

            # 2) Convert DOCX -> DocBook (V4) XML (pandoc)
            local_xml = tmpdir_path / xml_name
            logger.info(f"[DocBook] Converting DOCX to DocBook (V4) XML at {local_xml}")
            try:
                pypandoc.convert_file(
                    source_file=str(local_docx),
                    to='docbook',
                    outputfile=str(local_xml),
                    extra_args=[
                        '--standalone',
                        '--wrap=none',
                        '--top-level-division=chapter',
                        f'--metadata=title:{Path(local_docx).stem}',
                        f"--extract-media={str(tmpdir_path / 'extracted_media')}",
                    ],
                )
            except Exception as e:
                logger.exception("Pandoc conversion DOCX->DocBook (V4) failed")
                raise

            # 3) Package into book.xml + ch000X.xml + multimedia/*
            packager = DocbookPackager(logger=logger)
            package_root = tmpdir_path / "package"
            # Derive ISBN from filename if present (digits only heuristic)
            base_stem = Path(output_filename).stem
            isbn_guess = ''.join([c for c in base_stem if c.isdigit()]) or None

            book_xml_path, chapters = packager.package(
                combined_docbook_xml=local_xml,
                output_dir=package_root,
                package_root_folder=None,
                title=Path(local_docx).stem,
                media_extracted_dir=(tmpdir_path / 'extracted_media'),
                isbn=isbn_guess,
            )

            # 4) Zip and upload package to S3
            root_dir = book_xml_path.parent
            zip_base = tmpdir_path / Path(output_filename).with_suffix('').name
            zip_file_path = Path(shutil.make_archive(str(zip_base), 'zip', root_dir))

            xml_s3_key = docx_s3_key.replace('/docx/', '/xml/').rsplit('.', 1)[0] + '.zip'
            logger.info(f"[DocBook] Uploading package ZIP {zip_file_path} to S3 at {xml_s3_key}")
            s3_service.upload_file(str(zip_file_path), xml_s3_key, content_type='application/zip')

            # Build metadata
            metadata: Dict[str, Any] = {
                "source_pdf_s3_key": pdf_s3_key,
                "intermediate_docx_s3_key": docx_s3_key,
                "xml_s3_key": xml_s3_key,
                "conversion_quality": quality,
                "tool": "pandoc (docx->docbook) + packaging",
                "include_metadata": include_metadata,
                # Surface pdf/docx conversion metadata for downstream metrics
                **docx_meta,
                "package_chapter_count": len(chapters),
            }

            logger.info(f"[DocBook] Completed conversion -> {xml_s3_key}")
            return xml_s3_key, metadata

    async def convert_epub_to_docbook_package(
        self,
        epub_s3_key: str,
        output_filename: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Convert an EPUB (stored in S3) to a DocBook package (.zip) and upload to S3.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            local_epub = tmpdir_path / Path(output_filename).with_suffix('.epub').name
            # Download EPUB
            logger.info(f"[DocBook] Downloading EPUB {epub_s3_key} to {local_epub}")
            s3_service.download_file(epub_s3_key, str(local_epub))

            # Convert EPUB -> DocBook (V4)
            local_xml = tmpdir_path / Path(output_filename).with_suffix('.xml').name
            try:
                pypandoc.convert_file(
                    source_file=str(local_epub),
                    to='docbook',
                    outputfile=str(local_xml),
                    extra_args=[
                        '--standalone',
                        '--wrap=none',
                        '--top-level-division=chapter',
                        f'--metadata=title:{Path(local_epub).stem}',
                        f"--extract-media={str(tmpdir_path / 'extracted_media')}",
                    ],
                )
            except Exception:
                logger.exception("Pandoc conversion EPUB->DocBook (V4) failed")
                raise

            # Package
            packager = DocbookPackager(logger=logger)
            package_root = tmpdir_path / "package"
            base_stem = Path(output_filename).stem
            isbn_guess = ''.join([c for c in base_stem if c.isdigit()]) or None

            book_xml_path, chapters = packager.package(
                combined_docbook_xml=local_xml,
                output_dir=package_root,
                package_root_folder=None,
                title=Path(local_epub).stem,
                media_extracted_dir=(tmpdir_path / 'extracted_media'),
                isbn=isbn_guess,
            )

            # Zip and upload
            root_dir = book_xml_path.parent
            zip_base = tmpdir_path / Path(output_filename).with_suffix('').name
            zip_file_path = Path(shutil.make_archive(str(zip_base), 'zip', root_dir))

            # Derive target key
            xml_s3_key = f"converted/{Path(output_filename).with_suffix('.zip').name}"
            logger.info(f"[DocBook] Uploading EPUB package ZIP {zip_file_path} to S3 at {xml_s3_key}")
            s3_service.upload_file(str(zip_file_path), xml_s3_key, content_type='application/zip')

            metadata: Dict[str, Any] = {
                "source_epub_s3_key": epub_s3_key,
                "xml_s3_key": xml_s3_key,
                "tool": "pandoc (epub->docbook) + packaging",
                "package_chapter_count": len(chapters),
            }
            return xml_s3_key, metadata


# Global service instance
docbook_conversion_service = DocBookConversionService()
