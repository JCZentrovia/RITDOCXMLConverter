from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import click
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


@click.group()
@click.option("--config-dir", default="config", type=click.Path(file_okay=False, path_type=Path))
@click.option("--report-dir", default="out/reports", type=click.Path(file_okay=False, path_type=Path))
@click.pass_context
def cli(ctx: click.Context, config_dir: Path, report_dir: Path) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_dir"] = config_dir
    ctx.obj["report_dir"] = report_dir


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False))
@click.option("--publisher", required=True)
@click.option("--ocr-on-image-only", is_flag=True, default=False)
@click.option("--strict", is_flag=True, default=False)
@click.pass_context
def pdf(ctx: click.Context, input_path: str, out_path: str, publisher: str, ocr_on_image_only: bool, strict: bool) -> None:
    """Convert a PDF to DocBook XML."""

    metrics = convert_pdf(
        input_path,
        out_path,
        publisher,
        config_dir=str(ctx.obj["config_dir"]),
        ocr_on_image_only=ocr_on_image_only,
        strict=strict,
    )
    _write_reports(metrics, input_path, Path(ctx.obj["report_dir"]))
    if strict and metrics.get("mismatches"):
        logger.error("Extractor mismatches detected in strict mode: %s", metrics["mismatches"])
        sys.exit(1)
    click.echo(out_path)


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False))
@click.option("--publisher", required=True)
@click.option("--strict", is_flag=True, default=False)
@click.pass_context
def epub(ctx: click.Context, input_path: str, out_path: str, publisher: str, strict: bool) -> None:
    """Convert an EPUB to DocBook XML."""

    metrics = convert_epub(
        input_path,
        out_path,
        publisher,
        config_dir=str(ctx.obj["config_dir"]),
        strict=strict,
    )
    _write_reports(metrics, input_path, Path(ctx.obj["report_dir"]))
    click.echo(out_path)


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


@cli.command()
@click.option("--manifest", "manifest_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--parallel", default=1, show_default=True)
@click.option("--strict", is_flag=True, default=False)
@click.pass_context
def batch(ctx: click.Context, manifest_path: str, parallel: int, strict: bool) -> None:
    """Run batch conversions from a manifest."""

    if parallel > 1:
        logger.warning("Parallel processing not implemented; running sequentially.")

    jobs = _load_manifest(Path(manifest_path))
    success = True
    for job in jobs:
        job_type = job.get("type")
        try:
            if job_type == "pdf":
                convert_pdf(
                    job["input"],
                    job["out"],
                    job["publisher"],
                    config_dir=str(ctx.obj["config_dir"]),
                    ocr_on_image_only=job.get("ocr_on_image_only", "false").lower() == "true",
                    strict=strict,
                )
            elif job_type == "epub":
                convert_epub(
                    job["input"],
                    job["out"],
                    job["publisher"],
                    config_dir=str(ctx.obj["config_dir"]),
                    strict=strict,
                )
            else:
                raise ValueError(f"Unknown job type: {job_type}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed job %s", job)
            success = False
    if not success:
        sys.exit(1)


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--catalog", default="validation/catalog.xml", show_default=True)
@click.pass_context
def validate(ctx: click.Context, input_path: str, catalog: str) -> None:
    config_dir = Path(ctx.obj["config_dir"])
    default_mapping = json.loads((config_dir / "mapping.default.json").read_text(encoding="utf-8"))
    dtd_path = default_mapping.get("docbook", {}).get("dtd_system", "dtd/v1.1/docbookx.dtd")
    validate_dtd(input_path, dtd_path, catalog)
    click.echo("valid")


if __name__ == "__main__":
    cli()
