from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .epub_parser import import_epub
from .models import Book, StudyPack
from .pack_utils import normalize_pack
from .reporting import build_daily_plan, build_progress_report
from .storage import ensure_dir, read_json, write_json
from .study_pack import build_study_pack
from .tracking import get_status_map


def import_book(epub_path: Path, library_root: Path) -> dict[str, Any]:
    book, articles = import_epub(str(epub_path))
    if articles:
        for article in articles:
            article.book_id = book.book_id
    book_dir = ensure_dir(library_root / book.book_id)
    write_json(book_dir / "book.json", book.to_dict())
    write_json(book_dir / "articles.json", [article.to_dict() for article in articles])
    return {
        "book_id": book.book_id,
        "title": book.title,
        "article_count": len(articles),
        "library_path": str(book_dir),
    }


def create_study_pack(
    *,
    book_id: str,
    library_root: Path,
    packs_root: Path,
    start_date: date,
    focus_topics: list[str],
    main_count: int,
    short_count: int,
    mode: str,
) -> dict[str, Any]:
    book_dir = library_root / book_id
    book = Book(**read_json(book_dir / "book.json"))
    articles = load_articles(book_dir / "articles.json")
    pack = build_study_pack(
        book=book,
        articles=articles,
        start_date=start_date,
        focus_topics=focus_topics,
        main_count=main_count,
        short_count=short_count,
        mode=mode,
    )
    pack_dir = ensure_dir(packs_root / pack.pack_id)
    write_json(pack_dir / "pack.json", pack.to_dict())
    return {
        "pack_id": pack.pack_id,
        "pack_path": str(pack_dir / "pack.json"),
        "selected_articles": [item["title"] for item in pack.selected_articles],
        "book_id": book.book_id,
    }


def load_articles(path: Path) -> list:
    from .models import Article

    return [Article(**item) for item in read_json(path)]


def load_packs(pack_root: Path) -> list[StudyPack]:
    if not pack_root.exists():
        return []
    packs: list[StudyPack] = []
    for pack_json in sorted(pack_root.glob("*/pack.json")):
        packs.append(StudyPack(**read_json(pack_json)))
    return packs


def load_pack(pack_root: Path, pack_id: str, tracker: Path | None = None) -> dict[str, Any]:
    pack_path = pack_root / pack_id / "pack.json"
    pack = normalize_pack(read_json(pack_path))
    status_map = get_status_map(tracker) if tracker else {}
    if status_map:
        for task in pack["weekly_plan"]:
            task.update(
                {
                    "status": status_map.get(task["task_id"], {}).get("status", "pending"),
                    "completed_at": status_map.get(task["task_id"], {}).get("completed_at", ""),
                    "note": status_map.get(task["task_id"], {}).get("note", ""),
                }
            )
            for review in task["reviews"]:
                review.update(
                    {
                        "status": status_map.get(review["review_id"], {}).get("status", "pending"),
                        "completed_at": status_map.get(review["review_id"], {}).get("completed_at", ""),
                        "note": status_map.get(review["review_id"], {}).get("note", ""),
                    }
                )
    return pack


def load_article_lookup(library_root: Path, book_id: str) -> dict[str, dict[str, Any]]:
    articles = read_json(library_root / book_id / "articles.json")
    return {item["article_id"]: item for item in articles}


def list_books(library_root: Path) -> list[dict[str, Any]]:
    books: list[dict[str, Any]] = []
    if not library_root.exists():
        return books
    for book_json in sorted(library_root.glob("*/book.json")):
        book = read_json(book_json)
        books.append(book)
    return sorted(books, key=lambda item: item.get("imported_at", ""), reverse=True)


def list_packs(packs_root: Path, tracker: Path | None = None) -> list[dict[str, Any]]:
    pack_items: list[dict[str, Any]] = []
    if not packs_root.exists():
        return pack_items
    for pack_json in sorted(packs_root.glob("*/pack.json")):
        pack = load_pack(packs_root, pack_json.parent.name, tracker)
        completed = sum(1 for task in pack["weekly_plan"] if task.get("status") == "completed")
        pack_items.append(
            {
                "pack_id": pack["pack_id"],
                "book_id": pack["book_id"],
                "start_date": pack["start_date"],
                "mode": pack.get("mode", "general"),
                "task_count": len(pack["weekly_plan"]),
                "completed_tasks": completed,
            }
        )
    return sorted(pack_items, key=lambda item: item["start_date"], reverse=True)


def get_today_plan(packs_root: Path, tracker: Path, target_date: date) -> dict[str, Any]:
    return build_daily_plan(load_packs(packs_root), target_date, get_status_map(tracker))


def get_progress_summary(packs_root: Path, tracker: Path) -> dict[str, Any]:
    return build_progress_report(load_packs(packs_root), get_status_map(tracker))
