from textwrap import dedent

from pipeline.structure.heuristics import (
    Line,
    TextSegment,
    _collect_multiline_book_title,
    label_blocks,
)


def _make_line(
    text: str,
    *,
    page: int = 1,
    top: float = 100.0,
    left: float = 100.0,
    width: float = 200.0,
    height: float = 20.0,
    font_size: float = 24.0,
) -> Line:
    segment = TextSegment(text=text, left=left, width=width, font_size=font_size)
    return Line(
        page_num=page,
        page_width=600.0,
        page_height=800.0,
        top=top,
        left=left,
        height=height,
        font_size=font_size,
        text=text,
        segments=[segment],
    )


def test_collect_multiline_book_title_stops_before_table_of_contents():
    title_line = _make_line("Great Adventures", top=120.0)
    subtitle_line = _make_line("A Journey", top=145.0, font_size=23.5)
    toc_line = _make_line("Table of Contents", page=2, top=100.0)

    entries = [
        {"kind": "line", "line": title_line},
        {"kind": "line", "line": subtitle_line},
        {"kind": "line", "line": toc_line},
    ]

    collected, next_idx = _collect_multiline_book_title(entries, 0, body_size=12.0)

    assert [line.text for line in collected] == ["Great Adventures", "A Journey"]
    assert next_idx == 2


def test_collect_multiline_book_title_requires_similar_font():
    title_line = _make_line("Science 101", top=100.0)
    body_line = _make_line("Introduction", top=140.0, font_size=14.0)

    entries = [
        {"kind": "line", "line": title_line},
        {"kind": "line", "line": body_line},
    ]

    collected, next_idx = _collect_multiline_book_title(entries, 0, body_size=12.0)

    assert [line.text for line in collected] == ["Science 101"]
    assert next_idx == 1


def test_label_blocks_groups_index_section(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="12" family="Body" />
          <page number="3" width="600" height="800">
            <text top="60" left="100" width="240" height="35" font="f1">Sample Book</text>
            <text top="110" left="110" width="300" height="20" font="f2">An engaging introduction to testing heuristics.</text>
          </page>
          <page number="2" width="600" height="800">
            <text top="100" left="100" width="220" height="30" font="f1">Chapter 1</text>
            <text top="140" left="110" width="320" height="20" font="f2">This is some body text used to estimate the base font size.</text>
          </page>
          <page number="3" width="600" height="800">
            <text top="100" left="100" width="200" height="30" font="f1">Index</text>
            <text top="140" left="110" width="200" height="20" font="f2">Apple ........ 10</text>
            <text top="170" left="110" width="200" height="25" font="f1">A</text>
            <text top="200" left="110" width="200" height="20" font="f2">Ant ........ 12</text>
          </page>
          <page number="4" width="600" height="800">
            <text top="100" left="100" width="220" height="30" font="f1">Chapter 7</text>
            <text top="140" left="110" width="200" height="20" font="f2">Next section text</text>
          </page>
        </pdf2xml>
        """
    ).strip()
    pdf_path = tmp_path / "sample.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    assert any(
        block["label"] == "chapter"
        and block["text"].strip().lower() == "index"
        and block.get("chapter_role") == "index"
        for block in blocks
    )

    assert any(block["label"] == "para" and block["text"].strip() == "A" for block in blocks)

    assert any(block["label"] == "chapter" and block["text"].startswith("Chapter 7") for block in blocks)


def test_chapter_keyword_controls_split(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="12" family="Body" />
          <page number="3" width="600" height="800">
            <text top="80" left="100" width="240" height="30" font="f1">Chapter 1</text>
            <text top="180" left="110" width="320" height="20" font="f2">Body text after heading that provides sufficient length for detection.</text>
            <text top="210" left="110" width="320" height="20" font="f2">Additional paragraph content to stabilise the body font size estimate.</text>
            <text top="300" left="100" width="260" height="30" font="f1">Learning Objectives</text>
          </page>
        </pdf2xml>
        """
    ).strip()

    pdf_path = tmp_path / "chapter.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    chapter_blocks = [block for block in blocks if block["label"] == "chapter"]
    assert len(chapter_blocks) == 1
    assert chapter_blocks[0]["text"].strip() == "Chapter 1"

    assert any(block["label"] == "section" and block["text"].strip() == "Learning Objectives" for block in blocks)


def test_chapter_keyword_detected_anywhere(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="12" family="Body" />
          <page number="3" width="600" height="800">
            <text top="80" left="100" width="300" height="30" font="f1">Unit Overview - Chapter 1</text>
            <text top="130" left="110" width="320" height="20" font="f2">Body text to establish base font size.</text>
            <text top="220" left="110" width="320" height="20" font="f2">More supporting content beneath the heading.</text>
            <text top="300" left="100" width="260" height="30" font="f1">Glossary</text>
          </page>
        </pdf2xml>
        """
    ).strip()

    pdf_path = tmp_path / "chapter_anywhere.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    chapter_blocks = [block for block in blocks if block["label"] == "chapter"]
    assert len(chapter_blocks) == 1
    assert chapter_blocks[0]["text"].strip().startswith("Unit Overview - Chapter 1")
    assert any(
        block["label"] == "section" and block["text"].strip() == "Glossary"
        for block in blocks
    )


def test_chapter_boundaries_follow_table_of_contents(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="12" family="Body" />
          <page number="1" width="600" height="800">
            <text top="80" left="100" width="240" height="30" font="f1">Table of Contents</text>
            <text top="140" left="120" width="320" height="20" font="f2">Chapter 1 Basics ........ 5</text>
            <text top="170" left="120" width="320" height="20" font="f2">Chapter 2 Advanced ........ 9</text>
          </page>
          <page number="2" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Chapter 1 Basics</text>
            <text top="140" left="110" width="320" height="20" font="f2">Body text for chapter one.</text>
          </page>
          <page number="3" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Chapter 2 Advanced</text>
            <text top="140" left="110" width="320" height="20" font="f2">Body text for chapter two.</text>
          </page>
          <page number="4" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Appendix A</text>
            <text top="140" left="110" width="320" height="20" font="f2">Supplemental material.</text>
          </page>
        </pdf2xml>
        """
    ).strip()

    pdf_path = tmp_path / "toc.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    chapter_titles = [block["text"].strip() for block in blocks if block["label"] == "chapter"]
    assert chapter_titles == ["Chapter 1 Basics", "Chapter 2 Advanced"]
    assert all("Appendix" not in title for title in chapter_titles)


def test_chapter_boundaries_ignore_nested_toc_entries(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="24" family="Heading" />
          <fontspec id="f3" size="12" family="Body" />
          <page number="1" width="600" height="800">
            <text top="80" left="100" width="240" height="30" font="f1">Table of Contents</text>
            <text top="140" left="120" width="320" height="20" font="f3">Chapter 1 Basics ........ 5</text>
            <text top="170" left="150" width="320" height="20" font="f3">Section 1.1 Overview ........ 6</text>
            <text top="200" left="120" width="320" height="20" font="f3">Chapter 2 Advanced ........ 10</text>
          </page>
          <page number="2" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Chapter 1 Basics</text>
            <text top="140" left="110" width="320" height="20" font="f3">Body text for chapter one.</text>
            <text top="220" left="100" width="240" height="28" font="f2">Section 1.1 Overview</text>
            <text top="260" left="110" width="320" height="20" font="f3">Section body text.</text>
          </page>
          <page number="3" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Chapter 2 Advanced</text>
            <text top="140" left="110" width="320" height="20" font="f3">Body text for chapter two.</text>
          </page>
        </pdf2xml>
        """
    ).strip()

    pdf_path = tmp_path / "toc_nested.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    chapter_titles = [block["text"].strip() for block in blocks if block["label"] == "chapter"]
    assert chapter_titles == ["Chapter 1 Basics", "Chapter 2 Advanced"]
    assert all("Section 1.1" not in title for title in chapter_titles)


def test_chapter_boundaries_follow_bookmarks(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="12" family="Body" />
          <outline>
            <item title="Preface" />
            <item title="Chapter 1" />
          </outline>
          <page number="1" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Preface</text>
            <text top="140" left="110" width="320" height="20" font="f2">Opening remarks.</text>
          </page>
          <page number="2" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Chapter 1</text>
            <text top="140" left="110" width="320" height="20" font="f2">Body text chapter one.</text>
          </page>
          <page number="3" width="600" height="800">
            <text top="90" left="100" width="240" height="30" font="f1">Chapter 2</text>
            <text top="140" left="110" width="320" height="20" font="f2">Additional chapter not bookmarked.</text>
          </page>
        </pdf2xml>
        """
    ).strip()

    pdf_path = tmp_path / "bookmarks.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    chapter_titles = [block["text"].strip() for block in blocks if block["label"] == "chapter"]
    assert chapter_titles == ["Preface", "Chapter 1"]
    assert all(title != "Chapter 2" for title in chapter_titles)


def test_chapter_fallback_without_keyword(tmp_path):
    pdf_xml = dedent(
        """
        <pdf2xml>
          <fontspec id="f1" size="28" family="Heading" />
          <fontspec id="f2" size="12" family="Body" />
          <page number="3" width="600" height="800">
            <text top="80" left="100" width="240" height="30" font="f1">Introduction</text>
            <text top="130" left="110" width="320" height="20" font="f2">Body text establishing base font size.</text>
          </page>
          <page number="4" width="600" height="800">
            <text top="80" left="100" width="240" height="30" font="f1">Background</text>
            <text top="130" left="110" width="320" height="20" font="f2">More body text content.</text>
          </page>
        </pdf2xml>
        """
    ).strip()

    pdf_path = tmp_path / "chapter_fallback.xml"
    pdf_path.write_text(pdf_xml, encoding="utf-8")

    blocks = label_blocks(str(pdf_path), mapping={})

    chapter_blocks = [block for block in blocks if block["label"] == "chapter"]
    assert [block["text"].strip() for block in chapter_blocks] == [
        "Introduction",
        "Background",
    ]
