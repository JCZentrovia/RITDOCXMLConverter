# RIT DOC XML Converter

Deterministic pipeline for converting publisher PDFs and EPUBs into DocBook-style XML that conforms to the RIT DOC DTD. The system prioritizes character-for-character fidelity while providing validation, metrics, and QA reports for each run.

## Repository layout

```
cli.py                    # CLI entry point for pdf/epub/batch/validate commands
config/                   # Default + publisher-specific mapping files
pipeline/                 # Core extraction, structure inference, transforms, validators
reports/templates/        # HTML template used for QA reports
validation/               # xmllint catalog + helper scripts
docs/                     # Operator and developer guides
Makefile                  # Convenience targets for CLI commands and tests
```

Sample acceptance fixtures live under `tests/`. Additional publisher examples can be stored in `ConversionExamples/`.

## Prerequisites

* Python 3.10+
* Poppler utilities (`pdftohtml`, `pdftotext`)
* `pdfminer.six`
* `xmllint` with the DocBook DTD bundle available under `dtd/v1.1`
* Optional: `ocrmypdf` and Tesseract when OCR fallback is desired

Install Python packages with:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt
```

## Usage

All commands are executed via the CLI. Outputs include DocBook XML plus CSV/HTML QA reports written beneath `out/reports/` by default.

```bash
# Convert a PDF
python cli.py pdf --input INPUT.pdf --out OUTPUT.xml --publisher publisher_A [--ocr-on-image-only] [--strict]

# Convert an EPUB
python cli.py epub --input INPUT.epub --out OUTPUT.xml --publisher publisher_A [--strict]

# Run a batch manifest (CSV or JSON)
python cli.py batch --manifest jobs.csv [--parallel N] [--strict]

# Validate an existing DocBook file against the RIT DOC DTD
python cli.py validate --input OUTPUT.xml [--catalog validation/catalog.xml]
```

See `docs/OPERATOR_GUIDE.md` for command details and `docs/DEV_GUIDE.md` for architecture notes.

## Testing

Run the unit test suite with:

```bash
pytest
```

The Makefile exposes shortcuts:

```bash
make pdf INPUT=file.pdf OUT=file.xml PUBLISHER=publisher_A
make epub INPUT=file.epub OUT=file.xml PUBLISHER=publisher_A
make validate FILE=output.xml
make tests
```

## Configuration

Default normalization, mapping, and tolerance rules live in `config/mapping.default.json`. Publisher-specific overrides can be added under `config/publishers/<publisher>.json` without modifying the Python code.

## QA reports

Every conversion produces per-page metrics (character/word counts, checksums, OCR flags) alongside an HTML summary rendered via Jinja2. Templates can be customized in `reports/templates/qa_report.html.j2`.

