from pipeline.structure.heuristics import (
    Line,
    TextSegment,
    _collect_multiline_book_title,
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
