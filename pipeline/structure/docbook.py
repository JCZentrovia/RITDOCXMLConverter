from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from lxml import etree

# Set up logging so we can see what's happening
logger = logging.getLogger(__name__)

from .label_taxonomy import LabelDefinition, LabelTaxonomy, load_label_taxonomy


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


@dataclass
class ActiveContainer:
    name: str
    level: int
    element: etree._Element


class ContainerManager:
    """Manage the hierarchy of DocBook containers."""

    def __init__(self, root: etree._Element, taxonomy: LabelTaxonomy) -> None:
        self._taxonomy = taxonomy
        book_def = taxonomy.get_container("book")
        level = book_def.level if book_def else 0
        self._root_state = ActiveContainer("book", level, root)
        self._stack: List[ActiveContainer] = [self._root_state]
        self._registry: Dict[str, List[ActiveContainer]] = {"book": [self._root_state]}

    def ensure(self, name: str, starts_container: bool) -> etree._Element:
        definition = self._taxonomy.get_container(name)
        if not definition:
            return self._stack[-1].element

        if definition.singleton and name in self._registry:
            state = self._registry[name][0]
            self._align_stack(state)
            return state.element

        parent_name = definition.parent or self._root_state.name
        if parent_name != name:
            parent_element = self.ensure(parent_name, False)
        else:
            parent_element = self._root_state.element

        if starts_container:
            while self._stack and self._stack[-1].level >= definition.level:
                self._stack.pop()
        else:
            for state in reversed(self._stack):
                if state.name == name:
                    return state.element
            while self._stack and self._stack[-1].level > definition.level:
                self._stack.pop()

        if self._stack and self._stack[-1].name == name:
            return self._stack[-1].element

        element = etree.SubElement(parent_element, definition.element)
        state = ActiveContainer(name, definition.level, element)
        self._registry.setdefault(name, []).append(state)
        self._stack.append(state)
        return element

    def _align_stack(self, target: ActiveContainer) -> None:
        if target in self._stack:
            while self._stack[-1] != target:
                self._stack.pop()
            return
        # Reset to root and push target
        self._stack = [self._root_state, target]


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
    """Build a DocBook XML tree from expanded blocks."""

    logger.info("=" * 70)
    logger.info("🏗️  BUILDING DOCBOOK TREE")
    logger.info("=" * 70)
    logger.info(f"Total blocks to process: {len(blocks)}")

    label_counts: Dict[str, int] = {}
    blocks_with_text_count = 0
    total_text_chars = 0

    for block in blocks:
        label = (
            block.get("rittdoc_label")
            or block.get("classifier_label")
            or block.get("label", "para")
        )
        text = block.get("text", "")
        label_counts[label] = label_counts.get(label, 0) + 1
        if text and text.strip():
            blocks_with_text_count += 1
            total_text_chars += len(text)

    logger.info(f"Blocks with text content: {blocks_with_text_count}/{len(blocks)}")
    logger.info(f"Total characters in all blocks: {total_text_chars:,}")
    logger.info(f"Block types: {label_counts}")
    logger.info("=" * 70)

    taxonomy = load_label_taxonomy()
    root = etree.Element(root_name)
    manager = ContainerManager(root, taxonomy)
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
        text = (block.get("text") or "").strip()
        entities = block.get("entities") if isinstance(block, dict) else None
        label_name = (
            block.get("rittdoc_label")
            or block.get("classifier_label")
            or block.get("label", "para")
        )
        label_def: Optional[LabelDefinition] = taxonomy.get_label(label_name)
        container_name = (
            block.get("rittdoc_container")
            or (label_def.container if label_def else "book")
        )
        type_name = (
            block.get("rittdoc_type")
            or (label_def.type_name if label_def else label_name)
        )
        starts_container = bool(
            block.get("rittdoc_starts_container")
            or (label_def.starts_container if label_def else False)
        )
        role = block.get("rittdoc_role") or (label_def.role if label_def else None)

        container_element = manager.ensure(container_name, starts_container)

        if container_name == "chapter":
            state["current_chapter"] = container_element
            state["current_section"] = None
            state["current_index"] = None
        elif container_name in {"sect1", "sect2", "sect3"}:
            state["current_section"] = container_element
        elif container_name == "index":
            state["current_index"] = container_element

        if state.get("pending_caption") and type_name not in {
            "figure.caption",
            "table.caption",
            "figure",
            "table",
        }:
            _attach_pending_caption(root, state, None)

        if container_name == "index" and type_name == "entry":
            if _handle_index_para(block, state):
                state["last_structure"] = state.get("current_index")
                continue

        if type_name == "title" and text:
            _ensure_title(container_element, text)
            if container_name == "index":
                state["index_state"] = _initialise_index_state()
            _close_list(state)
            state["last_structure"] = container_element
            continue

        if type_name == "subtitle" and text:
            subtitle = container_element.find("subtitle")
            if subtitle is None:
                subtitle = etree.SubElement(container_element, "subtitle")
            subtitle.text = text
            _close_list(state)
            state["last_structure"] = container_element
            continue

        if type_name == "abstract" and text:
            abstract = container_element.find("abstract")
            if abstract is None:
                abstract = etree.SubElement(container_element, "abstract")
            _append_para(abstract, text, entities)
            _close_list(state)
            state["last_structure"] = abstract
            continue

        if type_name == "toc.entry" and text:
            para = etree.SubElement(container_element, "para")
            para.text = text
            _close_list(state)
            state["last_structure"] = container_element
            continue

        if type_name in {"itemizedlist.item", "orderedlist.item"} and text:
            list_tag = "orderedlist" if "ordered" in type_name else "itemizedlist"
            if (
                state["current_list"] is None
                or state["current_list"].tag != list_tag
                or state["current_list"].getparent() is not container_element
            ):
                state["current_list"] = etree.SubElement(container_element, list_tag)
                state["current_list_type"] = list_tag
            listitem = etree.SubElement(state["current_list"], "listitem")
            _append_para(listitem, text, entities)
            state["last_structure"] = state["current_list"]
            continue

        _close_list(state)

        if type_name == "figure" and block.get("src"):
            figure = etree.SubElement(container_element, "figure")
            if role:
                figure.set("role", role)
            mediaobject = etree.SubElement(figure, "mediaobject")
            imageobject = etree.SubElement(mediaobject, "imageobject")
            etree.SubElement(imageobject, "imagedata", fileref=block["src"])
            _attach_pending_caption(root, state, figure)
            state["last_structure"] = figure
            continue

        if type_name == "table" and block.get("rows"):
            rows = block["rows"]
            cols = len(rows[0]) if rows else 0
            table = etree.SubElement(container_element, "informaltable")
            if role:
                table.set("role", role)
            tgroup = etree.SubElement(table, "tgroup", cols=str(cols))
            tbody = etree.SubElement(tgroup, "tbody")
            for row in rows:
                row_el = etree.SubElement(tbody, "row")
                for cell in row:
                    entry = etree.SubElement(row_el, "entry")
                    entry.text = (cell or "").strip()
            _attach_pending_caption(root, state, table)
            state["last_structure"] = table
            continue

        if type_name in {"figure.caption", "table.caption"} and text:
            if _attach_caption(state.get("last_structure"), text):
                state["pending_caption"] = None
            else:
                _queue_pending_caption(state, text)
            continue

        if container_name == "footnote" and text:
            parent_def = taxonomy.get_container("footnote")
            parent_name = parent_def.parent if parent_def else "book"
            parent_element = manager.ensure(parent_name, False)
            footnote = etree.SubElement(parent_element, "footnote")
            if role:
                footnote.set("role", role)
            _append_para(footnote, text, entities)
            state["last_structure"] = footnote
            continue

        if label_def and container_name in {"metadata", "frontmatter", "preface"}:
            element_name = label_def.element
            if element_name:
                element = etree.SubElement(container_element, element_name)
                if role:
                    element.set("role", role)
                if element_name == "abstract":
                    _append_para(element, text, entities)
                else:
                    element.text = text
                state["last_structure"] = element
                continue

        if type_name in {"note", "tip", "warning", "caution"} and text:
            node = etree.SubElement(container_element, type_name)
            if role:
                node.set("role", role)
            _append_para(node, text, entities)
            state["last_structure"] = node
            continue

        if label_def and label_def.element in {"programlisting", "literallayout", "blockquote"}:
            element = etree.SubElement(container_element, label_def.element)
            if role:
                element.set("role", role)
            element.text = text
            state["last_structure"] = element
            continue

        if text:
            para = _append_para(container_element, text, entities)
            if role and para is not None:
                para.set("role", role)
            state["last_structure"] = container_element

    if state.get("pending_caption"):
        _attach_pending_caption(root, state, None)

    logger.info("=" * 70)
    logger.info("✅ DOCBOOK TREE BUILT")
    logger.info("=" * 70)

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
