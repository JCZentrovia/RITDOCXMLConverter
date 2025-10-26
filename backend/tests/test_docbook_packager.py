import os
from pathlib import Path
from lxml import etree

from app.utils.docbook_packager import DocbookPackager


def test_packager_creates_book_and_chapters(tmp_path: Path):
    # Minimal combined docbook4 content with two chapters and images
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<book>\n"
        "  <title>Sample Book</title>\n"
        "  <chapter id=\"chA\"><title>One</title><para>Text <inlinemediaobject><imageobject><imagedata fileref=\"img1.jpg\"/></imageobject></inlinemediaobject></para></chapter>\n"
        "  <chapter id=\"chB\"><title>Two</title><para>More</para></chapter>\n"
        "</book>\n"
    )
    combined = tmp_path / "combined.xml"
    combined.write_text(xml, encoding="utf-8")

    # Create dummy image
    (tmp_path / "img1.jpg").write_bytes(b"fakejpg")

    packager = DocbookPackager()
    book_xml_path, chapters = packager.package(
        combined_docbook_xml=combined,
        output_dir=tmp_path / "out",
        package_root_folder=None,
        title="Sample Book",
        media_extracted_dir=tmp_path,
    )

    # book.xml exists
    assert book_xml_path.exists()
    # Chapters written
    for ci in chapters:
        assert (book_xml_path.parent / ci.file_name).exists()
    # Multimedia exists
    assert (book_xml_path.parent / "multimedia").exists()

    # book.xml has DOCTYPE and entities
    raw = book_xml_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE book PUBLIC" in raw
    assert "<!ENTITY ch0001" in raw
    assert "&ch0001;" in raw


def test_packager_zip_contains_multimedia_images(tmp_path: Path):
    # Combined docbook with a single chapter referencing an image
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<book>\n"
        "  <title>Sample Book</title>\n"
        "  <chapter><title>One</title><para>Text <inlinemediaobject><imageobject><imagedata fileref=\"imgA.jpg\"/></imageobject></inlinemediaobject></para></chapter>\n"
        "</book>\n"
    )
    combined = tmp_path / "combined.xml"
    combined.write_text(xml, encoding="utf-8")

    # Create dummy image that should be copied into multimedia/
    (tmp_path / "imgA.jpg").write_bytes(b"fakejpgdata")

    packager = DocbookPackager()
    package_dir = tmp_path / "out"
    book_xml_path, _ = packager.package(
        combined_docbook_xml=combined,
        output_dir=package_dir,
        package_root_folder=None,
        title="Sample Book",
        media_extracted_dir=tmp_path,
    )

    # Create a zip archive of the package contents
    import shutil
    import zipfile

    root_dir = book_xml_path.parent
    zip_base = tmp_path / "package"
    zip_path = shutil.make_archive(str(zip_base), "zip", root_dir)

    # Verify zip contains multimedia folder and the image file
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert any(n.endswith("multimedia/") or n.endswith("multimedia") for n in names), "multimedia folder missing in ZIP"
        assert any(n.endswith("multimedia/imgA.jpg") for n in names), "image not found in multimedia/ within ZIP"
        assert any(n.endswith("book.xml") for n in names), "book.xml missing in ZIP"
