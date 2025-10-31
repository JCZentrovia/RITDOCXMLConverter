from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Sequence

from lxml import etree

# Set up logging so we can see what's happening
logger = logging.getLogger(__name__)


def _ensure_title(parent: etree._Element, text: str) -> etree._Element:
    title = parent.find("title")
    if title is None:
        title = etree.SubElement(parent, "title")
    title.text = text.strip()
    return title


def _append_text_fragment(parent: etree._Element, fragment: str) -> None:
    if not fragment:
        return
    fragment = str(fragment)
    if len(parent):
        last = parent[-1]
        last.tail = (last.tail or "") + fragment
    else:
        if parent.text:
            parent.text += fragment
        else:
            parent.text = fragment


def _create_personname_element(text: str, details: Dict[str, object], label: str) -> etree._Element:
    element = etree.Element("personname")
    element.set("role", f"ner-{label}")

    prefix = details.get("prefix")
    if prefix:
        prefix_el = etree.SubElement(element, "othername")
        prefix_el.set("role", "prefix")
        prefix_el.text = str(prefix)

    first = details.get("first")
    if first:
        etree.SubElement(element, "firstname").text = str(first)

    for middle in details.get("middle", []) or []:
        middle_el = etree.SubElement(element, "othername")
        middle_el.set("role", "middle")
        middle_el.text = str(middle)

    last = details.get("last")
    if last:
        etree.SubElement(element, "surname").text = str(last)

    suffix = details.get("suffix")
    if suffix:
        suffix_el = etree.SubElement(element, "othername")
        suffix_el.set("role", "suffix")
        suffix_el.text = str(suffix)

    if not len(element):
        element.text = text

    return element


def _create_entity_element(entity: Dict[str, object]) -> etree._Element:
    label = str(entity.get("label") or entity.get("type") or "entity").lower()
    text = str(entity.get("text") or "")
    if label == "person":
        details = entity.get("person") or {}
        element = _create_personname_element(text, details, label)
    else:
        element = etree.Element("phrase")
        element.set("role", f"ner-{label}")
        element.text = text

    original = entity.get("original_label")
    if original and element.get("role") is not None:
        element.set("orig-label", str(original))
    score = entity.get("score")
    if score is not None:
        element.set("confidence", f"{float(score):.3f}")
    return element


def _append_entities(parent: etree._Element, text: str, entities: Sequence[Dict[str, object]]) -> None:
    if not entities:
        parent.text = text
        return

    cursor = 0
    text_length = len(text)
    for entity in sorted(entities, key=lambda item: int(item.get("start", 0))):
        start = int(entity.get("start", 0) or 0)
        end = int(entity.get("end", start) or start)
        start = max(0, min(text_length, start))
        end = max(start, min(text_length, end))
        if start < cursor or start == end:
            continue

        _append_text_fragment(parent, text[cursor:start])
        segment = text[start:end]
        if not segment:
            cursor = end
            continue

        leading_ws = len(segment) - len(segment.lstrip())
        trailing_ws = len(segment) - len(segment.rstrip())
        if leading_ws:
            _append_text_fragment(parent, segment[:leading_ws])

        core = segment[leading_ws: len(segment) - trailing_ws if trailing_ws else len(segment)]
        if core:
            entity_copy = dict(entity)
            entity_copy.setdefault("text", core)
            parent.append(_create_entity_element(entity_copy))

        if trailing_ws:
            _append_text_fragment(parent, segment[-trailing_ws:])

        cursor = end

    if cursor < text_length:
        _append_text_fragment(parent, text[cursor:])

    if not len(parent) and not parent.text:
        parent.text = text


def _append_para(parent: etree._Element, text: str, entities: Optional[Sequence[Dict[str, object]]] = None) -> etree._Element:
    para = etree.SubElement(parent, "para")
    clean_text = text.strip()
    if entities:
        _append_entities(para, clean_text, entities)
    else:
        para.text = clean_text
    return para


def _close_list(state: dict) -> None:
    state["current_list"] = None
    state["current_list_type"] = None


def _queue_pending_caption(state: dict, text: str) -> None:
    text = text.strip()
    if not text:
        return
    pending = state.get("pending_caption")
    if pending:
        state["pending_caption"] = f"{pending} {text}"
    else:
        state["pending_caption"] = text


def _attach_pending_caption(root: etree._Element, state: dict, target: Optional[etree._Element]) -> None:
    pending = state.get("pending_caption")
    if not pending:
        return
    if target is not None and _attach_caption(target, pending):
        state["pending_caption"] = None
        return
    container = _current_container(root, state)
    if container is not None:
        _append_para(container, pending)
        state["last_structure"] = container
    state["pending_caption"] = None
    _close_list(state)


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
    """
    Build a DocBook XML tree from a list of labeled blocks.
    
    Each block should have:
    - 'label' or 'classifier_label': what type of content it is (chapter, para, etc.)
    - 'text': the actual text content
    - other fields depending on the block type
    """
    logger.info("=" * 70)
    logger.info("🏗️  BUILDING DOCBOOK TREE")
    logger.info("=" * 70)
    logger.info(f"Total blocks to process: {len(blocks)}")
    
    # Count blocks by label to see what we're working with
    label_counts = {}
    blocks_with_text_count = 0
    total_text_chars = 0
    
    for block in blocks:
        label = block.get("classifier_label") or block.get("label", "para")
        text = block.get("text", "")
        
        label_counts[label] = label_counts.get(label, 0) + 1
        if text and text.strip():
            blocks_with_text_count += 1
            total_text_chars += len(text)
    
    logger.info(f"Blocks with text content: {blocks_with_text_count}/{len(blocks)}")
    logger.info(f"Total characters in all blocks: {total_text_chars:,}")
    logger.info(f"Block types: {label_counts}")
    logger.info("=" * 70)
    
    root = etree.Element(root_name)
    state = {
        "current_chapter": None,
        "current_section": None,
        "current_list": None,
        "current_list_type": None,
        "last_structure": None,
        "current_index": None,
        "index_state": None,
        "pending_caption": None,
    }

    for block in blocks:
        label = block.get("classifier_label") or block.get("label", "para")
        text = (block.get("text") or "").strip()
        entities = block.get("entities") if isinstance(block, dict) else None

        if state.get("pending_caption") and label not in {"caption", "figure", "table"}:
            _attach_pending_caption(root, state, None)

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
            _append_para(listitem, text, entities)
            state["last_structure"] = state["current_list"]
            continue

        if label == "figure" and block.get("src"):
            container = _current_container(root, state)
            figure = etree.SubElement(container, "figure")
            mediaobject = etree.SubElement(figure, "mediaobject")
            imageobject = etree.SubElement(mediaobject, "imageobject")
            etree.SubElement(imageobject, "imagedata", fileref=block["src"])
            _attach_pending_caption(root, state, figure)
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
            _attach_pending_caption(root, state, table)
            state["last_structure"] = table
            _close_list(state)
            continue

        if label == "caption" and text:
            if _attach_caption(state.get("last_structure"), text):
                state["pending_caption"] = None
                continue
            _queue_pending_caption(state, text)
            continue

        if label == "para" and text:
            container = _current_container(root, state)
            para = _append_para(container, text, entities)
            
            # Log every 10th paragraph to track progress
            if not hasattr(build_docbook_tree, '_para_count'):
                build_docbook_tree._para_count = 0
            build_docbook_tree._para_count += 1
            
            if build_docbook_tree._para_count % 10 == 0:
                logger.debug(f"Added paragraph #{build_docbook_tree._para_count}: {text[:50]}...")
            
            state["last_structure"] = container
            _close_list(state)
            continue

        if label == "footnote" and text:
            container = _current_container(root, state)
            footnote = etree.SubElement(container, "footnote")
            _append_para(footnote, text, entities)
            state["last_structure"] = footnote
            _close_list(state)
            continue

        # Any unrecognised label with text should still result in a paragraph.
        if text:
            container = _current_container(root, state)
            _append_para(container, text, entities)
            state["last_structure"] = container
            _close_list(state)

    if state.get("pending_caption"):
        _attach_pending_caption(root, state, None)
    
    # Final summary of what was built
    logger.info("=" * 70)
    logger.info("✅ DOCBOOK TREE BUILT")
    logger.info("=" * 70)
    
    # Count what was created in the tree
    para_count = len(root.findall(".//para"))
    chapter_count = len(root.findall(".//chapter"))
    section_count = len(root.findall(".//sect1"))
    
    logger.info(f"Chapters created: {chapter_count}")
    logger.info(f"Sections created: {section_count}")
    logger.info(f"Paragraphs created: {para_count}")
    
    if para_count == 0:
        logger.warning("⚠️  WARNING: NO PARAGRAPHS were created!")
        logger.warning("   This means no 'para' labeled blocks with text were processed")
        logger.warning("   Check if blocks have the right labels and text content")
    
    logger.info("=" * 70)

    return root