from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_pack(pack: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(pack)
    normalized.setdefault("mode", "general")
    for article in normalized.get("selected_articles", []):
        article.setdefault("difficulty_score", 0)
        article.setdefault("difficulty_level", "")
    for index, task in enumerate(normalized.get("weekly_plan", []), start=1):
        task.setdefault("pack_id", normalized["pack_id"])
        task.setdefault("task_id", f"{normalized['pack_id']}:study:{index}")
        task.setdefault("estimated_minutes", 35 if task.get("task_type") == "deep_read" else 18)
        task.setdefault("difficulty_score", 0)
        task.setdefault("difficulty_level", "")
        task.setdefault("tags", [])
        for review in task.get("reviews", []):
            review.setdefault("pack_id", normalized["pack_id"])
            review.setdefault(
                "review_id",
                f"{normalized['pack_id']}:review:{task['article_id']}:{review['review_type']}",
            )
    return normalized
