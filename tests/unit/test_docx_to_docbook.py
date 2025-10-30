from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

docx_mod = pytest.importorskip("docx")
Document = docx_mod.Document

from pipeline.ai.docx_to_docbook import convert_docx_to_docbook


def _make_sample_docx(path: Path) -> None:
    document = Document()
    document.add_heading("Chapter One", level=1)
    document.add_paragraph("This is the first paragraph.")
    document.add_paragraph("This is the second paragraph.")
    document.save(path)


def test_convert_docx_to_docbook_round_trips_text(tmp_path):
    docx_path = tmp_path / "sample.docx"
    _make_sample_docx(docx_path)

    expected_text = "\n".join(
        ["Chapter One", "This is the first paragraph.", "This is the second paragraph."]
    )
    xml_path = convert_docx_to_docbook(docx_path, expected_text=expected_text)

    tree = etree.parse(str(xml_path))
    titles = tree.findall(".//title")
    paras = tree.findall(".//para")

    assert len(titles) == 1
    assert titles[0].text == "Chapter One"
    assert [para.text for para in paras] == [
        "This is the first paragraph.",
        "This is the second paragraph.",
    ]


def test_convert_docx_to_docbook_detects_text_drift(tmp_path):
    docx_path = tmp_path / "sample.docx"
    _make_sample_docx(docx_path)

    with pytest.raises(ValueError):
        convert_docx_to_docbook(docx_path, expected_text="Different text")
