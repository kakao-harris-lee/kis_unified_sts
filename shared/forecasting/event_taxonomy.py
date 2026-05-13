"""Event taxonomy loader and rule-based matcher."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TaxonomyEntry:
    key: str
    impact_score: int
    aliases: tuple[str, ...]
    description: str = ""


class EventTaxonomy:
    """Rule-based event classifier with alias matching."""

    def __init__(self, events: list[TaxonomyEntry], unknown_match_score: int = 40):
        self.events = events
        self.unknown_match_score = unknown_match_score
        # Pre-lowercase aliases for fast matching
        self._alias_index: list[tuple[str, TaxonomyEntry]] = []
        for event in events:
            for alias in event.aliases:
                self._alias_index.append((alias.lower(), event))

    @classmethod
    def load(cls, yaml_path: Path) -> EventTaxonomy:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        events: list[TaxonomyEntry] = []
        for item in data.get("events", []):
            events.append(
                TaxonomyEntry(
                    key=item["key"],
                    impact_score=int(item["impact_score"]),
                    aliases=tuple(item.get("aliases", [])),
                    description=item.get("description", ""),
                )
            )
        unknown = int(data.get("unknown_match_score", 40))
        return cls(events, unknown_match_score=unknown)

    def match(self, text: str) -> TaxonomyEntry | None:
        """Return the first taxonomy entry whose alias appears in `text`.

        Match is case-insensitive substring. Returns None when no alias matches.
        """
        lowered = text.lower()
        for alias, entry in self._alias_index:
            if alias in lowered:
                return entry
        return None
