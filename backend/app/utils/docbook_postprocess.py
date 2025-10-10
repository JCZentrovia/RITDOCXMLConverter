# backend/app/utils/docbook_postprocess.py
from lxml import etree
from pathlib import Path

DB_NS = "http://docbook.org/ns/docbook"
NSMAP = {"db": DB_NS}
DB = "{%s}" % DB_NS

def fix_tables(tree: etree._ElementTree) -> int:
    """
    Fix DocBook tables that have empty <tbody> (no <row>), which violates the schema.
    - If <thead> has rows and <tbody> is empty: move head rows into a new <tbody>.
    - If neither thead nor tbody has rows: remove the entire <informaltable>.
    Returns: number of changes made.
    """
    root = tree.getroot()
    changed = 0

    for it in root.xpath(".//db:informaltable", namespaces=NSMAP):
        tg = it.find(f"{DB}tgroup")
        if tg is None:
            it.getparent().remove(it)
            changed += 1
            continue

        thead = tg.find(f"{DB}thead")
        tbody = tg.find(f"{DB}tbody")

        def rows(elem):
            return [] if elem is None else elem.findall(f"{DB}row")

        body_rows = rows(tbody)
        head_rows = rows(thead)

        if tbody is not None and len(body_rows) == 0:
            if len(head_rows) > 0:
                new_tbody = etree.Element(f"{DB}tbody")
                for r in head_rows:
                    new_tbody.append(r)
                if thead is not None:
                    tg.remove(thead)
                tg.remove(tbody)
                tg.append(new_tbody)
                changed += 1
            else:
                it.getparent().remove(it)
                changed += 1

        elif tbody is None and len(head_rows) > 0:
            new_tbody = etree.Element(f"{DB}tbody")
            for r in head_rows:
                new_tbody.append(r)
            tg.remove(thead)
            tg.append(new_tbody)
            changed += 1

    return changed

def ensure_docbook5_root(xml_path: Path, root_tag: str = "article", title: str | None = None):
    """
    Ensure the XML has a DocBook 5 root + namespace and an <info><title>.
    This is a safety belt in case pandoc ever returns a fragment.
    """
    parser = etree.XMLParser(remove_blank_text=False)
    with open(xml_path, "rb") as f:
        data = f.read()

    try:
        root = etree.fromstring(data, parser)
        tree = etree.ElementTree(root)
    except etree.XMLSyntaxError:
        wrapper = etree.Element(f"{{{DB_NS}}}{root_tag}", nsmap={None: DB_NS})
        para = etree.SubElement(wrapper, f"{DB}para")
        para.text = data.decode("utf-8", errors="ignore")
        tree = etree.ElementTree(wrapper)

    root = tree.getroot()
    if not root.tag.startswith("{"+DB_NS+"}"):
        wrapper = etree.Element(f"{{{DB_NS}}}{root_tag}", nsmap={None: DB_NS})
        wrapper.append(root)
        tree = etree.ElementTree(wrapper)

    info = root.find(f"{DB}info")
    if info is None:
        info = etree.SubElement(root, f"{DB}info")
    if title and info.find(f"{DB}title") is None:
        t = etree.SubElement(info, f"{DB}title")
        t.text = title

    tree.write(str(xml_path), encoding="utf-8", xml_declaration=True, pretty_print=False)

def postprocess_docbook_file(xml_path: Path, title: str | None = None) -> int:
    """
    Ensures proper root + fixes tables in-place. Returns number of table fixes.
    """
    ensure_docbook5_root(xml_path, root_tag="article", title=title)
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(xml_path), parser)
    fixed = fix_tables(tree)
    tree.write(str(xml_path), encoding="utf-8", xml_declaration=True, pretty_print=False)
    return fixed
