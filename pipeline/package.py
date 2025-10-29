from __future__ import annotations

import logging
import re
import tempfile
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from lxml import etree

logger = logging.getLogger(__name__)


MediaFetcher = Callable[[str], Optional[bytes]]


@dataclass
class ChapterFragment:
    """Representation of an extracted chapter fragment."""

    entity: str
    filename: str
    element: etree._Element


def _local_name(element: etree._Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _is_chapter_node(element: etree._Element) -> bool:
    tag = _local_name(element)
    return tag in {
        "chapter",
        "preface",
        "appendix",
        "part",
        "article",
        "section",
        "sect1",
    }


def _extract_isbn(root: etree._Element) -> Optional[str]:
    isbn_elements = root.xpath(".//isbn")
    for node in isbn_elements:
        if isinstance(node, etree._Element):
            text = (node.text or "").strip()
            if text:
                cleaned = re.sub(r"[^0-9A-Za-z]", "", text)
                if cleaned:
                    return cleaned
    return None


def _sanitise_basename(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_-]", "", name)
    return cleaned or "book"


def _split_root(root: etree._Element) -> Tuple[etree._Element, List[ChapterFragment]]:
    root_copy = etree.Element(root.tag, attrib=dict(root.attrib), nsmap=root.nsmap)
    root_copy.text = root.text
    fragments: List[ChapterFragment] = []

    for child in root:
        if isinstance(child.tag, str) and _is_chapter_node(child):
            entity_id = f"ch{len(fragments) + 1:04d}"
            filename = f"{entity_id}.xml"
            fragments.append(ChapterFragment(entity_id, filename, deepcopy(child)))
            entity_node = etree.Entity(entity_id)
            entity_node.tail = child.tail
            root_copy.append(entity_node)
        else:
            root_copy.append(deepcopy(child))

    if not fragments:
        # Fallback: treat non-metadata children as a single chapter to ensure
        # downstream consumers receive at least one fragment.
        preserved = []
        extracted = []
        for child in root:
            if not isinstance(child.tag, str):
                preserved.append(deepcopy(child))
                continue
            if _local_name(child) in {"bookinfo", "info"}:
                preserved.append(deepcopy(child))
            else:
                extracted.append(deepcopy(child))

        entity_id = "ch0001"
        filename = f"{entity_id}.xml"
        wrapper = etree.Element("chapter")
        for node in extracted:
            wrapper.append(node)
        fragments.append(ChapterFragment(entity_id, filename, wrapper))

        root_copy[:] = []
        root_copy.text = root.text
        for node in preserved:
            root_copy.append(node)
        entity_node = etree.Entity(entity_id)
        root_copy.append(entity_node)

    root_copy.tail = root.tail
    return root_copy, fragments


def _iter_imagedata(element: etree._Element) -> Iterable[etree._Element]:
    for node in element.iter():
        if isinstance(node.tag, str) and _local_name(node) in {"imagedata", "graphic"}:
            if node.get("fileref"):
                yield node


def _write_book_xml(
    target: Path,
    root_element: etree._Element,
    root_name: str,
    dtd_system: str,
    fragments: Sequence[ChapterFragment],
) -> None:
    header = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    header.append(f"<!DOCTYPE {root_name} SYSTEM \"{dtd_system}\"[")
    for fragment in fragments:
        header.append(f"        <!ENTITY {fragment.entity} SYSTEM \"{fragment.filename}\">")
    header.append("]>")
    header_text = "\n".join(header) + "\n\n"

    body = etree.tostring(root_element, encoding="UTF-8", pretty_print=True, xml_declaration=False)
    target.write_text(header_text + body.decode("utf-8"), encoding="utf-8")


def package_docbook(
    root: etree._Element,
    root_name: str,
    dtd_system: str,
    out_path: str,
    *,
    media_fetcher: Optional[MediaFetcher] = None,
) -> Path:
    """Package the DocBook tree into a chapterised ZIP bundle."""

    book_root, fragments = _split_root(root)
    isbn = _extract_isbn(root)
    base = _sanitise_basename(isbn or Path(out_path).stem or "book")
    zip_path = Path(out_path).with_name(f"{base}.zip")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        book_path = tmp_path / "Book.xml"
        _write_book_xml(book_path, book_root, root_name, dtd_system, fragments)

        media_dir = tmp_path / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        chapter_paths: List[Tuple[ChapterFragment, Path]] = []
        for fragment in fragments:
            chapter_path = tmp_path / fragment.filename
            image_index = 1
            for image_node in _iter_imagedata(fragment.element):
                original = image_node.get("fileref")
                suffix = Path(original).suffix or ".jpg"
                new_name = f"{fragment.entity}f{image_index:02d}{suffix}"
                image_index += 1
                image_node.set("fileref", f"media/{new_name}")

                data = media_fetcher(original) if media_fetcher else None
                media_target = media_dir / new_name
                if data is None:
                    logger.warning("Missing media asset for %s; creating placeholder", original)
                    media_target.touch(exist_ok=True)
                else:
                    media_target.write_bytes(data)

            chapter_bytes = etree.tostring(
                fragment.element, encoding="UTF-8", pretty_print=True, xml_declaration=False
            )
            chapter_path.write_bytes(chapter_bytes)
            chapter_paths.append((fragment, chapter_path))

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(book_path, "Book.xml")
            for fragment, chapter_path in chapter_paths:
                zf.write(chapter_path, fragment.filename)
            zf.writestr("media/", "")
            for media_file in sorted(media_dir.iterdir()):
                zf.write(media_file, f"media/{media_file.name}")

    return zip_path


def make_file_fetcher(search_paths: Sequence[Path]) -> MediaFetcher:
    paths = [Path(p) for p in search_paths]

    def _fetch(name: str) -> Optional[bytes]:
        candidates = [Path(name)] if Path(name).is_absolute() else []
        for base in paths:
            candidates.append(base / name)
        for candidate in candidates:
            if candidate.exists():
                try:
                    return candidate.read_bytes()
                except OSError as exc:
                    logger.warning("Failed reading media %s: %s", candidate, exc)
        return None

    return _fetch
