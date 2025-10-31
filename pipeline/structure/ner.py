"""Named entity recognition helpers for block annotations."""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from transformers import pipeline as hf_pipeline
except Exception as exc:  # pragma: no cover - gracefully degrade when unavailable
    hf_pipeline = None
    _TRANSFORMERS_AVAILABLE = False
    _TRANSFORMERS_IMPORT_ERROR = str(exc)
else:  # pragma: no cover - exercised only when deps available
    _TRANSFORMERS_AVAILABLE = True
    _TRANSFORMERS_IMPORT_ERROR = ""

_NER_CACHE: Dict[str, "BaseNamedEntityRecognizer"] = {}

_DEFAULT_LABEL_GROUPS = {
    "person": ["PER", "PERSON"],
    "organization": ["ORG", "ORGANIZATION"],
    "location": ["LOC", "LOCATION"],
    "date": ["DATE"],
    "misc": ["MISC", "TITLE", "WORK_OF_ART", "EVENT"],
}

_PERSON_SUFFIXES = {"Jr", "Jr.", "Sr", "Sr.", "II", "III", "IV", "V"}
_PERSON_PREFIXES = {"Dr", "Dr.", "Mr", "Mr.", "Mrs", "Mrs.", "Ms", "Ms.", "Prof", "Prof."}


class BaseNamedEntityRecognizer:
    """Base interface for NER backends."""

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or {}

    def annotate(self, blocks: Sequence[dict]) -> List[dict]:
        raise NotImplementedError


class StubNamedEntityRecognizer(BaseNamedEntityRecognizer):
    """Fallback recognizer when no backend is available."""

    def annotate(self, blocks: Sequence[dict]) -> List[dict]:
        results: List[dict] = []
        for block in blocks:
            new_block = dict(block)
            new_block.pop("entities", None)
            results.append(new_block)
        if self.config.get("enabled"):
            logger.warning("Named entity recognition requested but unavailable; using stub backend")
        return results


class HuggingFaceNamedEntityRecognizer(BaseNamedEntityRecognizer):
    """NER powered by HuggingFace token-classification pipelines."""

    def __init__(self, config: Optional[dict] = None) -> None:
        if not _TRANSFORMERS_AVAILABLE:  # pragma: no cover - depends on runtime env
            raise RuntimeError(f"transformers unavailable: {_TRANSFORMERS_IMPORT_ERROR}")
        super().__init__(config)
        self.model_name = self.config.get("model_name") or self.config.get("model_path")
        if not self.model_name:
            raise ValueError("NER configuration requires 'model_name' or 'model_path'")

        aggregation_strategy = self.config.get("aggregation_strategy", "simple")
        model_kwargs = self.config.get("model_kwargs") or {}
        tokenizer_kwargs = self.config.get("tokenizer_kwargs") or {}
        device = self.config.get("device")

        pipeline_kwargs = {
            "model": self.model_name,
            "tokenizer": self.model_name,
            "aggregation_strategy": aggregation_strategy,
        }
        if model_kwargs:
            pipeline_kwargs["model_kwargs"] = model_kwargs
        if tokenizer_kwargs:
            pipeline_kwargs["tokenizer_kwargs"] = tokenizer_kwargs
        if device is not None:
            pipeline_kwargs["device"] = device

        self._pipeline = hf_pipeline("token-classification", **pipeline_kwargs)

        label_groups = self.config.get("label_groups") or _DEFAULT_LABEL_GROUPS
        self._label_lookup = self._build_label_lookup(label_groups)
        eligible_labels = self.config.get("eligible_block_labels") or ["para", "footnote", "list_item"]
        self._eligible_labels = {label.lower() for label in eligible_labels}
        self._max_text_length = int(self.config.get("max_text_length", 2000))
        self._min_score = float(self.config.get("min_score", 0.0))

        logger.info("Loaded HuggingFace NER pipeline '%s' with strategy '%s'", self.model_name, aggregation_strategy)

    @staticmethod
    def _build_label_lookup(label_groups: Dict[str, Iterable[str]]) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for normalised, labels in label_groups.items():
            for label in labels:
                lookup[str(label).upper()] = normalised.lower()
        return lookup

    def annotate(self, blocks: Sequence[dict]) -> List[dict]:  # pragma: no cover - requires heavy deps
        annotated: List[dict] = []
        for block in blocks:
            new_block = dict(block)
            text = str(block.get("text") or "")
            clean_text = text.strip()
            if not clean_text:
                new_block.pop("entities", None)
                annotated.append(new_block)
                continue

            label = (block.get("classifier_label") or block.get("label") or "").lower()
            if self._eligible_labels and label and label not in self._eligible_labels:
                new_block.pop("entities", None)
                annotated.append(new_block)
                continue

            if self._max_text_length and len(clean_text) > self._max_text_length:
                logger.debug(
                    "Skipping NER for block exceeding max length (%d chars)",
                    len(clean_text),
                )
                new_block.pop("entities", None)
                annotated.append(new_block)
                continue

            try:
                raw_entities = self._pipeline(clean_text)
            except Exception as exc:
                logger.warning("NER pipeline failed for text '%s...': %s", clean_text[:40], exc)
                new_block.pop("entities", None)
                annotated.append(new_block)
                continue

            entities = self._normalise_entities(clean_text, raw_entities)
            if entities:
                new_block["entities"] = entities
            else:
                new_block.pop("entities", None)
            annotated.append(new_block)
        return annotated

    def _normalise_entities(self, text: str, raw_entities: Sequence[dict]) -> List[dict]:
        entities: List[dict] = []
        for entry in raw_entities:
            score = float(entry.get("score", 0.0))
            if score < self._min_score:
                continue

            label = entry.get("entity_group") or entry.get("entity")
            if not label:
                continue
            normalised = self._label_lookup.get(str(label).upper())
            if not normalised:
                continue

            start = int(entry.get("start", 0))
            end = int(entry.get("end", start))
            start = max(0, min(len(text), start))
            end = max(start, min(len(text), end))
            if start == end:
                continue
            segment = text[start:end]
            segment_clean = segment.strip()
            if not segment_clean:
                continue

            entity: Dict[str, object] = {
                "label": normalised,
                "original_label": label,
                "start": start,
                "end": end,
                "text": segment_clean,
                "score": score,
            }

            if normalised == "person":
                entity["type"] = "person"
                entity["person"] = _split_person_name(segment_clean)
            else:
                entity["type"] = normalised
            entities.append(entity)
        return entities


def _split_person_name(name: str) -> Dict[str, object]:
    """Split a full name into DocBook-friendly components."""

    cleaned = name.strip()
    if not cleaned:
        return {}

    tokens = [token for token in re.split(r"[\s,]+", cleaned) if token]
    if not tokens:
        return {}

    prefix = None
    if tokens and tokens[0] in _PERSON_PREFIXES:
        prefix = tokens.pop(0)

    suffix = None
    if tokens and tokens[-1] in _PERSON_SUFFIXES:
        suffix = tokens.pop()

    if not tokens:
        return {"prefix": prefix, "suffix": suffix}

    first = tokens[0]
    if len(tokens) == 1:
        components = {"first": first}
    else:
        last = tokens[-1]
        middle = tokens[1:-1]
        components = {"first": first, "last": last}
        if middle:
            components["middle"] = middle

    if prefix:
        components["prefix"] = prefix
    if suffix:
        components["suffix"] = suffix
    return components


def _config_cache_key(config: dict) -> str:
    return json.dumps(config, sort_keys=True, default=str)


def get_named_entity_recognizer(config: Optional[dict]) -> BaseNamedEntityRecognizer:
    cfg = config or {}
    cache_key = _config_cache_key(cfg)
    if cache_key in _NER_CACHE:
        return _NER_CACHE[cache_key]

    backend = cfg.get("backend", "huggingface")
    if not cfg.get("enabled", False):
        recognizer: BaseNamedEntityRecognizer = StubNamedEntityRecognizer(cfg)
    elif backend == "huggingface":
        try:
            recognizer = HuggingFaceNamedEntityRecognizer(cfg)
        except Exception as exc:  # pragma: no cover - depends on runtime env
            logger.warning("Falling back to stub NER backend: %s", exc)
            recognizer = StubNamedEntityRecognizer(cfg)
    else:
        logger.warning("Unknown NER backend '%s'; using stub", backend)
        recognizer = StubNamedEntityRecognizer(cfg)

    _NER_CACHE[cache_key] = recognizer
    return recognizer


def annotate_blocks_with_entities(blocks: Sequence[dict], config: Optional[dict]) -> List[dict]:
    """Annotate blocks with named entities based on configuration."""

    recognizer = get_named_entity_recognizer(config)
    return recognizer.annotate(blocks)


__all__ = [
    "annotate_blocks_with_entities",
    "get_named_entity_recognizer",
    "BaseNamedEntityRecognizer",
]

