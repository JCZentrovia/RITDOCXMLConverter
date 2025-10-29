from lxml import etree


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
