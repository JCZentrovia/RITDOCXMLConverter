"""
Utilities to transform a single DocBook XML (DocBook 4.x preferred) into a
publisher-compliant package that mirrors the provided examples:

- book.xml with a specific DOCTYPE and internal ENTITY declarations
- chapter files split as ch0001.xml, ch0002.xml, ... containing <chapter/>
- multimedia/ directory with images referenced by <imagedata fileref="..."/>

This module is intentionally conservative and focuses on predictable structure
over perfect semantic fidelity. It supports inputs produced by pandoc
(docx/epub -> docbook4) and attempts to:
  1) Ensure a <book> root if missing
  2) Split the document into chapters (existing <chapter> elements preferred; if
     none, the whole document becomes a single chapter)
  3) Normalize image paths into multimedia/ and rewrite fileref attributes
  4) Emit a book.xml with the required DOCTYPE + chapter ENTITY references and
     &chXXXX; entity usages in document order
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from lxml import etree


DOCBOOK4_PUBLIC_ID = "-//RIS Dev//DTD DocBook V4.3 -Based Variant V1.1//EN"
DOCBOOK4_SYSTEM_ID = "http://LOCALHOST/dtd/V1.1/RittDocBook.dtd"


@dataclass
class ChapterInfo:
    index: int
    file_name: str  # e.g., ch0001.xml
    id_value: str   # e.g., ch0001


class DocbookPackager:
    def __init__(self, logger=None):
        self.logger = logger

    def _log(self, message: str):
        if self.logger:
            self.logger.info(message)

    @staticmethod
    def _read_xml(xml_path: Path) -> etree._ElementTree:
        parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
        return etree.parse(str(xml_path), parser)

    @staticmethod
    def _write_xml(tree: etree._ElementTree, out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(str(out_path), encoding="UTF-8", xml_declaration=True, pretty_print=False)

    @staticmethod
    def _ensure_book_root(tree: etree._ElementTree, title: str | None = None) -> etree._ElementTree:
        root = tree.getroot()
        if root.tag == "book":
            # Ensure a <title> if provided and not set
            if title and root.find("title") is None:
                t = etree.SubElement(root, "title")
                t.text = title
            return tree

        # Create a new <book> and wrap the existing content
        book = etree.Element("book")
        if title:
            t = etree.SubElement(book, "title")
            t.text = title

        # If the existing root is an article/section/etc, attempt to convert to a chapter
        chapter = etree.Element("chapter")
        # Move children from old root into a container chapter
        # Also move a <title> if exists into chapter.title
        old_title = root.find("title")
        if old_title is not None:
            ch_title = etree.SubElement(chapter, "title")
            ch_title.text = (old_title.text or "").strip()
        for child in list(root):
            # Skip the original title as we copied it
            if child is old_title:
                continue
            chapter.append(child)

        book.append(chapter)
        return etree.ElementTree(book)

    @staticmethod
    def _collect_chapters(book_root: etree._Element) -> List[etree._Element]:
        chapters = book_root.findall("chapter")
        if chapters:
            return chapters
        # Fallback: treat the entire book content as a single chapter
        # Gather all children except book title/bookinfo to form a single chapter
        chapter = etree.Element("chapter")
        # Try to synthesize a title if missing
        if book_root.find("title") is not None:
            t = etree.SubElement(chapter, "title")
            t.text = (book_root.findtext("title") or "").strip()
        for child in list(book_root):
            if child.tag in {"title", "bookinfo"}:
                continue
            chapter.append(child)

        # Remove moved children from book root
        for child in list(book_root):
            if child.tag not in {"title", "bookinfo"}:
                book_root.remove(child)
        book_root.append(chapter)
        return [chapter]

    @staticmethod
    def _zero_pad(n: int, width: int = 4) -> str:
        return str(n).zfill(width)

    @staticmethod
    def _enumerate_imagedata_paths(elem: etree._Element) -> List[etree._Element]:
        return list(elem.iterfind(".//imagedata"))

    def _rewrite_images_to_multimedia(
        self,
        chapter_elem: etree._Element,
        media_root: Path,
        multimedia_dir: Path,
        chapter_index: int,
    ) -> int:
        """
        Move/copy images referenced by imagedata fileref into multimedia/ while
        preserving the original filename when possible. The fileref is rewritten
        to the bare filename (no 'multimedia/' prefix) to mirror examples.
        Returns number of images handled.
        """
        count = 0
        for img in self._enumerate_imagedata_paths(chapter_elem):
            src = (img.get("fileref") or "").strip()
            if not src:
                continue

            src_path = (media_root / src).resolve() if not Path(src).is_absolute() else Path(src)
            if not src_path.exists():
                # Try relative filenames (pandoc sometimes stores just the basename)
                alt = media_root / Path(src).name
                if alt.exists():
                    src_path = alt
                else:
                    # Leave as-is if not found
                    continue

            count += 1
            # Prefer original filename to mirror samples
            new_name = src_path.name
            dst_path = multimedia_dir / new_name
            multimedia_dir.mkdir(parents=True, exist_ok=True)
            if src_path.resolve() != dst_path.resolve():
                dst_path.write_bytes(src_path.read_bytes())

            # Rewrite fileref to just the filename (examples omit the folder)
            img.set("fileref", new_name)

        return count

    def package(
        self,
        combined_docbook_xml: Path,
        output_dir: Path,
        package_root_folder: str | None = None,
        title: str | None = None,
        media_extracted_dir: Path | None = None,
    ) -> Tuple[Path, List[ChapterInfo]]:
        """
        Build a DocBook package structure from a combined DocBook XML file.

        Returns:
            (book_xml_path, [ChapterInfo, ...])
        """
        self._log(f"Packaging DocBook: {combined_docbook_xml}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # If caller wants a nested root folder (e.g., ISBN), create it
        root_dir = output_dir / package_root_folder if package_root_folder else output_dir
        root_dir.mkdir(parents=True, exist_ok=True)

        tree = self._read_xml(combined_docbook_xml)
        tree = self._ensure_book_root(tree, title=title)
        book_root = tree.getroot()

        # Normalize chapters
        chapters = self._collect_chapters(book_root)

        # Prepare multimedia dir and rewrite images per chapter
        multimedia_dir = root_dir / "multimedia"
        media_root = media_extracted_dir or combined_docbook_xml.parent

        chapter_infos: List[ChapterInfo] = []
        for idx, ch in enumerate(chapters, start=1):
            # Assign stable id + label
            ch_id = f"ch{self._zero_pad(idx)}"
            ch.set("id", ch_id)
            if ch.get("label") is None:
                ch.set("label", str(idx))

            # Rewrite images into multimedia/
            self._rewrite_images_to_multimedia(
                ch,
                media_root=media_root,
                multimedia_dir=multimedia_dir,
                chapter_index=idx,
            )

            # Write chapter file
            ch_filename = f"ch{self._zero_pad(idx)}.xml"
            chapter_infos.append(ChapterInfo(index=idx, file_name=ch_filename, id_value=ch_id))

            ch_tree = etree.ElementTree(ch)
            self._write_xml(ch_tree, root_dir / ch_filename)

        # Build a shallow copy of the <book> without chapter children
        book_shallow = etree.Element("book")

        # Preserve top-level metadata elements (title, bookinfo, preface, etc.) except chapters
        for child in book_root:
            if child.tag == "chapter":
                continue
            book_shallow.append(child)

        # Serialize shallow book content (to be embedded into our manual assembly)
        book_body = etree.tostring(book_shallow, encoding="unicode", with_tail=False)

        # Construct the DOCTYPE with ENTITY declarations
        entity_lines = [
            f"\n\t<!ENTITY ch{self._zero_pad(ci.index)} SYSTEM \"{ci.file_name}\">"
            for ci in chapter_infos
        ]
        internal_subset = "".join(entity_lines) + "\n"

        # Insert entity references where chapters should go — append at the end of book
        chapters_entities = (
            "\n".join([f"\t&ch{self._zero_pad(ci.index)};" for ci in chapter_infos]) + "\n"
        )

        # Assemble final XML string (manual to preserve ENTITY refs)
        book_xml_str = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            f"<!DOCTYPE book PUBLIC \"{DOCBOOK4_PUBLIC_ID}\" \"{DOCBOOK4_SYSTEM_ID}\"["
            f"{internal_subset}]>\n"
        )

        # Place the shallow book content, then injected entity references, then close
        # Remove closing </book> to inject entities before it
        if book_body.endswith("</book>"):
            book_body_without_close = book_body[:-7]  # len("</book>") == 7
        else:
            book_body_without_close = book_body

        book_xml_str += book_body_without_close + "\n" + chapters_entities + "</book>\n"

        book_xml_path = root_dir / "book.xml"
        book_xml_path.write_text(book_xml_str, encoding="utf-8")

        self._log(f"Wrote book.xml and {len(chapter_infos)} chapters to {root_dir}")
        return book_xml_path, chapter_infos
