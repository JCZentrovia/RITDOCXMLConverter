from __future__ import annotations

import re
from typing import Dict, List, Optional

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
    if state.get("current_index") is not None:
        return state["current_index"]
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


_INDEX_LETTER_RE = re.compile(r"^[A-Z]$")
_INDEX_REF_RE = re.compile(r",\s*(see(?:\s+also)?)\s+(.*)$", re.IGNORECASE)
_INDEX_PAGE_RE = re.compile(r"(\d[\dA-Za-z\s,–-]*)$")
_INDEX_DOTS_RE = re.compile(r"\.{2,}")


def _initialise_index_state() -> Dict:
    return {
        "current_div": None,
        "current_entry": None,
        "base_left": None,
    }


def _start_index(root: etree._Element, text: str) -> etree._Element:
    index = etree.SubElement(root, "index")
    _ensure_title(index, text)
    return index


def _normalise_index_text(text: str) -> str:
    cleaned = _INDEX_DOTS_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_index_reference(text: str) -> tuple[str, Optional[str]]:
    match = _INDEX_REF_RE.search(text)
    if not match:
        return text, None
    prefix = match.group(1)
    target = match.group(2).strip()
    remainder = text[: match.start()].rstrip(", ")
    reference_text = f"{prefix} {target}".strip()
    return remainder, reference_text


def _extract_index_pages(text: str) -> tuple[str, Optional[str]]:
    match = _INDEX_PAGE_RE.search(text)
    if not match:
        return text, None
    pages = match.group(1).strip()
    if not any(char.isdigit() for char in pages):
        return text, None
    remainder = text[: match.start()].rstrip(",;: ")
    return remainder, pages


def _handle_index_para(block: dict, state: dict) -> bool:
    index = state.get("current_index")
    if index is None:
        return False

    text = (block.get("text") or "").strip()
    if not text:
        return True

    normalised = _normalise_index_text(text)
    if not normalised:
        return True

    index_state = state.setdefault("index_state", _initialise_index_state())

    bbox = block.get("bbox") or {}
    left = None
    if isinstance(bbox, dict):
        left = bbox.get("left")
    if index_state.get("base_left") is None and left is not None:
        index_state["base_left"] = float(left)

    if _INDEX_LETTER_RE.match(normalised):
        div = etree.SubElement(index, "indexdiv")
        _ensure_title(div, normalised)
        index_state["current_div"] = div
        index_state["current_entry"] = None
        index_state["base_left"] = float(left) if left is not None else index_state.get("base_left")
        state["last_structure"] = div
        _close_list(state)
        return True

    if index_state.get("current_div") is None:
        initial = normalised[0].upper() if normalised else "#"
        div = etree.SubElement(index, "indexdiv")
        _ensure_title(div, initial)
        index_state["current_div"] = div
        if left is not None:
            index_state["base_left"] = float(left)

    base_left = index_state.get("base_left") or 0.0
    indent = 0.0
    if left is not None:
        indent = max(0.0, float(left) - base_left)

    working_text, reference_text = _extract_index_reference(normalised)
    working_text, pages_text = _extract_index_pages(working_text)
    entry_text = working_text.strip(", ")

    if not entry_text:
        # If no entry text remains, attach page numbers/reference to current entry.
        current_entry = index_state.get("current_entry")
        if current_entry is not None:
            if pages_text:
                etree.SubElement(current_entry, "seeie").text = pages_text
            if reference_text:
                etree.SubElement(current_entry, "seealsoie").text = reference_text
        return True

    div = index_state.get("current_div")
    if div is None:
        div = etree.SubElement(index, "indexdiv")
        _ensure_title(div, entry_text[0].upper() if entry_text else "#")
        index_state["current_div"] = div

    indent_threshold = 18.0
    if indent <= indent_threshold or index_state.get("current_entry") is None:
        entry = etree.SubElement(div, "indexentry")
        primary = etree.SubElement(entry, "primaryie")
        primary.text = entry_text
        if pages_text:
            etree.SubElement(entry, "seeie").text = pages_text
        if reference_text:
            etree.SubElement(entry, "seealsoie").text = reference_text
        index_state["current_entry"] = entry
        _close_list(state)
        return True

    parent_entry = index_state.get("current_entry")
    secondary_container = etree.SubElement(parent_entry, "secondaryie")
    secondary_term = etree.SubElement(secondary_container, "secondaryie")
    secondary_term.text = entry_text
    if pages_text:
        etree.SubElement(secondary_container, "seeie").text = pages_text
    if reference_text:
        etree.SubElement(secondary_container, "seealsoie").text = reference_text
    _close_list(state)
    return True


def build_docbook_tree(blocks: List[dict], root_name: str) -> etree._Element:
    root = etree.Element(root_name)
    state = {
        "current_chapter": None,
        "current_section": None,
        "current_list": None,
        "current_list_type": None,
        "last_structure": None,
        "current_index": None,
        "index_state": None,
    }

    for block in blocks:
        label = block.get("classifier_label") or block.get("label", "para")
        text = (block.get("text") or "").strip()

        if state.get("current_index") is not None and label == "para":
            if _handle_index_para(block, state):
                state["last_structure"] = state.get("current_index")
                continue

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
            role = block.get("chapter_role")
            if role == "index":
                state["current_index"] = _start_index(root, text)
                state["index_state"] = _initialise_index_state()
                state["current_chapter"] = None
                state["current_section"] = None
                _close_list(state)
                state["last_structure"] = state["current_index"]
                continue

            state["current_index"] = None
            state["index_state"] = None
            chapter = etree.SubElement(root, "chapter")
            if role:
                chapter.set("role", role)
            _ensure_title(chapter, text)
            state["current_chapter"] = chapter
            state["current_section"] = None
            _close_list(state)
            state["last_structure"] = chapter
            continue

        if label == "section" and text:
            if state.get("current_index") is not None:
                if _handle_index_para(block, state):
                    state["last_structure"] = state.get("current_index")
                    continue
            container = state.get("current_chapter")
            if container is None:
                container = root
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
