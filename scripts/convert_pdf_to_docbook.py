
"""
CLI: Convert a local PDF/EPUB into a DocBook package matching examples.

Pipeline:
- PDF -> DOCX (pdf2docx) -> DocBook (V4) via pandoc -> packaged zip
- EPUB -> DocBook (V4) via pandoc -> packaged zip

Usage:
  python convert_pdf_to_docbook.py /path/to/file.(pdf|epub) /path/to/output.zip

Requirements:
  - pdf2docx (for PDFs)
  - pypandoc + pandoc binary (pypandoc_binary provides one)
"""

import sys
import os
import tempfile
from pathlib import Path
import pypandoc
from app.utils.docbook_packager import DocbookPackager
from pathlib import Path

def pdf_to_docx(pdf_path: str, docx_path: str, **kwargs):
    # Minimal pdf2docx usage to keep this CLI self-contained for PoC
    from pdf2docx import Converter
    cv = Converter(pdf_path)
    try:
        # You can tweak params (start=, end=, etc.) or layout_mode if needed.
        cv.convert(docx_path)
    finally:
        cv.close()

def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_pdf_to_docbook.py <input.(pdf|epub)> <output.zip>")
        sys.exit(1)
    input_path = sys.argv[1]
    out_zip  = Path(sys.argv[2]).resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_ext = Path(input_path).suffix.lower()
        local_combined_xml = tmpdir / (Path(input_path).stem + ".xml")

        if input_ext == '.pdf':
            docx_path = tmpdir / (Path(input_path).stem + ".docx")
            print(f"[1/3] Converting PDF -> DOCX: {input_path} -> {docx_path}")
            pdf_to_docx(input_path, str(docx_path))

            print(f"[2/3] Converting DOCX -> DocBook (V4): {docx_path} -> {local_combined_xml}")
            pypandoc.convert_file(
                source_file=str(docx_path),
                to='docbook',
                outputfile=str(local_combined_xml),
                extra_args=[
                    '--standalone',
                    '--wrap=none',
                    '--top-level-division=chapter',
                    f'--metadata=title:{Path(input_path).stem}',
                ],
            )
        elif input_ext == '.epub':
            print(f"[1/2] Converting EPUB -> DocBook (V4): {input_path} -> {local_combined_xml}")
            pypandoc.convert_file(
                source_file=str(input_path),
                to='docbook',
                outputfile=str(local_combined_xml),
                extra_args=[
                    '--standalone',
                    '--wrap=none',
                    '--top-level-division=chapter',
                    f'--metadata=title:{Path(input_path).stem}',
                ],
            )
        else:
            print("Unsupported input. Use .pdf or .epub")
            sys.exit(2)

        print(f"[3/3] Packaging DocBook into zip at {out_zip}")
        packager = DocbookPackager()
        book_xml_path, _ = packager.package(
            combined_docbook_xml=local_combined_xml,
            output_dir=tmpdir / "package",
            package_root_folder=None,
            title=Path(input_path).stem,
            media_extracted_dir=local_combined_xml.parent,
        )

        # Zip
        import shutil
        root_dir = book_xml_path.parent
        zip_base = out_zip.with_suffix('')
        zip_created = Path(shutil.make_archive(str(zip_base), 'zip', root_dir))
        if zip_created != out_zip:
            out_zip.unlink(missing_ok=True)
            zip_created.rename(out_zip)

    print(f"Done. Wrote: {out_zip}")

if __name__ == "__main__":
    main()
