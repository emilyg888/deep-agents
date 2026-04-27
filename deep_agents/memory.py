from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from .models import Paper, PaperPool


def _normalize_theme(theme: str) -> str:
    return " ".join(theme.lower().split())


def _normalize_title(title: str) -> str:
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in title).split()
    )


@dataclass
class ThemeMemoryEntry:
    theme: str
    last_used: str


class PaperMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {str(item) for item in payload}

    def _save(self, fingerprints: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(fingerprints), indent=2),
            encoding="utf-8",
        )

    def build_paper_pool(
        self,
        papers: list[Paper],
        *,
        similarity_threshold: float = 0.84,
        ignore_memory: bool = False,
    ) -> PaperPool:
        seen_memory = set() if ignore_memory else self._load()
        seen_batch: set[str] = set()
        exact_dropped: list[Paper] = []
        unique: list[Paper] = []

        for paper in papers:
            fingerprint = paper.fingerprint
            if fingerprint in seen_memory or fingerprint in seen_batch:
                exact_dropped.append(paper)
                continue
            seen_batch.add(fingerprint)
            unique.append(paper)

        prioritized: list[Paper] = []
        similarity_deprioritized: list[Paper] = []
        for paper in unique:
            normalized_title = _normalize_title(paper.title)
            similar_to_existing = any(
                SequenceMatcher(
                    None,
                    normalized_title,
                    _normalize_title(existing.title),
                ).ratio()
                >= similarity_threshold
                for existing in prioritized
            )
            if similar_to_existing:
                similarity_deprioritized.append(paper)
            else:
                prioritized.append(paper)

        deduped = prioritized + similarity_deprioritized
        return PaperPool(
            fetched=list(papers),
            deduped=deduped,
            exact_dropped=exact_dropped,
            similarity_deprioritized=similarity_deprioritized,
        )

    def remember(self, papers: list[Paper]) -> None:
        seen = self._load()
        seen.update(paper.fingerprint for paper in papers)
        self._save(seen)


class ThemeMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[ThemeMemoryEntry]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            ThemeMemoryEntry(theme=item["theme"], last_used=item["last_used"])
            for item in payload
        ]

    def _save(self, entries: list[ThemeMemoryEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {"theme": entry.theme, "last_used": entry.last_used}
            for entry in entries
        ]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def recent_themes(self, limit: int = 3) -> list[str]:
        entries = self._load()
        recent = entries[-limit:]
        return [_normalize_theme(entry.theme) for entry in recent]

    def was_used_recently(self, theme: str, limit: int = 3) -> bool:
        return _normalize_theme(theme) in self.recent_themes(limit=limit)

    def remember(self, theme: str, used_on: date) -> None:
        entries = self._load()
        entries.append(ThemeMemoryEntry(theme=theme, last_used=used_on.isoformat()))
        self._save(entries)
