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

### Plain text inspection artifacts

PDF conversions now package the intermediate text extracted by `pdfminer.six` inside the output ZIP bundle under `plain_text/`. Each page is available individually (`page_0001.txt`, etc.) together with a `full_text.txt` concatenation so you can audit exactly what the extractor produced before downstream processing.

### Optional AI-assisted formatting

When a PDF conversion runs, the pipeline can optionally invoke an OpenAI GPT‑4o Vision model to describe the PDF's formatting. The model returns JSON instructions keyed by the plain-text line numbers; those directives are applied locally to generate a formatted `.docx`, which is then converted into DocBook XML while preserving the original characters byte-for-byte. The service is disabled unless valid credentials are provided via environment variables.

1. Copy `.env.example` to `.env` and populate `OPENAI_API_KEY` and `OPENAI_API_MODEL` (e.g. `gpt-4o-mini`).
2. Ensure the optional dependencies are installed: `pip install -r tools/requirements.txt`.
3. Set `EXPORT_INTERMEDIATE_ARTIFACTS=true` (default) to collect the extracted plain text, JSON instructions, and formatted `.docx` in the output bundle. Set it to `false` to skip bundling those checkpoints while still running the formatter.
4. Run the PDF conversion as usual. When credentials are present, the formatter is engaged automatically for PDF inputs. EPUB conversions intentionally skip the AI stage.

The formatter validates that the AI output exactly matches the extracted text. Any deviation or runtime failure causes the AI artifacts to be skipped so that content fidelity is never compromised.

### Machine learning block classifier

The structural classifier built on LayoutLMv3 augments the heuristic labelling
in the PDF pipeline. Dataset construction, fine-tuning, evaluation, and runtime
integration are documented in `docs/BLOCK_CLASSIFIER.md`. The default
configuration keeps the classifier disabled; enable it by pointing
`config/mapping.default.json` (or a publisher override) at a trained model
bundle generated with the tooling under `tools/models/`.

## QA reports

Every conversion produces per-page metrics (character/word counts, checksums, OCR flags) alongside an HTML summary rendered via Jinja2. Templates can be customized in `reports/templates/qa_report.html.j2`.

