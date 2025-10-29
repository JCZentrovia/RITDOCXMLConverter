from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline.epub_pipeline import convert_epub
from pipeline.pdf_pipeline import convert_pdf
from pipeline.validators.dtd_validator import validate_dtd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


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
            ]
        )
        for page in metrics.get("pages", []):
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
                    ";".join(page.get("flags", [])),
                    "yes" if page.get("has_ocr") else "no",
                ]
            )

    env = Environment(
        loader=FileSystemLoader("reports/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("qa_report.html.j2")
    files = [
        {
            "name": source,
            "pages": [
                {
                    "number": page["page"],
                    "chars_in": page["chars_in"],
                    "chars_out": page["chars_out"],
                    "words_in": page["words_in"],
                    "words_out": page["words_out"],
                    "checksum_in": page["checksum_in"],
                    "checksum_out": page["checksum_out"],
                    "flags": page.get("flags", []),
                    "mismatch": bool(page.get("flags")),
                }
                for page in metrics.get("pages", [])
            ],
        }
    ]
    html_path.write_text(template.render(files=files), encoding="utf-8")


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


    batch_parser = subparsers.add_parser("batch", help="Run batch conversions from a manifest")
    batch_parser.add_argument("--manifest", dest="manifest_path", required=True, type=_existing_file)
    batch_parser.add_argument("--parallel", type=int, default=1)
    batch_parser.add_argument("--strict", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate a DocBook XML file")
    validate_parser.add_argument("--input", dest="input_path", required=True, type=_existing_file)
    validate_parser.add_argument("--catalog", default="validation/catalog.xml")

    return parser


def _handle_pdf(args: argparse.Namespace, config_dir: Path, report_dir: Path) -> int:
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
    success = True
    for job in jobs:
        job_type = job.get("type")
        try:
            if job_type == "pdf":
                convert_pdf(
                    job["input"],
                    job["out"],
                    job["publisher"],
                    config_dir=str(config_dir),
                    ocr_on_image_only=job.get("ocr_on_image_only", "false").lower() == "true",
                    strict=args.strict,
                )
            elif job_type == "epub":
                convert_epub(
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
    dtd_path = default_mapping.get("docbook", {}).get("dtd_system", "dtd/v1.1/docbookx.dtd")
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
