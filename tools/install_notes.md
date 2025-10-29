# Installation Notes

1. Install system packages: `poppler-utils`, `tesseract-ocr`, `ocrmypdf`, and `libxml2-utils`.
2. Create a virtual environment and install Python dependencies with `pip install -r tools/requirements.txt`.
3. Ensure the DocBook DTD files are available in `dtd/v1.1` and that `validation/catalog.xml` lists them for xmllint.
