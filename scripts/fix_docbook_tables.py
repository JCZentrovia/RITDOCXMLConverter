#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix DocBook tables that have empty <tbody> (no <row>), which violates the schema.
Strategy:
- For each informaltable/tgroup:
  - If <tbody> exists but has 0 <row>:
      * If <thead> has rows: move those rows into a new <tbody>, remove <thead>.
      * Else: remove the entire <informaltable> (it's empty / malformed).
"""

import sys
from pathlib import Path
from lxml import etree

DB_NS = "http://docbook.org/ns/docbook"
NSMAP = {"db": DB_NS}
DB = "{%s}" % DB_NS

def fix_tables(tree: etree._ElementTree) -> int:
    root = tree.getroot()
    changed = 0

    for it in root.xpath(".//db:informaltable", namespaces=NSMAP):
        # We will look within tgroup
        tg = it.find(f"{DB}tgroup")
        if tg is None:
            # malformed: no tgroup => remove table
            it.getparent().remove(it)
            changed += 1
            continue

        thead = tg.find(f"{DB}thead")
        tbody = tg.find(f"{DB}tbody")

        def get_rows(elem):
            return [] if elem is None else elem.findall(f"{DB}row")

        body_rows = get_rows(tbody)
        head_rows = get_rows(thead)

        if tbody is not None and len(body_rows) == 0:
            if len(head_rows) > 0:
                # Create a new tbody and move head rows there
                new_tbody = etree.Element(f"{DB}tbody")
                for r in head_rows:
                    new_tbody.append(r)
                # remove old thead
                if thead is not None:
                    tg.remove(thead)
                # replace/insert tbody
                tg.remove(tbody)
                tg.append(new_tbody)
                changed += 1
            else:
                # No rows anywhere => remove the whole table
                parent = it.getparent()
                parent.remove(it)
                changed += 1

        # Also: if there's no tbody at all but thead has rows, convert thead->tbody
        elif tbody is None and len(head_rows) > 0:
            new_tbody = etree.Element(f"{DB}tbody")
            for r in head_rows:
                new_tbody.append(r)
            # remove old thead and add tbody
            tg.remove(thead)
            tg.append(new_tbody)
            changed += 1

    return changed

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/fix_docbook_tables.py <in.xml> <out.xml>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(in_path), parser)

    changed = fix_tables(tree)
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True, pretty_print=False)
    print(f"Fixed tables: {changed}. Wrote: {out_path}")

if __name__ == "__main__":
    main()
