from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from pipeline.structure.dataset_builder import (
    align_blocks,
    build_dataset,
    load_docbook_blocks,
    save_dataset_jsonl,
    summarise_dataset,
)


def _create_docbook_archive(tmp_path: Path) -> Path:
    chapter = """
    <chapter id="ch01">
      <title>Sample Chapter</title>
      <para>Introductory paragraph.</para>
      <sect1 id="sec1">
        <title>Background</title>
        <para>Background content.</para>
        <itemizedlist>
          <listitem><para>Bullet point</para></listitem>
        </itemizedlist>
      </sect1>
    </chapter>
    """.strip()
    archive = tmp_path / "sample.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("ch0001.xml", chapter)
    return archive


def test_load_docbook_blocks(tmp_path):
    archive = _create_docbook_archive(tmp_path)
    blocks = load_docbook_blocks(archive)
    labels = {block.label for block in blocks}
    assert "chapter.title" in labels
    assert "para" in labels
    assert any(block.label.endswith(".item") for block in blocks)


def test_align_blocks_assigns_labels(tmp_path):
    archive = _create_docbook_archive(tmp_path)
    docbook_blocks = load_docbook_blocks(archive)
    pdf_blocks = [
        {"text": "Sample Chapter", "bbox": {"left": 10, "top": 10, "width": 400, "height": 40}, "page_num": 1, "font_size": 18, "label": "heading"},
        {"text": "Introductory paragraph.", "bbox": {"left": 20, "top": 60, "width": 380, "height": 60}, "page_num": 1, "font_size": 12, "label": "para"},
        {"text": "Background", "bbox": {"left": 10, "top": 140, "width": 300, "height": 40}, "page_num": 1, "font_size": 16, "label": "heading"},
        {"text": "Background content.", "bbox": {"left": 20, "top": 180, "width": 380, "height": 60}, "page_num": 1, "font_size": 12, "label": "para"},
        {"text": "Bullet point", "bbox": {"left": 40, "top": 240, "width": 360, "height": 40}, "page_num": 1, "font_size": 12, "label": "list"},
    ]
    aligned = align_blocks(pdf_blocks, docbook_blocks, source_id="sample")
    assert len(aligned) == len(pdf_blocks)
    labels = [example.dct_label for example in aligned]
    assert labels[0] == "chapter.title"
    assert labels[1] == "para"
    assert labels[-1].endswith(".item")


def test_build_dataset_uses_stub_provider(tmp_path):
    archive = _create_docbook_archive(tmp_path)
    root = tmp_path / "ConversionExamples"
    example_dir = root / "Example"
    input_dir = example_dir / "Input"
    output_dir = example_dir / "Output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    pdf_path = input_dir / "example.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    target_zip = output_dir / "example.zip"
    target_zip.write_bytes(archive.read_bytes())

    pdf_blocks = [
        {"text": "Sample Chapter", "bbox": {"left": 0, "top": 0, "width": 1, "height": 1}, "page_num": 1, "font_size": 14, "label": "heading"},
        {"text": "Introductory paragraph.", "bbox": {"left": 0, "top": 0, "width": 1, "height": 1}, "page_num": 1, "font_size": 12, "label": "para"},
    ]

    def fake_provider(_pdf_path: Path, _example_id: str):
        return pdf_blocks

    dataset = build_dataset(root, config_dir=Path("config"), pdf_block_provider=fake_provider)
    assert len(dataset) == len(pdf_blocks)
    assert {example.dct_label for example in dataset} >= {"para", "chapter.title"}

    out_path = tmp_path / "dataset.jsonl"
    save_dataset_jsonl(dataset, out_path)
    saved = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(saved) == len(pdf_blocks)
    summary = summarise_dataset(dataset)
    assert summary["total_examples"] == len(pdf_blocks)
    assert "label_distribution" in summary
