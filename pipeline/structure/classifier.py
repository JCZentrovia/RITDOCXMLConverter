from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional heavy dependencies
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except Exception as exc:  # pragma: no cover - dependency missing
    torch = None  # type: ignore[assignment]
    AutoModelForSequenceClassification = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    _TRANSFORMERS_AVAILABLE = False
    _TRANSFORMERS_IMPORT_ERROR = str(exc)
else:  # pragma: no cover - exercised only when deps available
    _TRANSFORMERS_AVAILABLE = True
    _TRANSFORMERS_IMPORT_ERROR = ""

_CLASSIFIER_CACHE: Dict[str, "BaseBlockClassifier"] = {}


@dataclass
class ClassificationResult:
    label: str
    confidence: float


class BaseBlockClassifier:
    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or {}

    def classify(self, blocks: Sequence[dict]) -> List[dict]:
        raise NotImplementedError


class StubBlockClassifier(BaseBlockClassifier):
    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self.abstain_label = self.config.get("abstain_label", "abstain")
        self.fallback_label = self.config.get("fallback_label", "para")
        self.log_predictions = bool(self.config.get("monitoring", {}).get("log_predictions"))

    def classify(self, blocks: Sequence[dict]) -> List[dict]:
        results: List[dict] = []
        for block in blocks:
            label = block.get("label") or self.fallback_label
            result = {
                **block,
                "classifier_label": label,
                "classifier_confidence": 1.0,
            }
            results.append(result)
        if self.log_predictions:
            logger.debug("Stub classifier emitted %s labels", len(results))
        return results


class HuggingFaceBlockClassifier(BaseBlockClassifier):
    def __init__(self, config: Optional[dict] = None) -> None:
        if not _TRANSFORMERS_AVAILABLE:  # pragma: no cover - depends on env
            raise RuntimeError(f"transformers unavailable: {_TRANSFORMERS_IMPORT_ERROR}")
        super().__init__(config)
        self.model_name_or_path = self.config.get("model_path") or self.config.get("model_name_or_path") or self.config.get("model_name")
        if not self.model_name_or_path:
            raise ValueError("HuggingFace classifier requires 'model_path' or 'model_name'")
        self.max_length = int(self.config.get("max_length", 256))
        self.batch_size = int(self.config.get("batch_size", 8))
        self.threshold = float(self.config.get("threshold", 0.5))
        self.abstain_label = self.config.get("abstain_label", "abstain")
        self.fallback_label = self.config.get("fallback_label", "para")
        self.device = torch.device(self.config.get("device", "cuda" if torch.cuda.is_available() else "cpu"))
        model_path = Path(self.model_name_or_path)
        if model_path.exists() and model_path.is_dir():
            config_path = model_path / "config.json"
            if not config_path.exists():
                raise FileNotFoundError(
                    "HuggingFace classifier model path "
                    f"'{self.model_name_or_path}' does not contain a config.json file. "
                    "Ensure the trained model artifacts are available or disable the classifier."
                )
        self._model = None
        self._tokenizer = None
        self._id_to_label: Dict[int, str] = {}
        self._label_map_path = Path(self.config.get("label_map_path") or "") if self.config.get("label_map_path") else None
        self._log_predictions = bool(self.config.get("monitoring", {}).get("log_predictions"))

    # ------------------------------------------------------------------
    # Lazy loading helpers
    # ------------------------------------------------------------------
    def _label_map_candidates(self) -> List[Path]:
        candidates: List[Path] = []
        if self._label_map_path:
            candidates.append(self._label_map_path)
        model_path = Path(self.model_name_or_path)
        candidates.append(model_path / "label_map.json")
        candidates.append(model_path / "labels.json")
        return candidates

    def _load_label_map(self) -> Dict[str, int]:
        for candidate in self._label_map_candidates():
            if candidate.exists():
                mapping = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(mapping, dict):
                    return {str(label): int(idx) for label, idx in mapping.items()}
                if isinstance(mapping, list):
                    return {str(label): idx for idx, label in enumerate(mapping)}
        logger.warning("Label map not found for classifier at %s; using model config order", self.model_name_or_path)
        return {}

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        label_to_id = self._load_label_map()
        tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_name_or_path)
        if not label_to_id:
            label_to_id = model.config.label2id or {label: idx for idx, label in enumerate(model.config.id2label.values())}
        self._id_to_label = {int(idx): label for label, idx in label_to_id.items()}
        if not self._id_to_label:
            self._id_to_label = {idx: label for idx, label in model.config.id2label.items()}
        model.to(self.device)
        model.eval()
        self._model = model
        self._tokenizer = tokenizer
        logger.info("Loaded HuggingFace classifier from %s on %s", self.model_name_or_path, self.device)

    # ------------------------------------------------------------------
    # Encoding helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_bbox(geometry: Optional[dict]) -> List[int]:
        if not geometry:
            return [0, 0, 0, 0]
        left = float(geometry.get("left", 0.0))
        top = float(geometry.get("top", 0.0))
        width = float(geometry.get("width", 0.0))
        height = float(geometry.get("height", 0.0))
        right = left + width
        bottom = top + height
        max_dim = max(right, bottom, 1.0)
        scale = 1000.0 / max_dim
        x0 = int(max(0.0, min(1000.0, round(left * scale))))
        y0 = int(max(0.0, min(1000.0, round(top * scale))))
        x1 = int(max(0.0, min(1000.0, round(right * scale))))
        y1 = int(max(0.0, min(1000.0, round(bottom * scale))))
        return [x0, y0, x1, y1]

    def _encode_block(self, block: dict) -> Dict[str, List[int]]:
        text = str(block.get("text") or "")
        encoding = self._tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_attention_mask=True,
        )
        geometry = block.get("bbox") or block.get("geometry")
        bbox = self._normalise_bbox(geometry)
        encoding["bbox"] = [bbox] * len(encoding["input_ids"])
        return encoding

    def _batch(self, encodings: Sequence[Dict[str, List[int]]]) -> Dict[str, torch.Tensor]:
        if not encodings:
            return {}
        batch: Dict[str, torch.Tensor] = {}
        keys = encodings[0].keys()
        for key in keys:
            values = [encoding[key] for encoding in encodings]
            tensor_list = [torch.tensor(value) for value in values]
            batch[key] = torch.stack(tensor_list).to(self.device)
        return batch

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def classify(self, blocks: Sequence[dict]) -> List[dict]:
        self._ensure_model()
        if not blocks:
            return []
        assert self._model is not None and self._tokenizer is not None
        results: List[dict] = []
        encodings: List[Dict[str, List[int]]] = []
        index_map: List[int] = []
        for idx, block in enumerate(blocks):
            text = str(block.get("text") or "").strip()
            if not text:
                results.append(
                    {
                        **block,
                        "classifier_label": self.fallback_label,
                        "classifier_confidence": 0.0,
                    }
                )
                continue
            encodings.append(self._encode_block(block))
            index_map.append(idx)
            results.append({})  # placeholder
        if not encodings:
            return [
                {
                    **block,
                    "classifier_label": self.fallback_label,
                    "classifier_confidence": 0.0,
                }
                for block in blocks
            ]

        with torch.no_grad():
            start = 0
            predictions: List[ClassificationResult] = []
            while start < len(encodings):
                chunk = encodings[start : start + self.batch_size]
                start += self.batch_size
                batch_inputs = self._batch(chunk)
                outputs = self._model(**batch_inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)
                scores, indices = probs.max(dim=-1)
                for score, index in zip(scores.cpu().tolist(), indices.cpu().tolist()):
                    label = self._id_to_label.get(int(index), str(index))
                    predictions.append(ClassificationResult(label=label, confidence=float(score)))

        abstained = 0
        for idx, result_index in enumerate(index_map):
            prediction = predictions[idx]
            if prediction.confidence < self.threshold:
                label = self.abstain_label
                abstained += 1
            else:
                label = prediction.label
            results[result_index] = {
                **blocks[result_index],
                "classifier_label": label,
                "classifier_confidence": prediction.confidence,
            }

        # Fill placeholders for empty-text blocks
        for idx, block in enumerate(blocks):
            if results[idx]:
                continue
            results[idx] = {
                **block,
                "classifier_label": self.fallback_label,
                "classifier_confidence": 0.0,
            }

        if self._log_predictions:
            coverage = 1 - abstained / max(len(blocks), 1)
            logger.info(
                "HF classifier processed %s blocks (threshold %.2f, coverage %.1f%%)",
                len(blocks),
                self.threshold,
                coverage * 100,
            )
        return results


def _config_cache_key(config: dict) -> str:
    serialisable = json.dumps(config, sort_keys=True, default=str)
    return serialisable


def get_classifier(config: Optional[dict]) -> BaseBlockClassifier:
    cfg = config or {}
    cache_key = _config_cache_key(cfg)
    if cache_key in _CLASSIFIER_CACHE:
        return _CLASSIFIER_CACHE[cache_key]

    backend = cfg.get("backend", "huggingface")
    if not cfg.get("enabled", False):
        classifier = StubBlockClassifier(cfg)
    elif backend == "huggingface":
        try:
            classifier = HuggingFaceBlockClassifier(cfg)
        except Exception as exc:  # pragma: no cover - depends on runtime env
            logger.warning("Falling back to stub classifier: %s", exc)
            classifier = StubBlockClassifier(cfg)
    else:
        logger.warning("Unknown classifier backend '%s'; using stub", backend)
        classifier = StubBlockClassifier(cfg)

    _CLASSIFIER_CACHE[cache_key] = classifier
    return classifier


def classify_blocks(blocks: Sequence[dict], config: Optional[dict]) -> List[dict]:
    classifier = get_classifier(config)
    return classifier.classify(blocks)


__all__ = ["classify_blocks", "get_classifier", "BaseBlockClassifier"]
