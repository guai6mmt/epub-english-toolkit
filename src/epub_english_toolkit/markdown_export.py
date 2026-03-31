from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .storage import write_text


def export_pack_markdown(pack: dict[str, Any], output_path: Path) -> Path:
    lines: list[str] = []
    lines.append(f"# Study Pack: {pack['pack_id']}")
    lines.append("")
    lines.append(f"- Mode: `{pack.get('mode', 'general')}`")
    lines.append(f"- Start date: `{pack['start_date']}`")
    lines.append(f"- Focus topics: {', '.join(pack.get('focus_topics', [])) or 'general'}")
    lines.append("")
    lines.append("## Selected Articles")
    lines.append("")
    for article in pack["selected_articles"]:
        lines.append(
            f"- **{article['title']}** | {article['section']} | {article['task_type']} | "
            f"{article['difficulty_level']} ({article['difficulty_score']}) | {article['reading_minutes']} min"
        )
        lines.append(f"  - {article['excerpt']}")
    lines.append("")
    lines.append("## Weekly Plan")
    lines.append("")

    for task in pack["weekly_plan"]:
        lines.append(f"### {task['date']} - {task['title']}")
        lines.append("")
        lines.append(f"- Task ID: `{task['task_id']}`")
        lines.append(f"- Status: `{task.get('status', 'pending')}`")
        lines.append(f"- Difficulty: `{task['difficulty_level']} ({task['difficulty_score']})`")
        lines.append(f"- Estimated minutes: `{task['estimated_minutes']}`")
        lines.append("- Reading focus:")
        for item in task["reading_focus"]:
            lines.append(f"  - {item}")
        lines.append("- Speaking:")
        lines.append(f"  - Warm-up: {task['speaking_task']['warmup']}")
        lines.append(f"  - Retell: {task['speaking_task']['retell']}")
        if "part2_cue_card" in task["speaking_task"]:
            cue = task["speaking_task"]["part2_cue_card"]
            lines.append(f"  - Part 2: {cue['prompt']}")
        lines.append(f"  - Shadowing: {task['speaking_task']['shadowing_sentence']}")
        lines.append("- Writing:")
        lines.append(f"  - Summary: {task['writing_task']['summary_120w']}")
        lines.append(f"  - Essay: {task['writing_task']['essay_prompt']}")
        lines.append("- Vocabulary:")
        for phrase in task["vocabulary"]:
            lines.append(f"  - {phrase['phrase']}: {phrase.get('example', '')}")
        lines.append("- Reviews:")
        for review in task["reviews"]:
            lines.append(
                f"  - `{review['due_date']}` {review['review_type']} | `{review['review_id']}` | {review.get('status', 'pending')}"
            )
        lines.append("")

    write_text(output_path, "\n".join(lines).strip() + "\n")
    return output_path


def export_daily_markdown(plan: dict[str, Any], output_path: Path) -> Path:
    lines: list[str] = []
    lines.append(f"# Daily Plan: {plan['date']}")
    lines.append("")
    lines.append(f"- Study tasks: `{plan['totals']['study_tasks']}`")
    lines.append(f"- Review tasks: `{plan['totals']['review_tasks']}`")
    lines.append(f"- Completed study tasks: `{plan['totals'].get('completed_study_tasks', 0)}`")
    lines.append(f"- Completed review tasks: `{plan['totals'].get('completed_review_tasks', 0)}`")
    lines.append("")
    lines.append("## Study Tasks")
    lines.append("")
    for task in plan["study_tasks"]:
        checkbox = "[x]" if task.get("status") == "completed" else "[ ]"
        lines.append(f"- {checkbox} `{task['task_id']}` {task['title']} ({task['estimated_minutes']} min)")
    lines.append("")
    lines.append("## Review Tasks")
    lines.append("")
    for review in plan["review_tasks"]:
        checkbox = "[x]" if review.get("status") == "completed" else "[ ]"
        lines.append(f"- {checkbox} `{review['review_id']}` {review['title']} - {review['prompt']}")
    write_text(output_path, "\n".join(lines).strip() + "\n")
    return output_path
