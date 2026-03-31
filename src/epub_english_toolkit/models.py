from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Article:
    article_id: str
    book_id: str
    title: str
    section: str
    order: int
    href: str
    word_count: int
    reading_minutes: int
    paragraphs: list[str]
    tags: list[str] = field(default_factory=list)
    excerpt: str = ""
    difficulty_score: int = 0
    difficulty_level: str = ""
    difficulty_metrics: dict[str, float | int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Book:
    book_id: str
    title: str
    source_path: str
    language: str
    publisher: str
    published_at: str
    imported_at: str
    description: str
    sections: list[str]
    article_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StudyPack:
    pack_id: str
    book_id: str
    created_at: str
    start_date: str
    focus_topics: list[str]
    selected_articles: list[dict[str, Any]]
    weekly_plan: list[dict[str, Any]]
    mode: str = "general"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
