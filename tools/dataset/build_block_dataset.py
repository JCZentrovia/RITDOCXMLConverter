"""CLI for building the block-level layout dataset used by the classifier."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.structure.dataset_builder import (
    build_dataset,
    save_dataset_jsonl,
    save_summary,
    summarise_dataset,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "conversion_examples",
        type=Path,
        help="Path to the ConversionExamples directory",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="Directory containing mapping.default.json",
    )
    parser.add_argument(
        "--publisher",
        type=str,
        default=None,
        help="Optional publisher override when loading configuration",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of conversion examples processed (for smoke tests)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/block_dataset.jsonl"),
        help="Path for the JSONL dataset output",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("datasets/block_dataset.summary.json"),
        help="Path for the dataset summary metadata",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.84,
        help="Minimum SequenceMatcher ratio when aligning DocBook and PDF blocks",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if not args.conversion_examples.exists():
        logger.error("Conversion examples not found: %s", args.conversion_examples)
        return 2

    examples = build_dataset(
        args.conversion_examples,
        config_dir=args.config_dir,
        publisher=args.publisher,
        fuzzy_threshold=args.fuzzy_threshold,
        limit=args.limit,
    )
    save_dataset_jsonl(examples, args.output)
    save_summary(summarise_dataset(examples), args.summary)
    logger.info("Dataset build completed")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
