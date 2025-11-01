from lxml import etree

from pipeline.structure.docbook import build_docbook_tree


def _block(
    label,
    text,
    page_num=1,
    left=100.0,
    top=100.0,
    width=200.0,
    height=20.0,
    font_size=24.0,
    rittdoc_label=None,
    rittdoc_container=None,
    rittdoc_type=None,
    rittdoc_starts_container=False,
    **extra,
):
    block = {
        "label": label,
        "text": text,
        "page_num": page_num,
        "bbox": {"top": top, "left": left, "width": width, "height": height},
        "font_size": font_size,
    }
    if rittdoc_label is not None:
        block["rittdoc_label"] = rittdoc_label
    if rittdoc_container is not None:
        block["rittdoc_container"] = rittdoc_container
    if rittdoc_type is not None:
        block["rittdoc_type"] = rittdoc_type
    if rittdoc_starts_container:
        block["rittdoc_starts_container"] = True
    block.update(extra)
    return block


def test_build_docbook_tree_creates_structured_index():
    blocks = [
        _block(
            "chapter",
            "Index",
            font_size=30.0,
            rittdoc_label="index.title",
            rittdoc_container="index",
            rittdoc_type="title",
            rittdoc_starts_container=True,
        ),
        _block(
            "para",
            "A",
            left=100.0,
            rittdoc_label="index.entry",
            rittdoc_container="index",
            rittdoc_type="entry",
        ),
        _block(
            "para",
            "AI-Driven Diagnostics ........ 10, 12",
            left=105.0,
            rittdoc_label="index.entry",
            rittdoc_container="index",
            rittdoc_type="entry",
        ),
        _block(
            "para",
            "Analytics, see Data Science",
            left=105.0,
            rittdoc_label="index.entry",
            rittdoc_container="index",
            rittdoc_type="entry",
        ),
        _block(
            "para",
            "Blockchain ........ 20, 21",
            left=105.0,
            rittdoc_label="index.entry",
            rittdoc_container="index",
            rittdoc_type="entry",
        ),
        _block(
            "para",
            "Blockchain technology ........ 22",
            left=130.0,
            rittdoc_label="index.entry",
            rittdoc_container="index",
            rittdoc_type="entry",
        ),
        _block(
            "chapter",
            "Appendix A",
            page_num=2,
            left=90.0,
            font_size=30.0,
            rittdoc_label="chapter.title",
            rittdoc_container="chapter",
            rittdoc_type="title",
            rittdoc_starts_container=True,
        ),
    ]

    doc = build_docbook_tree(blocks, "book")

    index_nodes = doc.findall("index")
    assert len(index_nodes) == 1

    index = index_nodes[0]
    assert index.findtext("title") == "Index"

    index_divs = index.findall("indexdiv")
    assert any(div.findtext("title") == "A" for div in index_divs)

    ai_entry = index.xpath(".//indexentry[primaryie='AI-Driven Diagnostics']")
    assert ai_entry, "Expected AI-Driven Diagnostics entry"
    assert ai_entry[0].findtext("seeie") == "10, 12"

    analytics_entry = index.xpath(".//indexentry[primaryie='Analytics']")
    assert analytics_entry, "Expected Analytics entry"
    assert analytics_entry[0].findtext("seealsoie") == "see Data Science"

    blockchain_entry = index.xpath(".//indexentry[primaryie='Blockchain']")
    assert blockchain_entry, "Expected Blockchain entry"
    secondary = blockchain_entry[0].find("secondaryie")
    assert secondary is not None
    assert secondary.findtext("secondaryie") == "Blockchain technology"
    assert secondary.findtext("seeie") == "22"

    chapters = doc.findall("chapter")
    assert any(ch.findtext("title") == "Appendix A" for ch in chapters)


def test_caption_preceding_figure_is_attached():
    blocks = [
        _block(
            "chapter",
            "Chapter 1",
            font_size=28.0,
            rittdoc_label="chapter.title",
            rittdoc_container="chapter",
            rittdoc_type="title",
            rittdoc_starts_container=True,
        ),
        _block(
            "caption",
            "Figure 1.1 Diagram of the process",
            rittdoc_label="chapter.figure.caption",
            rittdoc_container="chapter",
            rittdoc_type="figure.caption",
        ),
        {
            **_block(
                "figure",
                "",
                src="images/figure.png",
                rittdoc_label="chapter.figure",
                rittdoc_container="chapter",
                rittdoc_type="figure",
            ),
        },
    ]

    doc = build_docbook_tree(blocks, "book")

    chapter = doc.find("chapter")
    assert chapter is not None
    figure = chapter.find("figure")
    assert figure is not None
    caption = figure.find("caption")
    assert caption is not None
    assert caption.text == "Figure 1.1 Diagram of the process"


def test_orphan_caption_falls_back_to_paragraph():
    blocks = [
        _block(
            "chapter",
            "Chapter 1",
            font_size=28.0,
            rittdoc_label="chapter.title",
            rittdoc_container="chapter",
            rittdoc_type="title",
            rittdoc_starts_container=True,
        ),
        _block(
            "caption",
            "Figure 1.2 Unused caption",
            rittdoc_label="chapter.figure.caption",
            rittdoc_container="chapter",
            rittdoc_type="figure.caption",
        ),
        _block(
            "para",
            "Following paragraph",
            rittdoc_label="chapter.para",
            rittdoc_container="chapter",
            rittdoc_type="para",
        ),
    ]

    doc = build_docbook_tree(blocks, "book")

    chapter = doc.find("chapter")
    assert chapter is not None
    paras = chapter.findall("para")
    texts = [para.text for para in paras]
    assert "Figure 1.2 Unused caption" in texts
    assert "Following paragraph" in texts
