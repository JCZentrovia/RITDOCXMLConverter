from __future__ import annotations

import argparse
import csv
import html
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set

from pipeline.validators.dtd_validator import validate_dtd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


_DEPENDENCY_HINTS = {
    "lxml": "Install the lxml wheels via `pip install -r tools/requirements.txt`.",
    "pdfminer": "Install pdfminer.six via `pip install -r tools/requirements.txt`.",
    "openai": "Install the OpenAI SDK via `pip install -r tools/requirements.txt`.",
    "docx": "Install python-docx via `pip install -r tools/requirements.txt`.",
    "dotenv": "Install python-dotenv via `pip install -r tools/requirements.txt`.",
}

def _module_available(module: str) -> bool:
    """Return True if *module* can be imported without executing it."""

    if importlib.util.find_spec(module):
        return True
    if "." in module:
        root = module.split(".")[0]
        if importlib.util.find_spec(root):
            return True
    return False

def _module_available(module: str) -> bool:
    """Return True if *module* can be imported without executing it."""

    if importlib.util.find_spec(module):
        return True
    if "." in module:
        root = module.split(".")[0]
        if importlib.util.find_spec(root):
            return True
    return False


def _verify_runtime_dependencies(modules: Iterable[str]) -> None:
    missing: List[str] = []
    for module in modules:
        if not _module_available(module):
            missing.append(module)
    if not missing:
        return

    seen: Set[str] = set()
    bullet_points: List[str] = []
    for name in missing:
        root = name.split(".")[0]
        if root in seen:
            continue
        seen.add(root)
        hint = _DEPENDENCY_HINTS.get(root, "Install dependencies with `pip install -r tools/requirements.txt`.")
        bullet_points.append(f"  - {root}: {hint}")

    message = (
        "Missing required Python packages for this command:\n"
        + "\n".join(bullet_points)
        + "\nInstall the packages and retry."
    )
    raise SystemExit(message)


def _ensure_report_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_reports(metrics: Dict, source: str, report_dir: Path) -> None:
    report_dir = _ensure_report_dir(report_dir)
    stem = Path(source).stem
    csv_path = report_dir / f"{stem}_qa.csv"
    html_path = report_dir / f"{stem}_qa.html"

    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                "file",
                "page",
                "chars_in",
                "chars_out",
                "words_in",
                "words_out",
                "checksum_in",
                "checksum_out",
                "flags",
                "has_ocr",
                "status",
            ]
        )
        for page in metrics.get("pages", []):
            flags = page.get("flags", [])
            discrepancy = bool(flags)
            writer.writerow(
                [
                    source,
                    page["page"],
                    page["chars_in"],
                    page["chars_out"],
                    page["words_in"],
                    page["words_out"],
                    page["checksum_in"],
                    page["checksum_out"],
                    ";".join(flags),
                    "yes" if page.get("has_ocr") else "no",
                    "discrepancy" if discrepancy else "ok",
                ]
            )

    rows = []
    for page in metrics.get("pages", []):
        flags = page.get("flags", [])
        discrepancy = bool(flags)
        row_class = " class=\"has-discrepancy\"" if discrepancy else ""
        rows.append(
            f"            <tr{row_class}>\n"
            f"                <td>{html.escape(str(page['page']))}</td>\n"
            f"                <td>{html.escape(str(page['chars_in']))}</td>\n"
            f"                <td>{html.escape(str(page['chars_out']))}</td>\n"
            f"                <td>{html.escape(str(page['words_in']))}</td>\n"
            f"                <td>{html.escape(str(page['words_out']))}</td>\n"
            f"                <td>{html.escape(str(page['checksum_in']))}</td>\n"
            f"                <td>{html.escape(str(page['checksum_out']))}</td>\n"
            f"                <td>{html.escape(';'.join(flags))}</td>\n"
            f"                <td>{'yes' if page.get('has_ocr') else 'no'}</td>\n"
            "            </tr>"
        )

    report_html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "  <head>\n"
        "    <meta charset=\"utf-8\">\n"
        f"    <title>{html.escape(source)} QA Report</title>\n"
        "    <style>table {border-collapse: collapse;} th, td {border: 1px solid #999; padding: 0.3em; text-align: left;} th {background: #eee;} .has-discrepancy {background: #fde8e8;}</style>\n"
        "  </head>\n"
        "  <body>\n"
        f"    <h1>QA Report for {html.escape(source)}</h1>\n"
        "    <table>\n"
        "      <thead>\n"
        "        <tr>\n"
        "          <th>Page</th>\n"
        "          <th>Chars In</th>\n"
        "          <th>Chars Out</th>\n"
        "          <th>Words In</th>\n"
        "          <th>Words Out</th>\n"
        "          <th>Checksum In</th>\n"
        "          <th>Checksum Out</th>\n"
        "          <th>Flags</th>\n"
        "          <th>Has OCR</th>\n"
        "        </tr>\n"
        "      </thead>\n"
        "      <tbody>\n"
        + ("\n".join(rows) if rows else "        <tr><td colspan=\"9\">No pages processed</td></tr>")
        + "\n      </tbody>\n"
        "    </table>\n"
        "  </body>\n"
        "</html>\n"
    )
    html_path.write_text(report_html, encoding="utf-8")

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RIT DocBook converter CLI")
    parser.add_argument("--config-dir", default=Path("config"), type=_directory)
    parser.add_argument("--report-dir", default=Path("out/reports"), type=_directory)

def _existing_file(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"{path} is not an existing file")
    return path


def _directory(path_str: str) -> Path:
    path = Path(path_str)
    if path.exists() and not path.is_dir():
        raise argparse.ArgumentTypeError(f"{path} is not a directory")
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RIT DocBook converter CLI")
    parser.add_argument("--config-dir", default=Path("config"), type=_directory)
    parser.add_argument("--report-dir", default=Path("out/reports"), type=_directory)

    subparsers = parser.add_subparsers(dest="command", required=True)

    pdf_parser = subparsers.add_parser("pdf", help="Convert a PDF to DocBook XML")
    pdf_parser.add_argument("--input", dest="input_path", required=True, type=_existing_file)
    pdf_parser.add_argument("--out", dest="out_path", required=True)
    pdf_parser.add_argument("--publisher", required=True)
    pdf_parser.add_argument("--ocr-on-image-only", action="store_true")
    pdf_parser.add_argument("--strict", action="store_true")

    epub_parser = subparsers.add_parser("epub", help="Convert an EPUB to DocBook XML")
    epub_parser.add_argument("--input", dest="input_path", required=True, type=_existing_file)
    epub_parser.add_argument("--out", dest="out_path", required=True)
    epub_parser.add_argument("--publisher", required=True)
    epub_parser.add_argument("--strict", action="store_true")

    batch_parser = subparsers.add_parser("batch", help="Run batch conversions from a manifest")
    batch_parser.add_argument("--manifest", dest="manifest_path", required=True, type=_existing_file)
    batch_parser.add_argument("--parallel", type=int, default=1)
    batch_parser.add_argument("--strict", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate a DocBook XML file")
    validate_parser.add_argument("--input", dest="input_path", required=True, type=_existing_file)
    validate_parser.add_argument("--catalog", default="validation/catalog.xml")

    return parser


def _load_manifest(manifest_path: Path) -> List[Dict[str, str]]:
    if manifest_path.suffix.lower() == ".json":
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("jobs", [])
        return data
    rows: List[Dict[str, str]] = []
    with manifest_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def _handle_pdf(args: argparse.Namespace, config_dir: Path, report_dir: Path) -> int:
    _verify_runtime_dependencies({"lxml.etree", "pdfminer"})
    from pipeline.pdf_pipeline import convert_pdf

    metrics = convert_pdf(
        str(args.input_path),
        args.out_path,
        args.publisher,
        config_dir=str(config_dir),
        ocr_on_image_only=args.ocr_on_image_only,
        strict=args.strict,
    )
    _write_reports(metrics, str(args.input_path), report_dir)
    if args.strict and metrics.get("mismatches"):
        logger.error("Extractor mismatches detected in strict mode: %s", metrics["mismatches"])
        return 1
    print(metrics.get("output_path", args.out_path))
    return 0


def _handle_epub(args: argparse.Namespace, config_dir: Path, report_dir: Path) -> int:
    _verify_runtime_dependencies({"lxml.etree"})
    from pipeline.epub_pipeline import convert_epub

    metrics = convert_epub(
        str(args.input_path),
        args.out_path,
        args.publisher,
        config_dir=str(config_dir),
        strict=args.strict,
    )
    _write_reports(metrics, str(args.input_path), report_dir)
    print(metrics.get("output_path", args.out_path))
    return 0


def _handle_batch(args: argparse.Namespace, config_dir: Path) -> int:
    if args.parallel > 1:
        logger.warning("Parallel processing not implemented; running sequentially.")

    jobs = _load_manifest(args.manifest_path)

    required_modules: Set[str] = set()
    needs_pdf = False
    needs_epub = False
    for job in jobs:
        job_type = job.get("type")
        if job_type == "pdf":
            required_modules.update({"lxml.etree", "pdfminer"})
            needs_pdf = True
        elif job_type == "epub":
            required_modules.add("lxml.etree")
            needs_epub = True

    if required_modules:
        _verify_runtime_dependencies(required_modules)

    pdf_converter: Optional[Callable[..., Dict]] = None
    epub_converter: Optional[Callable[..., Dict]] = None
    if needs_pdf:
        from pipeline.pdf_pipeline import convert_pdf as _convert_pdf

        pdf_converter = _convert_pdf
    if needs_epub:
        from pipeline.epub_pipeline import convert_epub as _convert_epub

        epub_converter = _convert_epub

    success = True
    for job in jobs:
        job_type = job.get("type")
        try:
            if job_type == "pdf":
                assert pdf_converter is not None
                pdf_converter(
                    job["input"],
                    job["out"],
                    job["publisher"],
                    config_dir=str(config_dir),
                    ocr_on_image_only=job.get("ocr_on_image_only", "false").lower() == "true",
                    strict=args.strict,
                )
            elif job_type == "epub":
                assert epub_converter is not None
                epub_converter(
                    job["input"],
                    job["out"],
                    job["publisher"],
                    config_dir=str(config_dir),
                    strict=args.strict,
                )
            else:
                raise ValueError(f"Unknown job type: {job_type}")
        except Exception:  # noqa: BLE001
            logger.exception("Failed job %s", job)
            success = False
    return 0 if success else 1


def _handle_validate(args: argparse.Namespace, config_dir: Path) -> int:
    default_mapping = json.loads((config_dir / "mapping.default.json").read_text(encoding="utf-8"))
    dtd_path = default_mapping.get("docbook", {}).get(
        "dtd_system", "RITTDOCdtd/v1.1/RittDocBook.dtd"
    )
    validate_dtd(str(args.input_path), dtd_path, args.catalog)
    print("valid")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config_dir = args.config_dir
    report_dir = args.report_dir

    if args.command == "pdf":
        return _handle_pdf(args, config_dir, report_dir)
    if args.command == "epub":
        return _handle_epub(args, config_dir, report_dir)
    if args.command == "batch":
        return _handle_batch(args, config_dir)
    if args.command == "validate":
        return _handle_validate(args, config_dir)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
