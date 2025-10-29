from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


def classify_blocks(blocks: List[dict], threshold: float, abstain_label: str) -> List[dict]:
    """Return blocks with classifier labels.

    This stub classifier simply echoes existing labels with full confidence.
    An external model can replace this implementation; it must support abstention
    by returning the ``abstain_label`` when confidence falls below ``threshold``.
    """

    enriched = []
    for block in blocks:
        enriched.append(
            {
                **block,
                "classifier_label": block.get("label", "para"),
                "classifier_confidence": 1.0,
            }
        )
    logger.debug("Classifier processed %s blocks", len(enriched))
    return enriched
