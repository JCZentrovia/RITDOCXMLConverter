from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Tuple

import re

from lxml import etree


@dataclass(frozen=True)
class RittDocTransformResult:
    """Structured result produced by the DocBook→RITTDoc transform."""

    root: etree._Element
    processing_instructions: Tuple[Tuple[str, str], ...] = ()
    assets: Tuple[Tuple[str, Path], ...] = ()


@lru_cache(maxsize=1)
def _load_transform() -> etree.XSLT:
    xslt_path = Path(__file__).with_name("docbook_to_rittdoc.xsl")
    return etree.XSLT(etree.parse(str(xslt_path)))


_HREF_RE = re.compile(r"href\s*=\s*\"([^\"]+)\"")


def _gather_processing_instructions(root: etree._Element) -> Tuple[Tuple[str, str], ...]:
    entries = []
    node = root.getprevious()
    while node is not None:
        if isinstance(node, etree._ProcessingInstruction):
            entries.append((node.target, node.text or ""))
        node = node.getprevious()
    entries.reverse()
    return tuple(entries)


def _resolve_assets(pis: Iterable[Tuple[str, str]]) -> Tuple[Tuple[str, Path], ...]:
    assets = []
    base = Path(__file__).resolve().parent
    for target, data in pis:
        if target != "xml-stylesheet":
            continue
        match = _HREF_RE.search(data or "")
        if not match:
            continue
        href = match.group(1)
        candidate = base / href
        if candidate.exists():
            assets.append((href, candidate))
    return tuple(assets)


def transform_docbook_to_rittdoc(
    root: etree._Element,
    *,
    default_title: Optional[str] = None,
    stylesheet_href: Optional[str] = None,
) -> RittDocTransformResult:
    if root is None:
        raise ValueError("root element is required")

    transform = _load_transform()
    params = {}
    if default_title is not None:
        params["default-title"] = etree.XSLT.strparam(default_title)
    if stylesheet_href is not None:
        params["stylesheet-href"] = etree.XSLT.strparam(stylesheet_href)

    result = transform(etree.ElementTree(root), **params)
    raw_bytes = bytes(result)
    result_root = etree.fromstring(raw_bytes)
    pis = _gather_processing_instructions(result_root)
    assets = _resolve_assets(pis)
    return RittDocTransformResult(root=result_root, processing_instructions=pis, assets=assets)


__all__ = ["RittDocTransformResult", "transform_docbook_to_rittdoc"]
