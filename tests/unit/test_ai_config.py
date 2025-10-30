from __future__ import annotations

import os

from pipeline.ai.config import (
    OpenAIConfig,
    export_intermediate_artifacts_enabled,
)


def test_openai_config_load_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_MODEL", raising=False)
    assert OpenAIConfig.load() is None


def test_openai_config_load_reads_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_BASE_URL", "https://example.com/v1")

    config = OpenAIConfig.load()
    assert config is not None
    assert config.api_key == "test-key"
    assert config.model == "gpt-4o-mini"
    assert config.base_url == "https://example.com/v1"


def test_export_intermediate_artifacts_enabled_defaults_true(monkeypatch):
    monkeypatch.delenv("EXPORT_INTERMEDIATE_ARTIFACTS", raising=False)
    assert export_intermediate_artifacts_enabled() is True


def test_export_intermediate_artifacts_enabled_false(monkeypatch):
    monkeypatch.setenv("EXPORT_INTERMEDIATE_ARTIFACTS", "false")
    assert export_intermediate_artifacts_enabled() is False
