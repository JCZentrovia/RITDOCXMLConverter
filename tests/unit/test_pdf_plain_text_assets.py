from __future__ import annotations

from pipeline.common import PageText
from pipeline.pdf_pipeline import _write_plain_text_assets


def test_write_plain_text_assets_creates_files(tmp_path):
    pages = [
        PageText(page_num=1, raw_text="Hello", norm_text="Hello", checksum="1"),
        PageText(page_num=2, raw_text="World", norm_text="World", checksum="2"),
    ]

    assets, combined_path, combined_text = _write_plain_text_assets(
        pages, tmp_path, export=True
    )

    asset_hrefs = [href for href, _ in assets]
    assert "plain_text/page_0001.txt" in asset_hrefs
    assert "plain_text/page_0002.txt" in asset_hrefs
    assert "plain_text/full_text.txt" in asset_hrefs
    assert combined_path.read_text(encoding="utf-8") == "Hello\nWorld"
    assert combined_text == "Hello\nWorld"


def test_write_plain_text_assets_can_skip_export(tmp_path):
    pages = [
        PageText(page_num=1, raw_text="Hello", norm_text="Hello", checksum="1"),
        PageText(page_num=2, raw_text="World", norm_text="World", checksum="2"),
    ]

    assets, combined_path, combined_text = _write_plain_text_assets(
        pages, tmp_path, export=False
    )

    assert assets == []
    assert combined_path is None
    assert combined_text == "Hello\nWorld"
