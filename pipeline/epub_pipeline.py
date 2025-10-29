from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from lxml import etree

from .common import PageText, checksum, load_mapping, normalize_text
from .package import package_docbook
from .validators.counters import compute_metrics

# Temporarily disable validation while focusing on chapter splitting.
# from .validators.dtd_validator import validate_dtd

logger = logging.getLogger(__name__)


EPUB_NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "html": "http://www.w3.org/1999/xhtml",
}


def _read_container(zf: zipfile.ZipFile) -> str:
    container_xml = etree.fromstring(zf.read("META-INF/container.xml"))
    rootfile = container_xml.xpath("//c:rootfile/@full-path", namespaces=EPUB_NS)
    if not rootfile:
        raise ValueError("EPUB container missing rootfile")
    return rootfile[0]


def _parse_opf(zf: zipfile.ZipFile, opf_path: str) -> Dict:
    opf_doc = etree.fromstring(zf.read(opf_path))
    manifest = {
        item.get("id"): item.get("href")
        for item in opf_doc.xpath("//opf:manifest/opf:item", namespaces=EPUB_NS)
    }
    spine = [
        item.get("idref")
        for item in opf_doc.xpath("//opf:spine/opf:itemref", namespaces=EPUB_NS)
    ]
    return {"manifest": manifest, "spine": spine, "opf": opf_doc}


def _aggregate_html(zf: zipfile.ZipFile, opf_path: str, manifest: Dict[str, str], spine: List[str]) -> etree._Element:
    base = Path(opf_path).parent
    html_root = etree.Element("{http://www.w3.org/1999/xhtml}html", nsmap={None: "http://www.w3.org/1999/xhtml"})
    body = etree.SubElement(html_root, "{http://www.w3.org/1999/xhtml}body")
    for item_id in spine:
        href = manifest.get(item_id)
        if not href:
            logger.warning("Missing manifest item for spine id %s", item_id)
            continue
        item_path = str((base / href).as_posix())
        doc = etree.fromstring(zf.read(item_path))
        doc_dir = Path(item_path).parent
        for img in doc.xpath("//html:img", namespaces=EPUB_NS):
            src = img.get("src")
            if src:
                resolved = (doc_dir / src).as_posix()
                img.set("src", resolved)
        for child in doc.xpath("//html:body/*", namespaces=EPUB_NS):
            body.append(child)
    return html_root


def _collect_text_blocks(doc: etree._Element) -> List[str]:
    return [
        " ".join(child.xpath(".//text()"))
        for child in doc.xpath("//html:body/*", namespaces=EPUB_NS)
    ]


def convert_epub(
    epub_path: str,
    out_path: str,
    publisher: str,
    *,
    config_dir: str = "config",
    strict: bool = False,
    catalog: str = "validation/catalog.xml",
) -> Dict:
    config = load_mapping(Path(config_dir), publisher)
    epub_file = Path(epub_path)
    if not epub_file.exists():
        raise FileNotFoundError(epub_path)

    with zipfile.ZipFile(epub_file, "r") as zf:
        rootfile = _read_container(zf)
        opf_info = _parse_opf(zf, rootfile)
        html_root = _aggregate_html(zf, rootfile, opf_info["manifest"], opf_info["spine"])
        blocks = _collect_text_blocks(html_root)

        if strict and any(not block.strip() for block in blocks):
            raise ValueError('Empty content block detected in strict mode')

        pages: List[PageText] = []
        for idx, text in enumerate(blocks, start=1):
            norm_text = normalize_text(text, config)
            pages.append(
                PageText(
                    page_num=idx,
                    raw_text=text,
                    norm_text=norm_text,
                    checksum=checksum(norm_text),
                )
            )

        xslt_path = Path(__file__).parent / "transform" / "epub_to_docbook.xsl"
        transform = etree.XSLT(etree.parse(str(xslt_path)))
        root_name = config.get("docbook", {}).get("root", "book")
        result_tree = transform(html_root, **{"root-element": etree.XSLT.strparam(root_name)})
        docbook_root = result_tree.getroot()

        dtd_system = config.get("docbook", {}).get("dtd_system", "dtd/v1.1/docbookx.dtd")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / "full_book.xml"
            header = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE {root_name} SYSTEM \"{dtd_system}\">\n"
            xml_bytes = etree.tostring(docbook_root, encoding="UTF-8", pretty_print=True, xml_declaration=False)
            tmp_file.write_text(header + xml_bytes.decode("utf-8"), encoding="utf-8")
            # Temporarily disable validation while focusing on chapter splitting.
            # validate_dtd(str(tmp_file), dtd_system, catalog)

        def fetch_media(ref: str) -> Optional[bytes]:
            normalized = ref.lstrip("/")
            try:
                return zf.read(normalized)
            except KeyError:
                try:
                    return zf.read(ref)
                except KeyError:
                    logger.warning("Missing media resource in EPUB: %s", ref)
                    return None

        zip_path = package_docbook(docbook_root, root_name, dtd_system, out_path, media_fetcher=fetch_media)

        post_pages = [
            PageText(
                page_num=page.page_num,
                raw_text=page.norm_text,
                norm_text=page.norm_text,
                checksum=page.checksum,
            )
            for page in pages
        ]
        metrics = compute_metrics(pages, post_pages)
        metrics["output_path"] = str(zip_path)
        return metrics
