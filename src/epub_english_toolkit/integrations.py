from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .storage import ensure_dir


def export_anki(pack: dict[str, Any], output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    seen: set[tuple[str, str]] = set()
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["Front", "Back", "Tags"])
        for task in pack["weekly_plan"]:
            tags = " ".join(task.get("tags", []))
            for item in task["vocabulary"]:
                key = (task["article_id"], item["phrase"])
                if key in seen:
                    continue
                seen.add(key)
                writer.writerow(
                    [
                        item["phrase"],
                        f"{item.get('example', '')}\n\nSource: {task['title']}",
                        f"{tags} {task['section'].lower().replace(' ', '-')}",
                    ]
                )
    return output_path


def export_notion(pack: dict[str, Any], output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Name",
                "Date",
                "Status",
                "Type",
                "Pack ID",
                "Article",
                "Section",
                "Difficulty",
                "Minutes",
                "Prompt",
                "Tracker ID",
            ]
        )
        for task in pack["weekly_plan"]:
            writer.writerow(
                [
                    task["title"],
                    task["date"],
                    task.get("status", "pending"),
                    "study",
                    pack["pack_id"],
                    task["article_id"],
                    task["section"],
                    f"{task['difficulty_level']} ({task['difficulty_score']})",
                    task["estimated_minutes"],
                    task["writing_task"]["essay_prompt"],
                    task["task_id"],
                ]
            )
            for review in task["reviews"]:
                writer.writerow(
                    [
                        f"{task['title']} - {review['review_type']}",
                        review["due_date"],
                        review.get("status", "pending"),
                        "review",
                        pack["pack_id"],
                        task["article_id"],
                        task["section"],
                        f"{task['difficulty_level']} ({task['difficulty_score']})",
                        10,
                        review["prompt"],
                        review["review_id"],
                    ]
                )
    return output_path
