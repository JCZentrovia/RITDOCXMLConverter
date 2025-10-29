from __future__ import annotations

import logging
from pathlib import Path

from ..common import run_cmd

logger = logging.getLogger(__name__)


def validate_dtd(xml_path: str, dtd_path: str, catalog: str) -> None:
    xml = Path(xml_path)
    if not xml.exists():
        raise FileNotFoundError(xml)
    env = {}
    if catalog:
        env["XML_CATALOG_FILES"] = str(Path(catalog).resolve())
    args = [
        "xmllint",
        "--noout",
        "--catalogs",
        "--valid",
        "--dtdvalid",
        str(dtd_path),
        str(xml),
    ]
    logger.info("Validating %s against %s", xml, dtd_path)
    run_cmd(args, env=env)
