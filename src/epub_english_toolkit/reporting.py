from __future__ import annotations

from datetime import date
from typing import Any

from .models import StudyPack
from .pack_utils import normalize_pack
from .study_pack import collect_due_reviews
from .tracking import annotate_status


def build_daily_plan(packs: list[StudyPack], target_date: date, status_map: dict[str, Any] | None = None) -> dict[str, Any]:
    status_map = status_map or {}
    due_tasks: list[dict[str, Any]] = []
    due_reviews: list[dict[str, Any]] = []

    for pack in packs:
        normalized_pack = normalize_pack(pack.to_dict())
        for task in normalized_pack["weekly_plan"]:
            if task["date"] == target_date.isoformat():
                task_status = annotate_status(task["task_id"], status_map)
                task.update(task_status)
                due_tasks.append(task)
        reviews = collect_due_reviews(StudyPack(**normalized_pack), target_date)
        for review in reviews:
            review.update(annotate_status(review["review_id"], status_map))
            due_reviews.append(review)

    return {
        "date": target_date.isoformat(),
        "study_tasks": due_tasks,
        "review_tasks": due_reviews,
        "totals": {
            "study_tasks": len(due_tasks),
            "review_tasks": len(due_reviews),
            "completed_study_tasks": sum(1 for item in due_tasks if item.get("status") == "completed"),
            "completed_review_tasks": sum(1 for item in due_reviews if item.get("status") == "completed"),
        },
    }


def build_progress_report(packs: list[StudyPack], status_map: dict[str, Any] | None = None) -> dict[str, Any]:
    status_map = status_map or {}
    study_tasks = 0
    review_tasks = 0
    speaking_minutes = 0
    writing_tasks = 0
    completed_study = 0
    completed_review = 0
    for pack in packs:
        normalized_pack = normalize_pack(pack.to_dict())
        study_tasks += len(normalized_pack["weekly_plan"])
        for task in normalized_pack["weekly_plan"]:
            review_tasks += len(task["reviews"])
            speaking_minutes += 3 if task["task_type"] == "deep_read" else 1
            writing_tasks += 1
            if annotate_status(task["task_id"], status_map)["status"] == "completed":
                completed_study += 1
            for review in task["reviews"]:
                if annotate_status(review["review_id"], status_map)["status"] == "completed":
                    completed_review += 1

    return {
        "packs": len(packs),
        "study_tasks": study_tasks,
        "review_tasks": review_tasks,
        "completed_study_tasks": completed_study,
        "completed_review_tasks": completed_review,
        "study_completion_rate": round(completed_study / study_tasks, 3) if study_tasks else 0,
        "review_completion_rate": round(completed_review / review_tasks, 3) if review_tasks else 0,
        "estimated_speaking_minutes": speaking_minutes,
        "writing_tasks": writing_tasks,
    }
