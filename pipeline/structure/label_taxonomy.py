"""Utilities for working with the expanded DocBook label taxonomy."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import json

DEFAULT_TAXONOMY_PATH = Path("config/labels.expanded.json")


@dataclass(frozen=True)
class ContainerDefinition:
    """Definition of a logical container in the DocBook hierarchy."""

    name: str
    element: str
    level: int
    parent: Optional[str] = None
    singleton: bool = False


@dataclass(frozen=True)
class LabelDefinition:
    """Definition for a concrete label in the taxonomy."""

    name: str
    container: str
    element: str
    description: str = ""
    role: Optional[str] = None
    starts_container: bool = False

    @property
    def type_name(self) -> str:
        parts = self.name.split(".", 1)
        return parts[1] if len(parts) == 2 else parts[0]


class LabelTaxonomy:
    """In-memory representation of the expanded label taxonomy."""

    def __init__(
        self,
        containers: Iterable[ContainerDefinition],
        labels: Iterable[LabelDefinition],
    ) -> None:
        container_map: Dict[str, ContainerDefinition] = {}
        for container in containers:
            container_map[container.name] = container
        label_map: Dict[str, LabelDefinition] = {}
        for label in labels:
            label_map[label.name] = label
        self._containers = container_map
        self._labels = label_map
        self._labels_by_container: Dict[str, Dict[str, LabelDefinition]] = {}
        for label in label_map.values():
            self._labels_by_container.setdefault(label.container, {})[label.name] = label

    def get_label(self, name: str) -> Optional[LabelDefinition]:
        return self._labels.get(name)

    def has_label(self, name: str) -> bool:
        return name in self._labels

    def labels_for_container(self, container: str) -> Dict[str, LabelDefinition]:
        return self._labels_by_container.get(container, {})

    def get_container(self, name: str) -> Optional[ContainerDefinition]:
        return self._containers.get(name)

    def container_level(self, name: str) -> int:
        container = self.get_container(name)
        if not container:
            return 0
        return container.level

    @property
    def containers(self) -> Dict[str, ContainerDefinition]:
        return dict(self._containers)

    @property
    def labels(self) -> Dict[str, LabelDefinition]:
        return dict(self._labels)


def _load_container(defn: dict) -> ContainerDefinition:
    return ContainerDefinition(
        name=str(defn.get("name")),
        element=str(defn.get("element")),
        level=int(defn.get("level", 0)),
        parent=defn.get("parent"),
        singleton=bool(defn.get("singleton", False)),
    )


def _load_label(defn: dict) -> LabelDefinition:
    return LabelDefinition(
        name=str(defn.get("name")),
        container=str(defn.get("container")),
        element=str(defn.get("element")),
        description=str(defn.get("description", "")),
        role=defn.get("role"),
        starts_container=bool(defn.get("starts_container", False)),
    )


def load_label_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> LabelTaxonomy:
    """Load the label taxonomy from ``path``."""

    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    containers = [_load_container(item) for item in data.get("containers", [])]
    labels = [_load_label(item) for item in data.get("labels", [])]
    if not labels:
        raise ValueError("Expanded label taxonomy must define at least one label")
    return LabelTaxonomy(containers, labels)
