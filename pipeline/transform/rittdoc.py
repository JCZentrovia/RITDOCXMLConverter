from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from lxml import etree


@lru_cache(maxsize=1)
def _load_transform() -> etree.XSLT:
    xslt_path = Path(__file__).with_name("docbook_to_rittdoc.xsl")
    return etree.XSLT(etree.parse(str(xslt_path)))


def transform_docbook_to_rittdoc(
    root: etree._Element,
    *,
    default_title: Optional[str] = None,
) -> etree._Element:
    if root is None:
        raise ValueError("root element is required")

    transform = _load_transform()
    params = {}
    if default_title is not None:
        params["default-title"] = etree.XSLT.strparam(default_title)

    result = transform(etree.ElementTree(root), **params)
    result_root = result.getroot()
    # Detach from the temporary result tree to avoid surprises when callers mutate
    # the returned element.
    return etree.fromstring(etree.tostring(result_root))


__all__ = ["transform_docbook_to_rittdoc"]
