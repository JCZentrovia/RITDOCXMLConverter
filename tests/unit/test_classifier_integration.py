from __future__ import annotations

from copy import deepcopy

import pytest

from pipeline.structure import classifier


@pytest.fixture(autouse=True)
def clear_classifier_cache():
    classifier._CLASSIFIER_CACHE.clear()
    yield
    classifier._CLASSIFIER_CACHE.clear()


def test_classify_blocks_stub_when_disabled():
    blocks = [
        {"text": "Example", "label": "para"},
        {"text": "Title", "label": "chapter"},
    ]
    result = classifier.classify_blocks(blocks, {"enabled": False, "fallback_label": "para"})
    assert [block["classifier_label"] for block in result] == ["para", "chapter"]
    assert all(block["classifier_confidence"] == 1.0 for block in result)


def test_classify_blocks_missing_transformers_falls_back(monkeypatch):
    monkeypatch.setattr(classifier, "_TRANSFORMERS_AVAILABLE", False, raising=False)
    monkeypatch.setattr(classifier, "_TRANSFORMERS_IMPORT_ERROR", "missing", raising=False)
    config = {"enabled": True, "backend": "huggingface", "fallback_label": "fallback"}
    blocks = [{"text": "Example", "label": "para"}]
    result = classifier.classify_blocks(blocks, config)
    assert result[0]["classifier_label"] == "para"
    assert result[0]["classifier_confidence"] == 1.0


def test_get_classifier_caches_instances():
    config = {"enabled": False, "backend": "huggingface"}
    first = classifier.get_classifier(config)
    second = classifier.get_classifier(deepcopy(config))
    assert first is second
