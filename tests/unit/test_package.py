import csv
import io
import struct
import zipfile
import zlib

from lxml import etree

from pipeline.package import package_docbook


def _make_png(width: int = 120, height: int = 120) -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = (
        struct.pack(">I", width)
        + struct.pack(">I", height)
        + b"\x08\x02\x00\x00\x00"
    )
    ihdr = (
        struct.pack(">I", len(ihdr_data))
        + b"IHDR"
        + ihdr_data
        + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    )
    raw_row = b"\x00" + b"\xff\x00\x00" * width
    raw_data = raw_row * height
    compressed = zlib.compress(raw_data)
    idat = (
        struct.pack(">I", len(compressed))
        + b"IDAT"
        + compressed
        + struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    )
    iend = struct.pack(">I", 0) + b"IEND" + b"" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    return header + ihdr + idat + iend


def test_package_docbook_creates_chapters_and_media(tmp_path):
    root = etree.Element("book")
    info = etree.SubElement(root, "bookinfo")
    etree.SubElement(info, "isbn").text = "978-1-2345-6789-0"
    info_media = etree.SubElement(info, "mediaobject")
    info_imageobj = etree.SubElement(info_media, "imageobject")
    etree.SubElement(info_imageobj, "imagedata", fileref="img/logo.png")
    textobject = etree.SubElement(info_media, "textobject")
    etree.SubElement(textobject, "phrase").text = "Publisher logo"

    toc = etree.SubElement(root, "chapter", role="toc")
    etree.SubElement(toc, "title").text = "Table of Contents"

    chapter_one = etree.SubElement(root, "chapter")
    etree.SubElement(chapter_one, "title").text = "Chapter One"
    fig = etree.SubElement(chapter_one, "figure")
    fig.set("id", "fig_1_1")
    media = etree.SubElement(fig, "mediaobject")
    image_obj = etree.SubElement(media, "imageobject")
    etree.SubElement(image_obj, "imagedata", fileref="img/figure1.png")
    fig_caption = etree.SubElement(fig, "caption")
    fig_caption.text = "Figure 1.1: Sample Chart"
    alt_text = etree.SubElement(media, "textobject")
    etree.SubElement(alt_text, "phrase").text = "Chart showing quarterly performance"

    chapter_two = etree.SubElement(root, "chapter")
    etree.SubElement(chapter_two, "title").text = "Chapter Two"

    media_store = {
        "img/figure1.png": _make_png(),
        "img/logo.png": _make_png(60, 60),
    }

    def fetch_media(ref: str):
        return media_store.get(ref)

    target = tmp_path / "output.xml"
    zip_path = package_docbook(root, "book", "dtd/v1.1/docbookx.dtd", str(target), media_fetcher=fetch_media)

    assert zip_path.name == "9781234567890.zip"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = sorted(zf.namelist())
        assert names == [
            "Book.xml",
            "Ch001.xml",
            "Ch002.xml",
            "TableOfContents.xml",
            "media/",
            "media/Book_Images/",
            "media/Book_Images/Chapters/",
            "media/Book_Images/Chapters/Ch0001f01.png",
            "media/Book_Images/Metadata/",
            "media/Book_Images/Metadata/image_catalog.xml",
            "media/Book_Images/Metadata/image_manifest.csv",
            "media/Book_Images/Shared/",
            "media/Book_Images/Shared/logo.png",
        ]

        book_xml = zf.read("Book.xml").decode("utf-8")
        assert "<!ENTITY Ch001 SYSTEM \"Ch001.xml\">" in book_xml
        assert "<!ENTITY Ch002 SYSTEM \"Ch002.xml\">" in book_xml
        assert "<!ENTITY toc SYSTEM \"TableOfContents.xml\">" in book_xml
        assert "&Ch001;" in book_xml
        assert "media/Book_Images/Shared/logo.png" in book_xml

        chapter_data = zf.read("Ch001.xml").decode("utf-8")
        assert "fileref=\"media/Book_Images/Chapters/Ch0001f01.png\"" in chapter_data

        toc_data = zf.read("TableOfContents.xml").decode("utf-8")
        assert "Table of Contents" in toc_data
        assert "Ch001.xml" in toc_data
        assert "Ch002.xml" in toc_data

        media_bytes = zf.read("media/Book_Images/Chapters/Ch0001f01.png")
        assert media_bytes == media_store["img/figure1.png"]

        logo_bytes = zf.read("media/Book_Images/Shared/logo.png")
        assert logo_bytes == media_store["img/logo.png"]

        catalog = etree.fromstring(zf.read("media/Book_Images/Metadata/image_catalog.xml"))
        images = catalog.findall("image")
        assert len(images) == 1
        entry = images[0]
        assert entry.findtext("filename") == "Ch0001f01.png"
        assert entry.findtext("original_filename") == "figure1.png"
        assert entry.findtext("chapter") == "1"
        assert entry.findtext("figure_number") == "1"
        assert entry.findtext("caption") == "Figure 1.1: Sample Chart"
        assert entry.findtext("alt_text") == "Chart showing quarterly performance"
        assert entry.findtext("referenced_in_text") == "true"
        assert entry.findtext("format") == "PNG"
        assert entry.findtext("width") == "120"
        assert entry.findtext("height") == "120"
        assert entry.findtext("file_size")

        manifest = zf.read("media/Book_Images/Metadata/image_manifest.csv").decode("utf-8")
        rows = list(csv.reader(io.StringIO(manifest)))
        assert rows[0] == [
            "Filename",
            "Chapter",
            "Figure",
            "Caption",
            "Alt-Text",
            "Original_Name",
            "File_Size",
            "Format",
        ]
        assert rows[1][0] == "Ch0001f01.png"
        assert rows[1][1] == "1"
        assert rows[1][2] == "1"
        assert rows[1][3] == "Figure 1.1: Sample Chart"
        assert rows[1][4] == "Chart showing quarterly performance"
        assert rows[1][5] == "figure1.png"
        assert rows[1][-1] == "PNG"


def test_package_docbook_creates_index_fragment(tmp_path):
    root = etree.Element("book")

    index_root = etree.SubElement(root, "index")
    etree.SubElement(index_root, "title").text = "Index"
    div = etree.SubElement(index_root, "indexdiv")
    etree.SubElement(div, "title").text = "A"
    entry = etree.SubElement(div, "indexentry")
    etree.SubElement(entry, "primaryie").text = "Apple"
    etree.SubElement(entry, "seeie").text = "10"

    chapter = etree.SubElement(root, "chapter")
    etree.SubElement(chapter, "title").text = "Chapter After"

    target = tmp_path / "output.xml"
    zip_path = package_docbook(root, "book", "dtd/v1.1/docbookx.dtd", str(target))

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = sorted(zf.namelist())
        assert "Index.xml" in names
        assert "Book.xml" in names
        assert "media/" in names
        assert "media/Book_Images/Metadata/image_catalog.xml" in names
        assert "media/Book_Images/Metadata/image_manifest.csv" in names
        # Non-index chapters are still numbered
        assert any(name.startswith("Ch") and name.endswith(".xml") for name in names)

        book_xml = zf.read("Book.xml").decode("utf-8")
        assert "<!ENTITY Index SYSTEM \"Index.xml\">" in book_xml
        assert "&Index;" in book_xml

        index_data = zf.read("Index.xml").decode("utf-8")
        assert "Index" in index_data


def test_package_docbook_reuses_shared_media(tmp_path):
    root = etree.Element("book")
    info = etree.SubElement(root, "bookinfo")
    logo_media = etree.SubElement(info, "mediaobject")
    logo_obj = etree.SubElement(logo_media, "imageobject")
    etree.SubElement(logo_obj, "imagedata", fileref="img/logo.png")
    chapter = etree.SubElement(root, "chapter")
    etree.SubElement(chapter, "title").text = "Chapter"
    para_media = etree.SubElement(chapter, "mediaobject")
    para_obj = etree.SubElement(para_media, "imageobject")
    etree.SubElement(para_obj, "imagedata", fileref="img/logo.png")

    media_store = {"img/logo.png": _make_png(50, 50)}

    def fetch_media(ref: str):
        return media_store.get(ref)

    target = tmp_path / "output.xml"
    zip_path = package_docbook(root, "book", "dtd/v1.1/docbookx.dtd", str(target), media_fetcher=fetch_media)

    with zipfile.ZipFile(zip_path, "r") as zf:
        shared_names = [name for name in zf.namelist() if name.startswith("media/Book_Images/Shared/")]
        assert shared_names.count("media/Book_Images/Shared/logo.png") == 1
        book_xml = zf.read("Book.xml").decode("utf-8")
        assert book_xml.count("media/Book_Images/Shared/logo.png") >= 1
        chapter_xml = zf.read("Ch001.xml").decode("utf-8")
        assert chapter_xml.count("media/Book_Images/Shared/logo.png") == 1
