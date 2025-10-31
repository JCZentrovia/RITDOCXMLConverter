# Block Classifier Pipeline

This document describes the end-to-end workflow for training and operating the
DocBook block classifier that augments the layout heuristics in the PDF
pipeline.

## Dataset construction

* Use `tools/dataset/build_block_dataset.py` to aggregate DocBook-labelled
  blocks from `ConversionExamples/`.
* The CLI resolves DocBook archives, runs the PDF heuristics when Poppler is
  available, and falls back to DocBook-only geometry when external tools are
  missing. All samples record text, bounding boxes, heuristic styles, and the
  DocBook (DCT) labels.
* Example invocation (captures one title as a smoke test):

  ```bash
  python tools/dataset/build_block_dataset.py ConversionExamples \
      --limit 1 \
      --output datasets/sample_block_dataset.jsonl \
      --summary datasets/sample_block_dataset.summary.json
  ```

* `datasets/sample_block_dataset.jsonl` is checked in as a reference build. The
  companion `*.summary.json` file reports label distribution and entropy for QA
  audits.

## Fine-tuning

`tools/models/train_layout_classifier.py` fine-tunes a LayoutLMv3 (or DocFormer)
model on the dataset. The script expects `transformers` and `torch` to be
installed locally. It automatically saves the tokenizer, model weights, and the
`label_map.json` file required by the runtime classifier.

Example command:

```bash
python tools/models/train_layout_classifier.py \
    datasets/sample_block_dataset.jsonl \
    --model microsoft/layoutlmv3-base \
    --output models/layout_classifier \
    --epochs 3 \
    --batch-size 4
```

The saved directory can be distributed with the pipeline or stored remotely and
referenced in configuration.

## Evaluation and threshold tuning

`tools/models/evaluate_layout_classifier.py` loads the trained model and a held
out dataset split to measure accuracy and tune the abstention threshold. The
script enumerates confidence levels and returns the highest threshold that
preserves accuracy while maximising coverage.

```bash
python tools/models/evaluate_layout_classifier.py \
    models/layout_classifier \
    datasets/sample_block_dataset.jsonl \
    --output models/layout_classifier/evaluation.json
```

`evaluation.json` records the chosen threshold, achieved accuracy on the
non-abstained blocks, and the resulting coverage.

## Runtime integration

* `pipeline/structure/classifier.py` encapsulates the runtime classifier logic.
  It loads a HuggingFace model on demand, classifies blocks in batches, and
  applies the tuned abstention threshold.
* Configuration is managed via `config/mapping.default.json` (and publisher
  overrides). The key options are:
  * `enabled`: gate the ML model; when disabled the heuristics-only stub is used.
  * `backend`: currently `huggingface`.
  * `model_path`: directory containing the fine-tuned model and `label_map.json`.
  * `threshold` and `abstain_label`: abstention control derived from evaluation.
  * `fallback_label`: used when the model abstains or the text is empty.
  * `monitoring.log_predictions`: emit coverage metrics for observability.
* The classifier caches loaded models per configuration to avoid repeated
  initialisation.
* When `transformers`/`torch` are absent or the model load fails, the module
  logs a warning and gracefully falls back to the stub classifier so the PDF
  pipeline continues to operate.

### Aligning configuration with a trained bundle

1. After fine-tuning, inspect the output directory (e.g.
   `models/layout_classifier/`). It should contain the HuggingFace artefacts
   (`config.json`, `pytorch_model.bin`, tokenizer files) and the generated
   `label_map.json`.
2. Point `model_path` in `config/mapping.default.json` (or a publisher override)
   to that directory.
3. Set `label_map_path` to the `label_map.json` file within the same directory.
   The runtime uses this to translate between model indices and DCT labels.
4. Run `tools/models/evaluate_layout_classifier.py` against your held-out
   dataset. Copy the recommended `threshold` value from the resulting
   `evaluation.json` into the configuration.
5. Optionally toggle `monitoring.log_predictions` to `true` so that the pipeline
   logs how many blocks were classified, abstained, and fell back to heuristics
   during runs. This helps verify threshold effectiveness in production.

When these paths or values do not resolve at runtime, the classifier logs the
misconfiguration and reverts to the deterministic fallback, avoiding pipeline
failures while signalling that the ML model was not engaged.

## Monitoring and troubleshooting

* Enable `monitoring.log_predictions` in the classifier config to log coverage
  and abstention rates to the pipeline logger.
* Dataset summaries (`*.summary.json`) provide drift monitoring; compare label
  entropy and distribution when rebuilding the dataset.
* For full transparency, the dataset builder logs when it cannot access Poppler
  and reverts to DocBook-only geometry, indicating that bounding boxes will be
  coarse.
