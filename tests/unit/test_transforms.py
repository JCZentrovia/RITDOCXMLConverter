from lxml import etree

from pipeline.transform import RittDocTransformResult, transform_docbook_to_rittdoc


def test_pdf_transform_para(tmp_path):
    doc = etree.Element("document")
    etree.SubElement(doc, "block", label="para").text = "Sample"
    xslt = etree.XSLT(etree.parse("pipeline/transform/pdfxml_to_docbook.xsl"))
    result = xslt(doc, **{"root-element": etree.XSLT.strparam("book")})
    xml_doc = etree.fromstring(etree.tostring(result))
    paras = xml_doc.findall("para")
    assert paras and paras[0].text == "Sample"


def test_epub_transform_basic():
    html = etree.XML(
        """
        <html xmlns=\"http://www.w3.org/1999/xhtml\"><body><p>Para</p></body></html>
        """
    )
    xslt = etree.XSLT(etree.parse("pipeline/transform/epub_to_docbook.xsl"))
    result = xslt(html, **{"root-element": etree.XSLT.strparam("book")})
    doc = etree.fromstring(etree.tostring(result))
    paras = doc.findall("para")
    assert paras and paras[0].text == "Para"


def test_transform_docbook_to_rittdoc_injects_bookinfo():
    root = etree.Element("book")
    etree.SubElement(root, "title").text = "Sample Book"
    chapter = etree.SubElement(root, "chapter")
    etree.SubElement(chapter, "title").text = "Chapter"

    transformed = transform_docbook_to_rittdoc(root)

    bookinfo = transformed.root.find("bookinfo")
    assert bookinfo is not None
    assert bookinfo.findtext("title") == "Sample Book"


def test_transform_docbook_to_rittdoc_emits_stylesheet():
    root = etree.Element("book")
    etree.SubElement(root, "title").text = "Styled"

    result = transform_docbook_to_rittdoc(root)

    assert isinstance(result, RittDocTransformResult)
    assert any(
        target == "xml-stylesheet" and "rittdoc.css" in (data or "")
        for target, data in result.processing_instructions
    )
    hrefs = {href for href, _ in result.assets}
    assert "rittdoc.css" in hrefs
