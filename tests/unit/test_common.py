import json
from pathlib import Path

from pipeline.common import checksum, load_mapping, merge_dicts, normalize_text


def test_normalize_text_collapse_whitespace():
    config = {"normalization": {"collapse_internal_whitespace": True}}
    text = "Hello\tworld\nthis  is"
    normalized = normalize_text(text, config)
    assert normalized == "Hello world this is"


def test_checksum_stable():
    assert checksum("abc") == checksum("abc")


def test_merge_dicts_deep():
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    override = {"a": {"c": 5}, "e": 6}
    merged = merge_dicts(base, override)
    assert merged["a"]["c"] == 5
    assert merged["e"] == 6


def test_load_mapping(tmp_path: Path):
    default = tmp_path / "mapping.default.json"
    json.dump({"docbook": {"root": "book"}}, default.open("w", encoding="utf-8"))
    publishers = tmp_path / "publishers"
    publishers.mkdir()
    json.dump({"docbook": {"root": "article"}}, (publishers / "pub.json").open("w", encoding="utf-8"))
    mapping = load_mapping(tmp_path, "pub")
    assert mapping["docbook"]["root"] == "article"
