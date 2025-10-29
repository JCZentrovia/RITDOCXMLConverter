from __future__ import annotations

import logging
from pathlib import Path

from ..common import run_cmd


def _project_root() -> Path:
    """Return the repository root irrespective of the working directory."""

    return Path(__file__).resolve().parents[2]


def resolve_dtd_path(dtd_path: str) -> Path:
    """Resolve the configured DTD path to a concrete location on disk.

    The pipelines embed the configured system identifier directly into the
    generated XML so that downstream consumers see the canonical
    ``RITTDOCdtd`` path.  When validating, however, we need to provide
    ``xmllint`` with an absolute file location.  This helper first honours an
    explicitly absolute configuration value and otherwise resolves relative
    paths against the project root so that running the CLI from any directory
    continues to work.
    """

    configured = Path(dtd_path)
    if configured.is_absolute():
        return configured

    candidate = _project_root() / configured
    if candidate.exists():
        return candidate

    # Fall back to the caller-provided relative path; ``xmllint`` will perform
    # its own resolution relative to the current working directory.
    return configured


def resolve_catalog_path(catalog_path: str) -> Path:
    """Resolve the XML catalog path similarly to :func:`resolve_dtd_path`."""

    configured = Path(catalog_path)
    if configured.is_absolute():
        return configured

    candidate = _project_root() / configured
    if candidate.exists():
        return candidate

    return configured

logger = logging.getLogger(__name__)


def validate_dtd(xml_path: str, dtd_path: str, catalog: str) -> None:
    xml = Path(xml_path)
    if not xml.exists():
        raise FileNotFoundError(xml)
    env = {}
    resolved_catalog: Path | None = None
    if catalog:
        resolved_catalog = resolve_catalog_path(catalog).resolve()
        env["XML_CATALOG_FILES"] = str(resolved_catalog)
    resolved_dtd = resolve_dtd_path(dtd_path)

    args = [
        "xmllint",
        "--noout",
        "--valid",
        "--dtdvalid",
        str(resolved_dtd),
    ]
    if resolved_catalog is not None:
        args.extend(["--catalog", str(resolved_catalog)])
    args.append(str(xml))
    logger.info("Validating %s against %s", xml, resolved_dtd)
    run_cmd(args, env=env)
