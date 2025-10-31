#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_layout_classifier_patched.py
- Works with text-only datasets (default, BERT) or layout-aware datasets (LayoutLMv3).
- JSONL expected:
  * Text-only: {"text": "...", "label": "SomeLabel"}
  * Layout-aware: {"words": ["w1", ...], "boxes": [[x0,y0,x1,y1], ...], "label": "SomeLabel"}
- Saves model + tokenizer + label_map.json in output dir.
"""
from __future__ import annotations

import itertools
import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

import torch
from torch.utils.data import Dataset

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
)

# Optional imports for layoutlmv3 path
try:
    from transformers import LayoutLMv3Processor, LayoutLMv3ForSequenceClassification  # type: ignore
    HAS_LAYOUTLMV3 = True
except Exception:
    HAS_LAYOUTLMV3 = False

import inspect
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("train_layout_classifier")


# ------------------------ Helpers ------------------------

# ----------- Flexible field detection helpers -----------

COMMON_TEXT_FIELDS = ["text", "content", "block_text", "sentence", "tokens_text"]
COMMON_LABEL_FIELDS = ["label", "labels", "category", "class", "target", "y", "block_type", "type", "tag", "label_name"]
COMMON_WORDS_FIELDS = ["words", "tokens"]
COMMON_BOXES_FIELDS = ["boxes", "bboxes", "bbox"]

def _lower_keys(d):
    return {k.lower(): k for k in d.keys()}

def autodetect_field(records, candidates):
    """
    Find the first candidate that appears (case-insensitively) in any record.
    Returns the original-cased key, or None if not found.
    """
    for cand in candidates:
        cand_l = cand.lower()
        for r in records:
            lk = _lower_keys(r)
            if cand_l in lk:
                return lk[cand_l]
    return None

def get_field_name(records, user_value, candidates, required=True, field_name=""):
    """
    Decide which field to use: prefer user_value; otherwise, auto-detect from candidates.
    """
    if user_value:
        return user_value
    found = autodetect_field(records, candidates)
    if not found and required:
        # show available keys to help
        all_keys = sorted(set(itertools.chain.from_iterable(r.keys() for r in records[:100])))
        raise KeyError(
            f"Could not find {field_name or 'required'} field. "
            f"Tried {candidates}. Available keys include: {all_keys[:30]}"
        )
    return found

def make_training_args(**kwargs) -> TrainingArguments:
    """Create TrainingArguments while dropping unsupported kwargs (version-safe)."""
    supported = set(inspect.signature(TrainingArguments.__init__).parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in supported}
    return TrainingArguments(**filtered)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def build_label_map(records, label_field):
    labels = sorted({r[label_field] for r in records})
    return {lbl: i for i, lbl in enumerate(labels)}


# ------------------------ Datasets ------------------------
class TextDataset(Dataset):
    def __init__(self, records: List[Dict[str, Any]], tokenizer, label2id: Dict[str, int], max_length: int = 256):
        self.records = records
        self.tokenizer = tokenizer
        self.label2id = label2id
        self.max_length = max_length

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        text = rec.get("text", "")
        label = self.label2id[rec["label"]]
        enc = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(label, dtype=torch.long)
        return item


class LayoutDataset(Dataset):
    def __init__(self, records: List[Dict[str, Any]], processor, label2id: Dict[str, int], max_length: int = 512):
        self.records = records
        self.processor = processor
        self.label2id = label2id
        self.max_length = max_length

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        words = rec.get("words")
        boxes = rec.get("boxes")
        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            raise ValueError("Layout dataset requires 'words': List[str]")
        if not isinstance(boxes, list) or not all(isinstance(b, list) and len(b) == 4 for b in boxes):
            raise ValueError("Layout dataset requires 'boxes': List[List[int]] with [x0,y0,x1,y1]")
        if len(words) != len(boxes):
            raise ValueError("Length of 'words' and 'boxes' must match")

        enc = self.processor(
            text=words,
            boxes=boxes,
            is_split_into_words=True,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(self.label2id[rec["label"]], dtype=torch.long)
        return item


# ------------------------ Metrics ------------------------
def compute_metrics(eval_pred):
    preds, labels = eval_pred
    if isinstance(preds, (list, tuple)):
        preds = preds[0]
    preds = np.argmax(preds, axis=-1)
    acc = (preds == labels).mean().item() if hasattr((preds == labels), "mean") else float(np.mean(preds == labels))
    # simple F1 macro without external deps
    f1 = 0.0
    try:
        # manual macro-F1
        unique = sorted(set(labels.tolist() if hasattr(labels, "tolist") else list(labels)))
        f1s = []
        for c in unique:
            tp = int(((preds == c) & (labels == c)).sum())
            fp = int(((preds == c) & (labels != c)).sum())
            fn = int(((preds != c) & (labels == c)).sum())
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1c = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            f1s.append(f1c)
        f1 = float(np.mean(f1s)) if f1s else 0.0
    except Exception:
        pass
    return {"accuracy": float(acc), "f1": float(f1)}


# ------------------------ Main ------------------------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("dataset", type=Path, help="Path to JSONL dataset")
    p.add_argument("--output", type=Path, required=True, help="Output directory to save model")
    p.add_argument("--backbone", choices=["bert", "layoutlmv3"], default="bert", help="Model family to use")
    p.add_argument("--pretrained", type=str, default=None, help="Override the pretrained model name")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--lr", type=float, default=5e-5, help="Learning rate")
    p.add_argument("--max-length", type=int, default=256, help="Max sequence length (text path).")
    p.add_argument("--max-length-layout", type=int, default=512, help="Max sequence length (layout path).")
    p.add_argument("--eval-steps", type=int, default=200)
    p.add_argument("--save-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--text-field", type=str, default=None, help="Name of the text field (default: auto-detect)")
    p.add_argument("--label-field", type=str, default=None, help="Name of the label field (default: auto-detect)")
    p.add_argument("--words-field", type=str, default=None, help="Name of the words field for LayoutLMv3 (default: auto-detect)")
    p.add_argument("--boxes-field", type=str, default=None, help="Name of the boxes field for LayoutLMv3 (default: auto-detect)")
    return p.parse_args()


def main():
    args = parse_args()
    records = load_jsonl(args.dataset)
    logger.info("Loaded %d records from %s", len(records), args.dataset)

    # Resolve which fields to use (auto-detect if not provided)
    TEXT_FIELD  = get_field_name(records, args.text_field,  COMMON_TEXT_FIELDS,  required=(args.backbone == "bert"), field_name="text")
    LABEL_FIELD = get_field_name(records, args.label_field, COMMON_LABEL_FIELDS, required=True,                     field_name="label")

    if args.backbone == "layoutlmv3":
        WORDS_FIELD = get_field_name(records, args.words_field, COMMON_WORDS_FIELDS, required=True,  field_name="words")
        BOXES_FIELD = get_field_name(records, args.boxes_field, COMMON_BOXES_FIELDS, required=True,  field_name="boxes")
    else:
        WORDS_FIELD = None
        BOXES_FIELD = None

    # Split simple train/val (90/10) deterministically
    rng = np.random.default_rng(args.seed)
    idx = np.arange(len(records))
    rng.shuffle(idx)
    split = int(0.9 * len(idx))
    train_idx, val_idx = idx[:split], idx[split:]
    train_records = [records[i] for i in train_idx]
    val_records = [records[i] for i in val_idx]

    label2id = build_label_map(records, LABEL_FIELD)
    id2label = {v: k for k, v in label2id.items()}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "label_map.json").write_text(json.dumps(label2id, indent=2), encoding="utf-8")

    if args.backbone == "layoutlmv3":
        if not HAS_LAYOUTLMV3:
            raise RuntimeError("transformers install lacks LayoutLMv3. Please install a recent transformers.")
        pretrained = args.pretrained or "microsoft/layoutlmv3-base"
        processor = LayoutLMv3Processor.from_pretrained(pretrained, apply_ocr=False)
        model = LayoutLMv3ForSequenceClassification.from_pretrained(
            pretrained, num_labels=len(label2id), id2label=id2label, label2id=label2id
        )
        train_ds = LayoutDataset(train_records, processor, label2id, max_length=args.max_length_layout)
        val_ds = LayoutDataset(val_records, processor, label2id, max_length=args.max_length_layout)
        data_collator = None  # processor handles padding
        tok_or_proc = processor
    else:
        pretrained = args.pretrained or "bert-base-uncased"
        tokenizer = AutoTokenizer.from_pretrained(pretrained)
        model = AutoModelForSequenceClassification.from_pretrained(
            pretrained, num_labels=len(label2id), id2label=id2label, label2id=label2id
        )
        train_ds = TextDataset(train_records, tokenizer, label2id, max_length=args.max_length)
        val_ds = TextDataset(val_records, tokenizer, label2id, max_length=args.max_length)
        data_collator = DataCollatorWithPadding(tokenizer)
        tok_or_proc = tokenizer

    training_args = make_training_args(
        output_dir=str(args.output),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        weight_decay=0.01,
        eval_strategy="steps",          # your installed version expects eval_strategy
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.save_steps,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_steps=10,
        seed=args.seed,
        remove_unused_columns=False,    # important for layout models
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tok_or_proc,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    # Save final model + tokenizer/processor
    tok_or_proc.save_pretrained(args.output)
    model.save_pretrained(args.output)
    logger.info("Saved model to %s", args.output)


if __name__ == "__main__":
    main()
