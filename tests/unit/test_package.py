import zipfile

from lxml import etree

from pipeline.package import package_docbook


def test_package_docbook_creates_chapters_and_media(tmp_path):
    root = etree.Element("book")
    info = etree.SubElement(root, "bookinfo")
    etree.SubElement(info, "isbn").text = "978-1-2345-6789-0"

    chapter_one = etree.SubElement(root, "chapter")
    etree.SubElement(chapter_one, "title").text = "Chapter One"
    fig = etree.SubElement(chapter_one, "figure")
    media = etree.SubElement(fig, "mediaobject")
    image_obj = etree.SubElement(media, "imageobject")
    etree.SubElement(image_obj, "imagedata", fileref="img/figure1.jpg")

    chapter_two = etree.SubElement(root, "chapter")
    etree.SubElement(chapter_two, "title").text = "Chapter Two"

    media_store = {"img/figure1.jpg": b"JPEGDATA"}

    def fetch_media(ref: str):
        return media_store.get(ref)

    target = tmp_path / "output.xml"
    zip_path = package_docbook(root, "book", "dtd/v1.1/docbookx.dtd", str(target), media_fetcher=fetch_media)

    assert zip_path.name == "9781234567890.zip"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = sorted(zf.namelist())
        assert names == [
            "Book.xml",
            "ch0001.xml",
            "ch0002.xml",
            "media/",
            "media/ch0001f01.jpg",
        ]

        book_xml = zf.read("Book.xml").decode("utf-8")
        assert "<!ENTITY ch0001 SYSTEM \"ch0001.xml\">" in book_xml
        assert "<!ENTITY ch0002 SYSTEM \"ch0002.xml\">" in book_xml
        assert "&ch0001;" in book_xml

        chapter_data = zf.read("ch0001.xml").decode("utf-8")
        assert "fileref=\"media/ch0001f01.jpg\"" in chapter_data

        media_bytes = zf.read("media/ch0001f01.jpg")
        assert media_bytes == media_store["img/figure1.jpg"]
