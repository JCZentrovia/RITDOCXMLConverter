# Operator Guide

This guide explains how to run the RIT DOC XML conversion pipeline on publisher PDFs and EPUBs.

## Prerequisites

* Python 3.10+
* Poppler utilities (`pdftohtml`, `pdftotext`)
* `pdfminer.six`
* `xmllint` and the DocBook DTD bundle in `dtd/v1.1`
* Optional: `ocrmypdf` for OCR fallback

Install Python dependencies:

```bash
pip install -r tools/requirements.txt
```

## Single file processing

### PDF

```bash
python cli.py pdf --input INPUT.pdf --out OUTPUT.xml --publisher publisher_A [--ocr-on-image-only] [--strict]
```

### EPUB

```bash
python cli.py epub --input INPUT.epub --out OUTPUT.xml --publisher publisher_A [--strict]
```

## Batch processing

Provide a CSV or JSON manifest with `input`, `type`, `publisher`, and `out` fields:

```bash
python cli.py batch --manifest jobs.csv --parallel 2
```

## Validation

```bash
python cli.py validate --input OUTPUT.xml
```

## Reports

Run commands write CSV and HTML QA reports to the directory configured via CLI options or defaults in the configuration.
