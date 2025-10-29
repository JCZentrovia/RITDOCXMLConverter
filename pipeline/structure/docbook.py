from __future__ import annotations

from typing import List, Optional

from lxml import etree


def _ensure_title(parent: etree._Element, text: str) -> etree._Element:
    title = parent.find("title")
    if title is None:
        title = etree.SubElement(parent, "title")
    title.text = text.strip()
    return title


def _append_para(parent: etree._Element, text: str) -> etree._Element:
    para = etree.SubElement(parent, "para")
    para.text = text.strip()
    return para


def _close_list(state: dict) -> None:
    state["current_list"] = None
    state["current_list_type"] = None


def _current_container(root: etree._Element, state: dict) -> etree._Element:
    if state.get("current_section") is not None:
        return state["current_section"]
    if state.get("current_chapter") is not None:
        return state["current_chapter"]
    return root


def _attach_caption(target: Optional[etree._Element], text: str) -> bool:
    if target is None:
        return False
    if target.tag not in {"figure", "informaltable", "table"}:
        return False
    caption = target.find("caption")
    if caption is None:
        caption = etree.SubElement(target, "caption")
    caption.text = text.strip()
    return True


def build_docbook_tree(blocks: List[dict], root_name: str) -> etree._Element:
    root = etree.Element(root_name)
    state = {
        "current_chapter": None,
        "current_section": None,
        "current_list": None,
        "current_list_type": None,
        "last_structure": None,
    }

    for block in blocks:
        label = block.get("classifier_label") or block.get("label", "para")
        text = (block.get("text") or "").strip()

        if label == "book_title" and text:
            _ensure_title(root, text)
            _close_list(state)
            state["last_structure"] = root
            continue

        if label == "toc" and text:
            chapter = etree.SubElement(root, "chapter")
            chapter.set("role", "toc")
            _ensure_title(chapter, text)
            state["current_chapter"] = chapter
            state["current_section"] = None
            _close_list(state)
            state["last_structure"] = chapter
            continue

        if label == "chapter" and text:
            chapter = etree.SubElement(root, "chapter")
            _ensure_title(chapter, text)
            state["current_chapter"] = chapter
            state["current_section"] = None
            _close_list(state)
            state["last_structure"] = chapter
            continue

        if label == "section" and text:
            container = state.get("current_chapter") or root
            section = etree.SubElement(container, "sect1")
            _ensure_title(section, text)
            state["current_section"] = section
            _close_list(state)
            state["last_structure"] = section
            continue

        if label == "list_item" and text:
            container = _current_container(root, state)
            list_type = block.get("list_type") or "itemized"
            tag = "orderedlist" if list_type == "ordered" else "itemizedlist"
            if state["current_list"] is None or state["current_list"].tag != tag:
                state["current_list"] = etree.SubElement(container, tag)
                state["current_list_type"] = tag
            listitem = etree.SubElement(state["current_list"], "listitem")
            _append_para(listitem, text)
            state["last_structure"] = state["current_list"]
            continue

        if label == "figure" and block.get("src"):
            container = _current_container(root, state)
            figure = etree.SubElement(container, "figure")
            mediaobject = etree.SubElement(figure, "mediaobject")
            imageobject = etree.SubElement(mediaobject, "imageobject")
            etree.SubElement(imageobject, "imagedata", fileref=block["src"])
            state["last_structure"] = figure
            _close_list(state)
            continue

        if label == "table" and block.get("rows"):
            container = _current_container(root, state)
            rows = block["rows"]
            cols = len(rows[0]) if rows else 0
            table = etree.SubElement(container, "informaltable")
            tgroup = etree.SubElement(table, "tgroup", cols=str(cols))
            tbody = etree.SubElement(tgroup, "tbody")
            for row in rows:
                row_el = etree.SubElement(tbody, "row")
                for cell in row:
                    entry = etree.SubElement(row_el, "entry")
                    entry.text = (cell or "").strip()
            state["last_structure"] = table
            _close_list(state)
            continue

        if label == "caption" and text:
            if _attach_caption(state.get("last_structure"), text):
                continue
            # Fallback to paragraph when we cannot attach the caption.
            label = "para"

        if label == "para" and text:
            container = _current_container(root, state)
            _append_para(container, text)
            state["last_structure"] = container
            _close_list(state)
            continue

        if label == "footnote" and text:
            container = _current_container(root, state)
            footnote = etree.SubElement(container, "footnote")
            _append_para(footnote, text)
            state["last_structure"] = footnote
            _close_list(state)
            continue

        # Any unrecognised label with text should still result in a paragraph.
        if text:
            container = _current_container(root, state)
            _append_para(container, text)
            state["last_structure"] = container
            _close_list(state)

    return root
