from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .models import Article, Book, StudyPack
from .text_utils import choose_focus_sentence, extract_candidate_phrases


REVIEW_INTERVALS = [0, 1, 3, 7, 14]


def build_study_pack(
    book: Book,
    articles: list[Article],
    start_date: date,
    focus_topics: list[str] | None = None,
    main_count: int = 2,
    short_count: int = 3,
    mode: str = "general",
) -> StudyPack:
    focus_topics = [item.lower() for item in (focus_topics or [])]
    selected = select_articles(articles, focus_topics, main_count, short_count, mode=mode)
    weekly_plan = []
    for day_offset, article_bundle in enumerate(selected):
        article = article_bundle["article"]
        task_date = start_date + timedelta(days=day_offset)
        pack_id = f"{book.book_id}-{start_date.isoformat()}"
        task_id = f"{pack_id}:study:{day_offset + 1}"
        study_task = {
            "date": task_date.isoformat(),
            "pack_id": pack_id,
            "task_id": task_id,
            "article_id": article.article_id,
            "title": article.title,
            "section": article.section,
            "task_type": article_bundle["task_type"],
            "reading_focus": _reading_focus(article, mode),
            "speaking_task": _speaking_task(article, mode),
            "writing_task": _writing_task(article, mode),
            "vocabulary": extract_candidate_phrases(article.paragraphs),
            "reviews": _review_dates(task_date, pack_id, article),
            "difficulty_score": article.difficulty_score,
            "difficulty_level": article.difficulty_level,
            "difficulty_metrics": article.difficulty_metrics,
            "estimated_minutes": _estimated_minutes(article_bundle["task_type"], mode),
            "tags": article.tags,
            "mode": mode,
        }
        weekly_plan.append(study_task)

    selected_articles = [_article_payload(bundle["article"], bundle["task_type"]) for bundle in selected]
    return StudyPack(
        pack_id=f"{book.book_id}-{start_date.isoformat()}",
        book_id=book.book_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        start_date=start_date.isoformat(),
        focus_topics=focus_topics,
        selected_articles=selected_articles,
        weekly_plan=weekly_plan,
        mode=mode,
    )


def select_articles(
    articles: list[Article],
    focus_topics: list[str],
    main_count: int,
    short_count: int,
    mode: str = "general",
) -> list[dict[str, Any]]:
    ranked = sorted(
        articles,
        key=lambda article: (
            _focus_score(article, focus_topics, mode),
            article.word_count,
            -article.order,
        ),
        reverse=True,
    )
    mains: list[Article] = []
    shorts: list[Article] = []
    used_ids: set[str] = set()
    used_sections: set[str] = set()

    for article in ranked:
        if article.article_id in used_ids:
            continue
        section_penalty = article.section in used_sections
        if len(mains) < main_count and article.word_count >= 450 and not section_penalty:
            mains.append(article)
            used_ids.add(article.article_id)
            used_sections.add(article.section)
            continue
        if len(shorts) < short_count and 140 <= article.word_count < 450 and not section_penalty:
            shorts.append(article)
            used_ids.add(article.article_id)
            used_sections.add(article.section)
        if len(mains) >= main_count and len(shorts) >= short_count:
            break

    if len(mains) < main_count or len(shorts) < short_count:
        for article in ranked:
            if article.article_id in used_ids:
                continue
            if len(mains) < main_count and article.word_count >= 450:
                mains.append(article)
                used_ids.add(article.article_id)
                continue
            if len(shorts) < short_count and 140 <= article.word_count < 450:
                shorts.append(article)
                used_ids.add(article.article_id)
            if len(mains) >= main_count and len(shorts) >= short_count:
                break

    selected: list[dict[str, Any]] = []
    for article in mains:
        selected.append({"article": article, "task_type": "deep_read"})
    for article in shorts:
        selected.append({"article": article, "task_type": "fast_read"})
    return selected


def collect_due_reviews(pack: StudyPack, target_date: date) -> list[dict[str, Any]]:
    due: list[dict[str, Any]] = []
    for task in pack.weekly_plan:
        for review in task["reviews"]:
            if review["due_date"] == target_date.isoformat():
                due.append(
                    {
                        "title": task["title"],
                        "article_id": task["article_id"],
                        "review_type": review["review_type"],
                        "prompt": review["prompt"],
                        "review_id": review["review_id"],
                        "pack_id": review.get("pack_id", task.get("pack_id", "")),
                        "section": task["section"],
                    }
                )
    return due


def _focus_score(article: Article, focus_topics: list[str], mode: str) -> int:
    if not focus_topics:
        score = len(article.tags)
    else:
        article_tokens = {article.section.lower(), article.title.lower(), *article.tags}
        score = 0
        for topic in focus_topics:
            if any(topic in token for token in article_tokens):
                score += 3
        score += len(article.tags)
    if "ielts-writing" in article.tags or "ielts-speaking" in article.tags:
        score += 1
    if mode == "ielts":
        if "ielts-writing" in article.tags:
            score += 3
        if "ielts-speaking" in article.tags:
            score += 3
        if article.difficulty_level in {"B2", "C1"}:
            score += 2
    return score


def _article_payload(article: Article, task_type: str) -> dict[str, Any]:
    return {
        "article_id": article.article_id,
        "title": article.title,
        "section": article.section,
        "task_type": task_type,
        "word_count": article.word_count,
        "reading_minutes": article.reading_minutes,
        "tags": article.tags,
        "excerpt": article.excerpt,
        "difficulty_score": article.difficulty_score,
        "difficulty_level": article.difficulty_level,
    }


def _reading_focus(article: Article, mode: str) -> list[str]:
    if mode == "ielts":
        return [
            f"Skim '{article.title}' in 3 minutes and write the main idea of each paragraph group.",
            "Underline the author's opinion, any concession, and the final conclusion.",
            "Choose 3 phrases you could reuse in IELTS Writing Task 2.",
        ]
    return [
        f"Summarise the main claim of '{article.title}' in 2 English sentences.",
        "Mark the paragraph where the author shifts from facts to interpretation.",
        f"Notice how the section '{article.section}' frames the issue for an international audience.",
    ]


def _speaking_task(article: Article, mode: str) -> dict[str, Any]:
    focus_sentence = choose_focus_sentence(article.paragraphs)
    payload = {
        "warmup": f"Give a 30-second summary of why '{article.title}' matters.",
        "retell": "Record a 2-minute retelling: issue, causes, consequences, and your opinion.",
        "part3_questions": [
            f"Why do international readers care about {article.section.lower()} issues like this?",
            "Do media reports shape public opinion or mainly reflect it?",
            "What background knowledge would help someone discuss this topic confidently in IELTS?",
        ],
        "shadowing_sentence": focus_sentence,
    }
    if mode == "ielts":
        payload["part2_cue_card"] = {
            "prompt": f"Describe a news issue related to '{article.title}' that people should understand better.",
            "bullet_points": [
                "What the issue is",
                "Why it became important",
                "What different groups think about it",
                "Why it is worth discussing in English",
            ],
        }
    return payload


def _writing_task(article: Article, mode: str) -> dict[str, Any]:
    payload = {
        "summary_120w": f"Write a 120-word summary of '{article.title}' without looking back at the text.",
        "essay_prompt": (
            f"Use '{article.title}' as background. Discuss whether governments should prioritise "
            "short-term stability or long-term reform when facing international pressure."
        ),
        "sentence_pattern": "There is growing concern that ..., yet the deeper issue is whether ...",
    }
    if mode == "ielts":
        payload["task2_prompt"] = (
            f"Some people believe topics like '{article.title}' show that governments should solve immediate crises "
            "before investing in long-term change. To what extent do you agree or disagree?"
        )
        payload["outline_prompt"] = "Write an IELTS Task 2 outline with introduction, two body paragraphs, and conclusion."
    return payload


def _review_dates(base_date: date, pack_id: str, article: Article) -> list[dict[str, str]]:
    review_types = [
        "same_day_recall",
        "next_day_retell",
        "three_day_phrase_review",
        "one_week_writing_reuse",
        "two_week_speaking_reuse",
    ]
    prompts = [
        "Retell the article from memory in 5 bullet points.",
        "Speak for 90 seconds without notes.",
        "Reuse 5 phrases from the article in original sentences.",
        "Write a 180-word opinion paragraph using the article as evidence.",
        "Answer one IELTS-style Part 3 question related to the topic.",
    ]
    return [
        {
            "due_date": (base_date + timedelta(days=days)).isoformat(),
            "review_type": review_type,
            "prompt": prompt,
            "pack_id": pack_id,
            "review_id": f"{pack_id}:review:{article.article_id}:{review_type}",
        }
        for days, review_type, prompt in zip(REVIEW_INTERVALS, review_types, prompts, strict=True)
    ]


def _estimated_minutes(task_type: str, mode: str) -> int:
    base = 32 if task_type == "deep_read" else 18
    if mode == "ielts":
        base += 8
    return base
