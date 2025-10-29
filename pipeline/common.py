from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NormalizationEvent:
    rule: str
    before: str
    after: str


@dataclass
class PageText:
    page_num: int
    raw_text: str
    norm_text: str
    checksum: str
    has_ocr: bool = False
    events: List[NormalizationEvent] = field(default_factory=list)


_whitespace_re = re.compile(r"\s+")
_line_dehyphen_re = re.compile(r"(?m)(\w+)-\n(\w+)")


def _collapse_whitespace(text: str) -> str:
    return _whitespace_re.sub(" ", text)


def _safe_dehyphenate(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        first, second = match.group(1), match.group(2)
        if first.isupper() and second.isupper():
            return f"{first}-{second}"
        return f"{first}{second}"

    return _line_dehyphen_re.sub(repl, text)


NORMALIZATION_RULES = {
    "collapse_internal_whitespace": _collapse_whitespace,
    "dehyphenate_line_endings": _safe_dehyphenate,
}


def merge_dicts(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def load_mapping(config_dir: Path, publisher: str | None = None) -> dict:
    import json

    default_path = config_dir / "mapping.default.json"
    with default_path.open("r", encoding="utf-8") as fh:
        config = json.load(fh)
    if publisher:
        publisher_path_json = config_dir / "publishers" / f"{publisher}.json"
        if publisher_path_json.exists():
            with publisher_path_json.open("r", encoding="utf-8") as fh:
                config = merge_dicts(config, json.load(fh))
    return config


def normalize_text(text: str, config: dict, events: Optional[List[NormalizationEvent]] = None) -> str:
    if events is None:
        events = []
    original = text
    normalization_cfg = config.get("normalization", {})
    result = text

    if normalization_cfg.get("collapse_internal_whitespace"):
        collapsed = _collapse_whitespace(result)
        if collapsed != result:
            events.append(NormalizationEvent("collapse_internal_whitespace", result, collapsed))
            result = collapsed

    mode = normalization_cfg.get("dehyphenate_line_endings")
    if mode in {"safe", True}:
        dehyphenated = _safe_dehyphenate(result)
        if dehyphenated != result:
            events.append(NormalizationEvent("dehyphenate_line_endings", result, dehyphenated))
            result = dehyphenated

    if normalization_cfg.get("preserve_ligatures"):
        # No-op placeholder; ligatures preserved by default.
        pass

    if normalization_cfg.get("log_every_change", False) and events and result != original:
        for event in events:
            logger.debug("Normalization %s: '%s' -> '%s'", event.rule, event.before, event.after)

    return result


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(args: Iterable[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> str:
    logger.debug("Running command: %s", " ".join(map(str, args)))
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    proc = subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=proc_env,
    )
    if proc.returncode != 0:
        logger.error("Command failed (%s): %s", proc.returncode, proc.stderr.strip())
        raise RuntimeError(f"Command {' '.join(args)} failed: {proc.stderr.strip()}")
    if proc.stderr:
        logger.debug("Command stderr: %s", proc.stderr.strip())
    return proc.stdout
