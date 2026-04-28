from __future__ import annotations

import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .models import EvaluationResult, Paper, PaperPool, PositionStrengthResult, ThemeCandidate


def _normalize_theme(theme: str) -> str:
    return " ".join(theme.lower().split())


def _normalize_title(title: str) -> str:
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in title).split()
    )


def _subtract_months(value: date, months: int) -> date:
    month_index = value.month - 1 - months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


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

    def recent_themes(
        self,
        *,
        as_of: date | None = None,
        months: int = 6,
    ) -> list[str]:
        reference_date = as_of or date.today()
        cutoff = _subtract_months(reference_date, months)
        entries = self._load()
        recent = [
            entry
            for entry in entries
            if date.fromisoformat(entry.last_used) >= cutoff
        ]
        return [_normalize_theme(entry.theme) for entry in recent]

    def was_used_recently(
        self,
        theme: str,
        *,
        as_of: date | None = None,
        months: int = 6,
    ) -> bool:
        return _normalize_theme(theme) in self.recent_themes(
            as_of=as_of,
            months=months,
        )

    def remember(self, theme: str, used_on: date) -> None:
        entries = self._load()
        entries.append(ThemeMemoryEntry(theme=theme, last_used=used_on.isoformat()))
        self._save(entries)


class ReasoningMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def _save(self, entries: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def remember(
        self,
        *,
        used_on: date,
        selected_theme: ThemeCandidate,
        rejected_themes: list[ThemeCandidate],
        evaluation: EvaluationResult,
        position_strength: PositionStrengthResult,
        storage_path: str,
        run_log_path: str,
    ) -> None:
        entries = self._load()
        candidate_themes = [
            {
                **selected_theme.as_dict(),
                "status": "selected",
            },
            *[
                {
                    **candidate.as_dict(),
                    "status": "rejected",
                }
                for candidate in rejected_themes
            ],
        ]
        entries.append(
            {
                "used_on": used_on.isoformat(),
                "selected_theme": selected_theme.theme,
                "candidate_themes": candidate_themes,
                "position_strength": position_strength.as_dict(),
                "evaluation": evaluation.as_dict(),
                "storage_path": storage_path,
                "run_log_path": run_log_path,
            }
        )
        self._save(entries)
