# Developer Guide

This document describes the architecture of the RIT DOC XML conversion pipeline and explains how to extend it.

## Architecture overview

The code base is organized around deterministic extract-transform-validate steps. The `pipeline/pdf_pipeline.py` module orchestrates PDF conversions by invoking dual text extractors, performing per-page diffs, running structure labeling, transforming annotated PDFXML to DocBook, and validating the output with the DocBook DTD. The EPUB path in `pipeline/epub_pipeline.py` follows a similar pattern but skips text layer detection.

## Adding publisher mappings

Publisher-specific overrides live in `config/publishers/<publisher>.json`. Only configuration files should change when tuning mappings for a new publisher. Each configuration can override normalization rules, font mappings, classifier thresholds, and DocBook root element.

## Classifier integration

The optional classifier in `pipeline/structure/classifier.py` operates on block descriptors produced by heuristics. It returns labels with confidences and may abstain. The pipeline ensures that classifier decisions never modify text content.

## Metrics and reporting

Per-page metrics, checksums, and diffs are produced by `pipeline/validators/counters.py`. CSV and HTML QA reports are rendered from Jinja2 templates in `reports/templates`. Update the template to change report formatting.

## Tests

Unit tests live under `tests/unit`, integration tests under `tests/integration`. Add sample fixtures to `tests/data`. Golden XML outputs must remain character-identical; tests fail if char counts differ or validation fails.
