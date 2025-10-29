from lxml import etree

from pipeline.structure.docbook import build_docbook_tree


def _block(label, text, page_num=1, left=100.0, top=100.0, width=200.0, height=20.0, font_size=24.0, **extra):
    block = {
        "label": label,
        "text": text,
        "page_num": page_num,
        "bbox": {"top": top, "left": left, "width": width, "height": height},
        "font_size": font_size,
    }
    block.update(extra)
    return block


def test_build_docbook_tree_creates_structured_index():
    blocks = [
        _block("chapter", "Index", font_size=30.0, chapter_role="index"),
        _block("para", "A", left=100.0),
        _block("para", "AI-Driven Diagnostics ........ 10, 12", left=105.0),
        _block("para", "Analytics, see Data Science", left=105.0),
        _block("para", "Blockchain ........ 20, 21", left=105.0),
        _block("para", "Blockchain technology ........ 22", left=130.0),
        _block("chapter", "Appendix A", page_num=2, left=90.0, font_size=30.0),
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
