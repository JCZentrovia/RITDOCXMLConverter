
"""
CLI script for PoC: convert a local PDF file to DocBook 5 XML using
(pdf -> docx via pdf2docx) then docx -> docbook via pandoc.

Usage:
  python convert_pdf_to_docbook.py /path/to/file.pdf /path/to/output.xml

Requirements:
  - pdf2docx
  - pypandoc + pandoc binary (pypandoc_binary provides one)
"""

import sys
import os
import tempfile
from pathlib import Path
import pypandoc

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
        print("Usage: python convert_pdf_to_docbook.py <input.pdf> <output.xml>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    out_xml  = sys.argv[2]

    out_xml = Path(out_xml).resolve()
    out_xml.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        docx_path = tmpdir / (Path(pdf_path).stem + ".docx")

        print(f"[1/2] Converting PDF -> DOCX: {pdf_path} -> {docx_path}")
        pdf_to_docx(pdf_path, str(docx_path))

        print(f"[2/2] Converting DOCX -> DocBook5 XML: {docx_path} -> {out_xml}")
        pypandoc.convert_file(
            source_file=str(docx_path),
            to='docbook5',
            outputfile=str(out_xml),
             extra_args=[
                '--standalone',
                '--wrap=none',
                '--top-level-division=chapter',
                f'--metadata=title:{Path(pdf_path).stem}',
            ],
        )

    print(f"Done. Wrote: {out_xml}")

if __name__ == "__main__":
    main()
