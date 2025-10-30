from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - gracefully degrade when dotenv unavailable
    load_dotenv = None

logger = logging.getLogger(__name__)


_FALSE_VALUES = {"0", "false", "no", "off"}


def _prepare_env() -> None:
    """Load environment variables from ``.env`` when available."""

    if load_dotenv is not None:
        load_dotenv(override=False)


def export_intermediate_artifacts_enabled() -> bool:
    """Return ``True`` when intermediate assets should be exported."""

    _prepare_env()
    raw_value = os.getenv("EXPORT_INTERMEDIATE_ARTIFACTS")
    if raw_value is None:
        return True
    return raw_value.strip().lower() not in _FALSE_VALUES


@dataclass(frozen=True)
class OpenAIConfig:
    """Runtime configuration for the OpenAI formatting workflow."""

    api_key: str
    model: str
    base_url: Optional[str] = None

    @classmethod
    def load(cls) -> Optional["OpenAIConfig"]:
        """Load settings from the environment.

        Environment variables are the canonical configuration surface. When the
        optional :mod:`python-dotenv` package is installed, values from a local
        ``.env`` file are also loaded to ease development.
        """

        _prepare_env()

        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_API_MODEL")
        base_url = os.getenv("OPENAI_API_BASE_URL") or None

        if not api_key or not model:
            logger.debug(
                "OpenAI configuration is incomplete (api_key or model missing); "
                "AI formatting workflow will be disabled."
            )
            return None

        return cls(api_key=api_key, model=model, base_url=base_url)
