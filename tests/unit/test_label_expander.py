from pipeline.structure.label_expander import LabelExpander


def test_label_expander_assigns_containers():
    blocks = [
        {
            "label": "book_title",
            "text": "Example Book",
            "font_size": 32.0,
        },
        {
            "label": "chapter",
            "text": "Chapter 1",
            "font_size": 28.0,
        },
        {
            "label": "section",
            "text": "Introduction",
            "font_size": 24.0,
        },
        {
            "label": "para",
            "text": "This is the opening paragraph.",
            "font_size": 12.0,
        },
    ]

    expanded = LabelExpander().expand(blocks)

    assert expanded[0]["rittdoc_label"] == "book.title"
    assert expanded[1]["rittdoc_label"] == "chapter.title"
    assert expanded[2]["rittdoc_label"] == "sect1.title"
    assert expanded[3]["rittdoc_label"] == "sect1.para"


def test_label_expander_detects_lists():
    blocks = [
        {
            "label": "chapter",
            "text": "Chapter 1",
            "font_size": 28.0,
        },
        {
            "label": "para",
            "text": "Intro paragraph",
            "font_size": 12.0,
        },
        {
            "label": "list_item",
            "text": "First item",
            "list_type": "itemized",
            "font_size": 12.0,
        },
        {
            "label": "list_item",
            "text": "Second item",
            "list_type": "ordered",
            "font_size": 12.0,
        },
    ]

    expanded = LabelExpander().expand(blocks)

    assert expanded[2]["rittdoc_label"] == "chapter.itemizedlist.item"
    assert expanded[3]["rittdoc_label"] == "chapter.orderedlist.item"
