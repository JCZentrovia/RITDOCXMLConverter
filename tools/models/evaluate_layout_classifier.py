"""Evaluate a trained layout classifier and tune abstention thresholds."""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import torch
from torch.utils.data import DataLoader, Dataset

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "transformers is required for evaluation; install with pip install transformers"
    ) from exc

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class EvalRecord:
    text: str
    bbox: Dict[str, float]
    label: str


def load_dataset(jsonl_path: Path) -> List[EvalRecord]:
    records: List[EvalRecord] = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            data = json.loads(line)
            records.append(
                EvalRecord(
                    text=data["text"],
                    bbox=data.get("geometry") or {"left": 0.0, "top": 0.0, "width": 0.0, "height": 0.0},
                    label=data["dct_label"],
                )
            )
    logger.info("Loaded %s evaluation records", len(records))
    return records


def _normalise_bbox(bbox: Dict[str, float]) -> List[int]:
    left = float(bbox.get("left", 0.0))
    top = float(bbox.get("top", 0.0))
    width = float(bbox.get("width", 0.0))
    height = float(bbox.get("height", 0.0))
    right = left + width
    bottom = top + height
    max_dim = max(right, bottom, 1.0)
    scale = 1000.0 / max_dim
    x0 = int(max(0.0, min(1000.0, round(left * scale))))
    y0 = int(max(0.0, min(1000.0, round(top * scale))))
    x1 = int(max(0.0, min(1000.0, round(right * scale))))
    y1 = int(max(0.0, min(1000.0, round(bottom * scale))))
    return [x0, y0, x1, y1]


class EvalDataset(Dataset):
    def __init__(self, records: Sequence[EvalRecord], tokenizer, max_length: int = 256) -> None:
        self.records = list(records)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        record = self.records[idx]
        encoding = self.tokenizer(
            record.text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_attention_mask=True,
        )
        bbox = _normalise_bbox(record.bbox)
        encoding["bbox"] = [bbox] * len(encoding["input_ids"])
        return {key: torch.tensor(value) for key, value in encoding.items()}


def _to_device(batch: Dict[str, torch.Tensor], device: torch.device) -> Dict[str, torch.Tensor]:
    return {key: tensor.to(device) for key, tensor in batch.items() if key != "labels"}


def evaluate(
    model_dir: Path,
    dataset_path: Path,
    *,
    batch_size: int = 8,
    max_length: int = 256,
    label_map_path: Optional[Path] = None,
) -> Dict[str, object]:
    records = load_dataset(dataset_path)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    dataset = EvalDataset(records, tokenizer, max_length=max_length)
    loader = DataLoader(dataset, batch_size=batch_size)

    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    label_map = None
    if label_map_path and label_map_path.exists():
        label_map = json.loads(label_map_path.read_text(encoding="utf-8"))
        id_to_label = {int(v): k for k, v in label_map.items()}
    else:
        id_to_label = {idx: str(idx) for idx in range(model.config.num_labels)}

    confidences: List[float] = []
    predictions: List[str] = []
    gold: List[str] = []

    offset = 0
    with torch.no_grad():
        for batch in loader:
            batch_count = batch["input_ids"].size(0)
            labels = [dataset.records[i].label for i in range(offset, offset + batch_count)]
            offset += batch_count
            gold.extend(labels)
            model_inputs = _to_device(batch, device)
            outputs = model(**model_inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            scores, indices = probs.max(dim=-1)
            confidences.extend(scores.cpu().tolist())
            predictions.extend(id_to_label[idx] for idx in indices.cpu().tolist())

    return tune_threshold(confidences, predictions, gold)


def tune_threshold(confidences: Sequence[float], predictions: Sequence[str], gold: Sequence[str]) -> Dict[str, object]:
    paired = sorted(zip(confidences, predictions, gold), reverse=True)
    best_threshold = 0.0
    best_accuracy = 0.0
    abstain_label = "abstain"
    for threshold in {round(score, 4) for score in confidences}:
        covered = 0
        correct = 0
        for score, pred_label, gold_label in paired:
            if score < threshold:
                continue
            covered += 1
            if pred_label == gold_label:
                correct += 1
        accuracy = correct / covered if covered else 0.0
        if accuracy >= best_accuracy:
            best_accuracy = accuracy
            best_threshold = threshold
    coverage = sum(score >= best_threshold for score in confidences) / max(len(confidences), 1)
    report = {
        "best_threshold": best_threshold,
        "non_abstain_accuracy": best_accuracy,
        "coverage": coverage,
        "abstain_label": abstain_label,
    }
    logger.info("Best threshold %.3f -> accuracy %.3f at %.1f%% coverage", best_threshold, best_accuracy, coverage * 100)
    return report


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir", type=Path, help="Trained model directory")
    parser.add_argument("dataset", type=Path, help="Evaluation dataset (JSONL)")
    parser.add_argument("--label-map", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("models/layout_classifier/evaluation.json"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    metrics = evaluate(
        args.model_dir,
        args.dataset,
        batch_size=args.batch_size,
        max_length=args.max_length,
        label_map_path=args.label_map,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    logger.info("Evaluation results stored in %s", args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
