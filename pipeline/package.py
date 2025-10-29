from __future__ import annotations

import csv
import logging
import re
import string
import tempfile
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from lxml import etree

logger = logging.getLogger(__name__)


MediaFetcher = Callable[[str], Optional[bytes]]


@dataclass
class ChapterFragment:
    """Representation of an extracted chapter fragment."""

    entity: str
    filename: str
    element: etree._Element
    kind: str = "chapter"
    title: str = ""
    section_type: str = ""


@dataclass
class ImageMetadata:
    """Captured metadata for a content image."""

    filename: str
    original_filename: str
    chapter: str
    figure_number: str
    caption: str
    alt_text: str
    referenced_in_text: bool
    width: int
    height: int
    file_size: str
    format: str



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
        "index",
    }


def _is_toc_node(element: etree._Element) -> bool:
    if _local_name(element) != "chapter":
        return False
    role = (element.get("role") or "").lower()
    if role == "toc":
        return True
    title = element.find("title")
    if title is not None:
        text = "".join(title.itertext()).strip().lower()
        if text == "table of contents":
            return True
    return False


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


def _extract_title_text(element: etree._Element) -> str:
    title = element.find("title")
    if title is not None:
        text = "".join(title.itertext()).strip()
        if text:
            return text
    return ""


def _split_root(root: etree._Element) -> Tuple[etree._Element, List[ChapterFragment]]:
    root_copy = etree.Element(root.tag, attrib=dict(root.attrib), nsmap=root.nsmap)
    root_copy.text = root.text
    fragments: List[ChapterFragment] = []
    chapter_index = 0

    for child in root:
        if not isinstance(child.tag, str):
            root_copy.append(deepcopy(child))
            continue

        if _is_toc_node(child):
            entity_id = "toc"
            filename = "TableOfContents.xml"
            title = _extract_title_text(child) or "Table of Contents"
            fragments.append(
                ChapterFragment(
                    entity_id,
                    filename,
                    deepcopy(child),
                    kind="toc",
                    title=title,
                    section_type="toc",
                )
            )
            entity_node = etree.Entity(entity_id)
            entity_node.tail = child.tail
            root_copy.append(entity_node)
            continue

        if _is_chapter_node(child):
            is_index_chapter = False
            local_name = _local_name(child)
            if local_name == "chapter":
                role = (child.get("role") or "").lower()
                if role == "index":
                    is_index_chapter = True
                else:
                    title_text = _extract_title_text(child).strip().lower()
                    if title_text == "index":
                        is_index_chapter = True
            elif local_name == "index":
                is_index_chapter = True

            section_type = _local_name(child) or "chapter"
            if is_index_chapter:
                entity_id = "Index"
                filename = "Index.xml"
                title = _extract_title_text(child) or "Index"
                section_type = "index"
            else:
                chapter_index += 1
                entity_id = f"Ch{chapter_index:03d}"
                filename = f"{entity_id}.xml"
                title = _extract_title_text(child)
            fragments.append(
                ChapterFragment(
                    entity_id,
                    filename,
                    deepcopy(child),
                    kind="chapter",
                    title=title,
                    section_type=section_type,
                )
            )
            entity_node = etree.Entity(entity_id)
            entity_node.tail = child.tail
            root_copy.append(entity_node)
            continue

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

        entity_id = "Ch001"
        filename = f"{entity_id}.xml"
        wrapper = etree.Element("chapter")
        for node in extracted:
            wrapper.append(node)
        fragments.append(
            ChapterFragment(entity_id, filename, wrapper, title="", section_type="chapter")
        )

        root_copy[:] = []
        root_copy.text = root.text
        for node in preserved:
            root_copy.append(node)
        entity_node = etree.Entity(entity_id)
        root_copy.append(entity_node)

    root_copy.tail = root.tail
    return root_copy, fragments


def _populate_toc_fragment(
    toc_fragment: ChapterFragment, chapter_fragments: Sequence[ChapterFragment]
) -> None:
    element = toc_fragment.element
    title_el = element.find("title")
    desired_title = toc_fragment.title or "Table of Contents"
    if title_el is None:
        title_el = etree.SubElement(element, "title")
    title_el.text = desired_title

    for child in list(element):
        if child is title_el:
            continue
        element.remove(child)

    itemized = etree.SubElement(element, "itemizedlist")
    for fragment in chapter_fragments:
        listitem = etree.SubElement(itemized, "listitem")
        para = etree.SubElement(listitem, "para")
        chapter_title = fragment.title or fragment.filename
        para.text = f"{chapter_title} ({fragment.filename})"


def _iter_imagedata(element: etree._Element) -> Iterable[etree._Element]:
    for node in element.iter():
        if isinstance(node.tag, str) and _local_name(node) in {"imagedata", "graphic"}:
            if node.get("fileref"):
                yield node


def _extract_caption_text(figure: Optional[etree._Element]) -> str:
    if figure is None:
        return ""
    caption = figure.find("caption")
    if caption is not None:
        text = "".join(caption.itertext()).strip()
        if text:
            return text
    title = figure.find("title")
    if title is not None:
        text = "".join(title.itertext()).strip()
        if text:
            return text
    return ""


def _extract_alt_text(image_node: etree._Element) -> str:
    alt = image_node.get("alt") or image_node.get("xlink:title")
    if alt:
        return alt.strip()

    mediaobject = next(
        (ancestor for ancestor in image_node.iterancestors() if _local_name(ancestor) == "mediaobject"),
        None,
    )
    if mediaobject is not None:
        for textobject in mediaobject.findall("textobject"):
            text = "".join(textobject.itertext()).strip()
            if text:
                return text
    return ""


DECORATIVE_KEYWORDS = {"logo", "watermark", "copyright", "trademark", "tm", "brand"}
BACKGROUND_KEYWORDS = {"background", "texture", "gradient", "border", "pattern"}
BOOKINFO_NODES = {"bookinfo", "info", "titlepage"}


def _classify_image(image_node: etree._Element, figure: Optional[etree._Element]) -> str:
    original = image_node.get("fileref", "")
    name = Path(original).name.lower()
    if figure is not None:
        return "content"

    ancestors = {_local_name(ancestor) for ancestor in image_node.iterancestors()}
    if ancestors & BOOKINFO_NODES:
        return "decorative"

    if any(keyword in name for keyword in DECORATIVE_KEYWORDS):
        return "decorative"
    if any(keyword in name for keyword in BACKGROUND_KEYWORDS):
        return "background"

    role = (image_node.get("role") or "").lower()
    if role in {"decorative", "background"}:
        return "background" if role == "background" else "decorative"

    return "content"


def _format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes}B"


def _inspect_image_bytes(data: bytes, fallback_suffix: str) -> Tuple[int, int, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width = int.from_bytes(data[16:20], "big", signed=False)
        height = int.from_bytes(data[20:24], "big", signed=False)
        return width, height, "PNG"

    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        if len(data) >= 10:
            width = int.from_bytes(data[6:8], "little", signed=False)
            height = int.from_bytes(data[8:10], "little", signed=False)
            return width, height, "GIF"

    if data.startswith(b"\xff\xd8"):
        offset = 2
        length = len(data)
        while offset + 1 < length:
            if data[offset] != 0xFF:
                break
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:  # SOI/EOI
                continue
            if offset + 1 >= length:
                break
            block_length = int.from_bytes(data[offset : offset + 2], "big", signed=False)
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if offset + 7 <= length:
                    height = int.from_bytes(data[offset + 3 : offset + 5], "big", signed=False)
                    width = int.from_bytes(data[offset + 5 : offset + 7], "big", signed=False)
                    return width, height, "JPEG"
                break
            offset += block_length

    suffix = fallback_suffix.lstrip(".")
    return 0, 0, suffix.upper() if suffix else ""


def _chapter_code(fragment: ChapterFragment) -> Tuple[str, str]:
    entity = fragment.entity
    if entity.lower() == "toc":
        return "TOC", "TOC"
    if entity.lower() == "index":
        return "Index", "Index"

    section_type = (fragment.section_type or "").lower()
    if section_type == "appendix":
        title = fragment.title or ""
        match = re.search(r"appendix\s+([A-Z])", title, re.IGNORECASE)
        letter = match.group(1).upper() if match else "A"
        return f"Appendix{letter}", f"Appendix {letter}"

    match = re.match(r"Ch(\d+)", entity, re.IGNORECASE)
    if match:
        chapter_num = int(match.group(1))
        return f"Ch{chapter_num:04d}", str(chapter_num)

    return "Ch0001", "1"


def _write_metadata_files(metadata_dir: Path, entries: List[ImageMetadata]) -> None:
    metadata_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = metadata_dir / "image_catalog.xml"
    root = etree.Element("images")
    for entry in entries:
        image_el = etree.SubElement(root, "image")
        etree.SubElement(image_el, "filename").text = entry.filename
        etree.SubElement(image_el, "original_filename").text = entry.original_filename
        etree.SubElement(image_el, "chapter").text = entry.chapter
        etree.SubElement(image_el, "figure_number").text = entry.figure_number
        etree.SubElement(image_el, "caption").text = entry.caption
        etree.SubElement(image_el, "alt_text").text = entry.alt_text
        etree.SubElement(image_el, "referenced_in_text").text = str(entry.referenced_in_text).lower()
        etree.SubElement(image_el, "width").text = str(entry.width)
        etree.SubElement(image_el, "height").text = str(entry.height)
        etree.SubElement(image_el, "file_size").text = entry.file_size
        etree.SubElement(image_el, "format").text = entry.format

    catalog_path.write_bytes(
        etree.tostring(root, encoding="UTF-8", pretty_print=True, xml_declaration=True)
    )

    manifest_path = metadata_dir / "image_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Filename",
                "Chapter",
                "Figure",
                "Caption",
                "Alt-Text",
                "Original_Name",
                "File_Size",
                "Format",
            ]
        )
        for entry in entries:
            writer.writerow(
                [
                    entry.filename,
                    entry.chapter,
                    entry.figure_number,
                    entry.caption,
                    entry.alt_text,
                    entry.original_filename,
                    entry.file_size,
                    entry.format,
                ]
            )


def _remove_image_node(image_node: etree._Element) -> None:
    parent = image_node.getparent()
    if parent is not None:
        parent.remove(image_node)


def _handle_decorative_image(
    image_node: etree._Element,
    shared_dir: Path,
    shared_cache: Dict[str, Path],
    media_fetcher: Optional[MediaFetcher],
) -> None:
    original = image_node.get("fileref", "")
    if not original:
        return
    filename = Path(original).name or original
    shared_dir.mkdir(parents=True, exist_ok=True)
    target_path = shared_cache.get(filename)
    if target_path is None:
        target_path = shared_dir / filename
        data = media_fetcher(original) if media_fetcher else None
        if data is None:
            logger.warning("Missing decorative media asset for %s; creating placeholder", original)
            target_path.touch(exist_ok=True)
            shared_cache[filename] = target_path
        elif len(data) == 0:
            logger.warning("Skipping decorative image %s because it is empty", original)
            _remove_image_node(image_node)
            return
        else:
            target_path.write_bytes(data)
            shared_cache[filename] = target_path
    image_node.set("fileref", f"media/Book_Images/Shared/{filename}")

def _write_book_xml(
    target: Path,
    root_element: etree._Element,
    root_name: str,
    dtd_system: str,
    fragments: Sequence[ChapterFragment],
    *,
    processing_instructions: Sequence[Tuple[str, str]] = (),
) -> None:
    header = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    for target_name, data in processing_instructions:
        header.append(f"<?{target_name} {data}?>")
    header.append(f"<!DOCTYPE {root_name} SYSTEM \"{dtd_system}\"[")
    for fragment in fragments:
        header.append(f"        <!ENTITY {fragment.entity} SYSTEM \"{fragment.filename}\">")
    header.append("]>")
    header_text = "\n".join(header) + "\n\n"

    body = etree.tostring(root_element, encoding="UTF-8", pretty_print=True, xml_declaration=False)
    target.write_text(header_text + body.decode("utf-8"), encoding="utf-8")


def _write_fragment_xml(
    target: Path,
    element: etree._Element,
    dtd_system: str,
    *,
    processing_instructions: Sequence[Tuple[str, str]] = (),
) -> None:
    root_tag = _local_name(element) or (
        element.tag if isinstance(element.tag, str) else "chapter"
    )
    header_lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    for target_name, data in processing_instructions:
        header_lines.append(f"<?{target_name} {data}?>")
    header_lines.append(f"<!DOCTYPE {root_tag} SYSTEM \"{dtd_system}\">")
    header = "\n".join(header_lines) + "\n\n"
    body = etree.tostring(element, encoding="UTF-8", pretty_print=True, xml_declaration=False)
    target.write_text(header + body.decode("utf-8"), encoding="utf-8")


def package_docbook(
    root: etree._Element,
    root_name: str,
    dtd_system: str,
    out_path: str,
    *,
    processing_instructions: Sequence[Tuple[str, str]] = (),
    assets: Sequence[Tuple[str, Path]] = (),
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

        media_dir = tmp_path / "media"
        book_images_dir = media_dir / "Book_Images"
        chapters_dir = book_images_dir / "Chapters"
        shared_dir = book_images_dir / "Shared"
        metadata_dir = book_images_dir / "Metadata"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        shared_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        asset_paths: List[Tuple[str, Path]] = []
        for href, source in assets:
            try:
                data = Path(source).read_bytes()
            except OSError as exc:
                logger.warning("Failed to read stylesheet asset %s: %s", source, exc)
                continue
            target_path = (tmp_path / href).resolve()
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning("Failed to create directory for stylesheet %s: %s", href, exc)
                continue
            target_path.write_bytes(data)
            asset_paths.append((href, target_path))

        chapter_paths: List[Tuple[ChapterFragment, Path]] = []
        toc_fragment = next((fragment for fragment in fragments if fragment.kind == "toc"), None)
        chapter_fragments = [fragment for fragment in fragments if fragment.kind == "chapter"]
        if toc_fragment is not None:
            _populate_toc_fragment(toc_fragment, chapter_fragments)
        metadata_entries: List[ImageMetadata] = []
        shared_cache: Dict[str, Path] = {}
        for fragment in fragments:
            chapter_path = tmp_path / fragment.filename
            chapter_code, chapter_label = _chapter_code(fragment)
            figure_counter = 1
            processed_nodes: Set[int] = set()
            for figure in fragment.element.findall(".//figure"):
                caption_text = _extract_caption_text(figure)
                images = list(_iter_imagedata(figure))
                if not images:
                    continue
                if len(images) == 1:
                    suffixes = [""]
                else:
                    suffixes = [
                        string.ascii_lowercase[idx]
                        if idx < len(string.ascii_lowercase)
                        else f"_{idx}"
                        for idx in range(len(images))
                    ]
                current_index = figure_counter
                for idx, image_node in enumerate(images):
                    processed_nodes.add(id(image_node))
                    original = image_node.get("fileref")
                    if not original:
                        continue
                    classification = _classify_image(image_node, figure)
                    if classification == "background":
                        parent = image_node.getparent()
                        if parent is not None:
                            parent.remove(image_node)
                        continue
                    if classification == "decorative":
                        _handle_decorative_image(image_node, shared_dir, shared_cache, media_fetcher)
                        continue

                    suffix = Path(original).suffix or ".jpg"
                    letter = suffixes[idx]
                    new_filename = f"{chapter_code}f{current_index:02d}{letter}{suffix}"
                    target_path = chapters_dir / new_filename
                    data = media_fetcher(original) if media_fetcher else None
                    if data is None:
                        logger.warning("Missing media asset for %s; creating placeholder", original)
                        target_path.touch(exist_ok=True)
                        width = height = 0
                        fmt = suffix.lstrip(".").upper()
                        file_size = "0B"
                    else:
                        if len(data) == 0:
                            logger.warning("Skipping media asset for %s because it is empty", original)
                            _remove_image_node(image_node)
                            continue
                        target_path.write_bytes(data)
                        width, height, fmt = _inspect_image_bytes(data, suffix)
                        file_size = _format_file_size(len(data))
                        if width and height and (width < 72 or height < 72):
                            logger.warning(
                                "Low resolution image %s detected (%dx%d)", original, width, height
                            )
                    alt_text = _extract_alt_text(image_node)
                    if not alt_text:
                        logger.warning("Missing alt text for image %s", original)
                    referenced = bool((figure.get("id") or "").strip())
                    if not referenced and caption_text:
                        if re.search(r"figure\s+\d", caption_text, re.IGNORECASE):
                            referenced = True
                    metadata_entries.append(
                        ImageMetadata(
                            filename=new_filename,
                            original_filename=Path(original).name or original,
                            chapter=chapter_label,
                            figure_number=f"{current_index}{letter}",
                            caption=caption_text or "",
                            alt_text=alt_text,
                            referenced_in_text=referenced,
                            width=width,
                            height=height,
                            file_size=file_size,
                            format=fmt,
                        )
                    )
                    image_node.set(
                        "fileref", f"media/Book_Images/Chapters/{new_filename}"
                    )
                figure_counter += 1

            for image_node in _iter_imagedata(fragment.element):
                if id(image_node) in processed_nodes:
                    continue
                original = image_node.get("fileref")
                if not original:
                    continue
                classification = _classify_image(image_node, None)
                if classification == "background":
                    parent = image_node.getparent()
                    if parent is not None:
                        parent.remove(image_node)
                    continue
                if classification == "decorative":
                    _handle_decorative_image(image_node, shared_dir, shared_cache, media_fetcher)
                    continue

                suffix = Path(original).suffix or ".jpg"
                current_index = figure_counter
                new_filename = f"{chapter_code}f{current_index:02d}{suffix}"
                target_path = chapters_dir / new_filename
                data = media_fetcher(original) if media_fetcher else None
                if data is None:
                    logger.warning("Missing media asset for %s; creating placeholder", original)
                    target_path.touch(exist_ok=True)
                    width = height = 0
                    fmt = suffix.lstrip(".").upper()
                    file_size = "0B"
                else:
                    if len(data) == 0:
                        logger.warning("Skipping media asset for %s because it is empty", original)
                        _remove_image_node(image_node)
                        continue
                    target_path.write_bytes(data)
                    width, height, fmt = _inspect_image_bytes(data, suffix)
                    file_size = _format_file_size(len(data))
                    if width and height and (width < 72 or height < 72):
                        logger.warning(
                            "Low resolution image %s detected (%dx%d)", original, width, height
                        )
                alt_text = _extract_alt_text(image_node)
                if not alt_text:
                    logger.warning("Missing alt text for image %s", original)
                placeholder_caption = f"Figure {chapter_label}.{current_index:02d} (Unlabeled)"
                metadata_entries.append(
                    ImageMetadata(
                        filename=new_filename,
                        original_filename=Path(original).name or original,
                        chapter=chapter_label,
                        figure_number=str(current_index),
                        caption=placeholder_caption,
                        alt_text=alt_text,
                        referenced_in_text=False,
                        width=width,
                        height=height,
                        file_size=file_size,
                        format=fmt,
                    )
                )
                image_node.set("fileref", f"media/Book_Images/Chapters/{new_filename}")
                figure_counter += 1

            _write_fragment_xml(
                chapter_path,
                fragment.element,
                dtd_system,
                processing_instructions=processing_instructions,
            )
            chapter_paths.append((fragment, chapter_path))

        for image_node in _iter_imagedata(book_root):
            original = image_node.get("fileref")
            if not original:
                continue
            classification = _classify_image(image_node, None)
            if classification == "background":
                parent = image_node.getparent()
                if parent is not None:
                    parent.remove(image_node)
                continue
            if classification == "decorative":
                _handle_decorative_image(image_node, shared_dir, shared_cache, media_fetcher)
            else:
                logger.warning(
                    "Unexpected content image in root document: %s; treating as decorative",
                    original,
                )
                _handle_decorative_image(image_node, shared_dir, shared_cache, media_fetcher)

        _write_metadata_files(metadata_dir, metadata_entries)
        _write_book_xml(
            book_path,
            book_root,
            root_name,
            dtd_system,
            fragments,
            processing_instructions=processing_instructions,
        )

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(book_path, "Book.xml")
            for fragment, chapter_path in chapter_paths:
                zf.write(chapter_path, fragment.filename)
            for directory in [media_dir, book_images_dir, chapters_dir, shared_dir, metadata_dir]:
                zf.writestr(str(directory.relative_to(tmp_path)).rstrip("/") + "/", "")
            for media_file in sorted(media_dir.rglob("*")):
                if media_file.is_dir():
                    continue
                rel_path = media_file.relative_to(tmp_path)
                zf.write(media_file, str(rel_path))
            for href, asset_path in asset_paths:
                arcname = Path(href).as_posix()
                zf.write(asset_path, arcname)

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
