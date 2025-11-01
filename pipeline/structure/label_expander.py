"""Expand heuristic labels into the rich RittDocBook taxonomy."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .label_taxonomy import (
    DEFAULT_TAXONOMY_PATH,
    LabelDefinition,
    LabelTaxonomy,
    load_label_taxonomy,
)


@dataclass
class ContainerState:
    name: str
    level: int


class HeadingLevelTracker:
    """Determine section depth based on observed heading font sizes."""

    def __init__(self, body_font: float) -> None:
        self.body_font = body_font
        self._levels: List[float] = []

    def level_for(self, font_size: Optional[float]) -> int:
        if not font_size:
            return 1
        size = float(font_size)
        if self.body_font and size <= self.body_font * 1.05:
            return max(len(self._levels), 1) or 1
        tolerance = max(0.75, size * 0.15)
        for idx, existing in enumerate(self._levels):
            if abs(existing - size) <= tolerance:
                return idx + 1
        self._levels.append(size)
        self._levels.sort(reverse=True)
        return self._levels.index(size) + 1


class LabelExpander:
    """Expand heuristic/classifier labels into the richer taxonomy."""

    def __init__(
        self,
        taxonomy: Optional[LabelTaxonomy] = None,
        *,
        taxonomy_path: Optional[Union[Path, str]] = None,
    ) -> None:
        if taxonomy is not None:
            self.taxonomy = taxonomy
        else:
            path: Path
            if taxonomy_path is None:
                path = DEFAULT_TAXONOMY_PATH
            elif isinstance(taxonomy_path, Path):
                path = taxonomy_path
            else:
                path = Path(taxonomy_path)
            self.taxonomy = load_label_taxonomy(path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def expand(self, blocks: Sequence[dict]) -> List[dict]:
        body_font = self._estimate_body_font(blocks)
        tracker = HeadingLevelTracker(body_font)
        stack: List[ContainerState] = [
            ContainerState("book", self.taxonomy.container_level("book")),
        ]
        in_main_matter = False
        in_back_matter = False
        last_media: Optional[str] = None

        expanded: List[dict] = []
        for block in blocks:
            base_label = (block.get("classifier_label") or block.get("label") or "para").lower()
            container, type_name, in_main_matter, in_back_matter = self._map_block(
                block,
                base_label,
                stack,
                tracker,
                in_main_matter,
                in_back_matter,
                last_media,
            )
            if base_label in {"figure", "table"}:
                last_media = base_label
            elif base_label != "caption":
                last_media = None
            resolved_label, definition = self._resolve_label(container, type_name)
            enriched = dict(block)
            enriched["rittdoc_container"] = container
            enriched["rittdoc_type"] = type_name
            enriched["rittdoc_label"] = resolved_label
            if definition:
                enriched["rittdoc_role"] = definition.role
                enriched["rittdoc_starts_container"] = definition.starts_container
            expanded.append(enriched)
        return expanded

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _estimate_body_font(blocks: Sequence[dict]) -> float:
        fonts = [
            float(block.get("font_size", 0) or 0)
            for block in blocks
            if (
                (block.get("classifier_label") or block.get("label") or "").lower()
                == "para"
            )
            and block.get("font_size")
        ]
        return float(median(fonts)) if fonts else 0.0

    def _map_block(
        self,
        block: dict,
        base_label: str,
        stack: List[ContainerState],
        tracker: HeadingLevelTracker,
        in_main_matter: bool,
        in_back_matter: bool,
        last_media: Optional[str],
    ) -> Tuple[str, str, bool, bool]:
        text = (block.get("text") or "").strip()
        font_size = block.get("font_size")

        if base_label == "book_title" and text:
            stack[:] = [ContainerState("book", self.taxonomy.container_level("book"))]
            return "book", "title", False, False

        if base_label == "toc":
            container = self._ensure_container(stack, "frontmatter")
            return container.name, "toc.entry", in_main_matter, in_back_matter

        if base_label == "chapter":
            role = (block.get("chapter_role") or "").lower()
            if role == "index":
                state = self._ensure_container(stack, "index")
                return state.name, "title", True, True
            state = self._ensure_container(stack, "chapter")
            return state.name, "title", True, in_back_matter

        if base_label == "section":
            if not in_main_matter:
                state = self._ensure_container(stack, "preface")
                return state.name, "title", in_main_matter, in_back_matter
            level = tracker.level_for(font_size)
            level = max(1, min(level, 3))
            state = self._ensure_container(stack, f"sect{level}")
            return state.name, "title", in_main_matter, in_back_matter

        if base_label == "figure":
            state = stack[-1]
            return state.name, "figure", in_main_matter, in_back_matter

        if base_label == "table":
            state = stack[-1]
            return state.name, "table", in_main_matter, in_back_matter

        if base_label == "caption":
            state = stack[-1]
            if last_media == "table":
                return state.name, "table.caption", in_main_matter, in_back_matter
            return state.name, "figure.caption", in_main_matter, in_back_matter

        if base_label == "list_item":
            list_type = (block.get("list_type") or "itemized").lower()
            suffix = "orderedlist.item" if list_type == "ordered" else "itemizedlist.item"
            state = stack[-1]
            return state.name, suffix, in_main_matter, in_back_matter

        if base_label == "footnote":
            state = self._ensure_container(stack, "footnote")
            return state.name, "para", in_main_matter, in_back_matter

        if base_label == "para":
            state = stack[-1]
            if state.name == "index":
                return state.name, "entry", in_main_matter, in_back_matter
            return state.name, "para", in_main_matter, in_back_matter

        # Default fallback
        state = stack[-1]
        return state.name, base_label or "para", in_main_matter, in_back_matter

    def _ensure_container(self, stack: List[ContainerState], name: str) -> ContainerState:
        definition = self.taxonomy.get_container(name)
        if not definition:
            return stack[-1]
        parent_name = definition.parent or stack[0].name
        # Ensure parent exists
        if parent_name and parent_name != name:
            parent_state = next((state for state in stack if state.name == parent_name), None)
            if parent_state is None:
                parent_state = self._ensure_container(stack, parent_name)
        # Pop containers at same or deeper level
        while stack and stack[-1].level >= definition.level:
            stack.pop()
        new_state = ContainerState(name, definition.level)
        stack.append(new_state)
        return new_state

    def _resolve_label(self, container: str, type_name: str) -> Tuple[str, Optional[LabelDefinition]]:
        candidates = self._candidate_labels(container, type_name)
        for candidate in candidates:
            definition = self.taxonomy.get_label(candidate)
            if definition:
                return candidate, definition
        # As a last resort, return an arbitrary label to avoid crashes
        first_label = next(iter(self.taxonomy.labels.values()))
        return first_label.name, first_label

    def _candidate_labels(self, container: str, type_name: str) -> Iterable[str]:
        if container and type_name:
            yield f"{container}.{type_name}"
        if container:
            yield f"{container}.para"
        yield "chapter.para"
        yield "book.para"
