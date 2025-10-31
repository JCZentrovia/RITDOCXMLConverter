"""Fine-tune a LayoutLMv3/DocFormer classifier on the block dataset."""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import torch
from torch.utils.data import Dataset

try:
    from transformers import (
        AutoConfig,
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "transformers is required for training; install with pip install transformers"
    ) from exc

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BlockRecord:
    text: str
    bbox: Dict[str, float]
    label: str


def load_dataset(jsonl_path: Path) -> List[BlockRecord]:
    records: List[BlockRecord] = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            data = json.loads(line)
            records.append(
                BlockRecord(
                    text=data["text"],
                    bbox=data.get("geometry") or {"left": 0.0, "top": 0.0, "width": 0.0, "height": 0.0},
                    label=data["dct_label"],
                )
            )
    logger.info("Loaded %s records from %s", len(records), jsonl_path)
    return records


def build_label_mapping(records: Iterable[BlockRecord], labels_path: Optional[Path]) -> Dict[str, int]:
    if labels_path and labels_path.exists():
        loaded = json.loads(labels_path.read_text(encoding="utf-8"))
        return {label: int(idx) for idx, label in enumerate(loaded)}
    labels = sorted({record.label for record in records})
    mapping = {label: idx for idx, label in enumerate(labels)}
    if labels_path:
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
    return mapping


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


class LayoutBlockDataset(Dataset):
    def __init__(
        self,
        records: List[BlockRecord],
        tokenizer,
        label_to_id: Dict[str, int],
        max_length: int = 256,
    ) -> None:
        self.records = records
        self.tokenizer = tokenizer
        self.label_to_id = label_to_id
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int):
        record = self.records[idx]
        encoding = self.tokenizer(
            record.text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_attention_mask=True,
        )
        bbox = _normalise_bbox(record.bbox)
        bbox_sequence = [bbox] * len(encoding["input_ids"])
        encoding["bbox"] = bbox_sequence
        encoding["labels"] = self.label_to_id[record.label]
        return {key: torch.tensor(value) for key, value in encoding.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Path to the JSONL dataset produced by build_block_dataset")
    parser.add_argument("--output", type=Path, default=Path("models/layout_classifier"))
    parser.add_argument("--model", type=str, default="microsoft/layoutlmv3-base")
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help=(
            "Optional path to persist the label vocabulary. When omitted the file "
            "is stored next to the fine-tuned model output directory."
        ),
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--warmup-steps", type=int, default=0)
    parser.add_argument(
        "--eval-split",
        type=float,
        default=0.1,
        help="Fraction reserved for evaluation (between 0 and 1).",
    )
    return parser.parse_args()


def train() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)

    if not 0 <= args.eval_split < 1:
        raise SystemExit("--eval-split must be within [0, 1).")

    records = load_dataset(args.dataset)
    split_idx = max(1, int(len(records) * (1 - args.eval_split)))
    train_records = records[:split_idx]
    eval_records = records[split_idx:] if split_idx < len(records) else records[-1:]

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    labels_path = args.labels or args.output / "labels.json"
    label_to_id = build_label_mapping(records, labels_path)
    id2label = {idx: label for label, idx in label_to_id.items()}

    train_dataset = LayoutBlockDataset(train_records, tokenizer, label_to_id, max_length=args.max_length)
    eval_dataset = LayoutBlockDataset(eval_records, tokenizer, label_to_id, max_length=args.max_length)

    config = AutoConfig.from_pretrained(
        args.model,
        num_labels=len(label_to_id),
        id2label=id2label,
        label2id=label_to_id,
    )
    model = AutoModelForSequenceClassification.from_pretrained(args.model, config=config)

    training_args = TrainingArguments(
        output_dir=str(args.output),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        warmup_steps=args.warmup_steps,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=10,
    )

    def compute_metrics(pred):  # pragma: no cover - heavy dependency on Trainer internals
        predictions = pred.predictions.argmax(-1)
        labels = pred.label_ids
        accuracy = (predictions == labels).mean() if len(labels) else 0.0
        return {"accuracy": float(accuracy)}

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    (args.output / "label_map.json").write_text(
        json.dumps(label_to_id, indent=2), encoding="utf-8"
    )
    logger.info("Training completed; model saved to %s", args.output)


if __name__ == "__main__":  # pragma: no cover
    train()
