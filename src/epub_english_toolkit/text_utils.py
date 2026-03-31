from __future__ import annotations

import html
import re
from collections import Counter
from html.parser import HTMLParser
from typing import Any


STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "do",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "more",
    "must",
    "not",
    "of",
    "on",
    "one",
    "or",
    "our",
    "said",
    "she",
    "should",
    "since",
    "that",
    "than",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "under",
    "until",
    "was",
    "while",
    "were",
    "what",
    "when",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}


class ParagraphHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current: list[str] = []
        self.paragraphs: list[str] = []
        self._capture_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "blockquote"}:
            if self._capture_depth == 0:
                self._current = []
            self._capture_depth += 1
        elif tag == "br" and self._capture_depth:
            self._current.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "blockquote"} and self._capture_depth:
            self._capture_depth -= 1
            if self._capture_depth == 0:
                paragraph = normalize_whitespace("".join(self._current))
                if paragraph:
                    self.paragraphs.append(paragraph)
                self._current = []

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self._current.append(data)


def normalize_whitespace(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def html_to_paragraphs(markup: str) -> list[str]:
    parser = ParagraphHTMLParser()
    parser.feed(markup)
    paragraphs = [line for line in parser.paragraphs if len(line.split()) >= 4]
    return paragraphs


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "item"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower())


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def estimate_reading_minutes(word_count: int) -> int:
    return max(1, round(word_count / 220))


def extract_candidate_phrases(paragraphs: list[str], limit: int = 8) -> list[dict[str, Any]]:
    tokens = tokenize(" ".join(paragraphs))
    token_counts = Counter(token for token in tokens if token not in STOPWORDS and len(token) > 3)
    ngram_counts: Counter[tuple[str, ...]] = Counter()
    for paragraph in paragraphs:
        words = tokenize(paragraph)
        for size in (2, 3):
            for index in range(0, max(0, len(words) - size + 1)):
                chunk = tuple(words[index : index + size])
                if chunk[0] in STOPWORDS or chunk[-1] in STOPWORDS:
                    continue
                if any(len(word) <= 2 for word in chunk):
                    continue
                ngram_counts[chunk] += 1

    ranked: list[dict[str, Any]] = []
    seen = set()
    for ngram, score in ngram_counts.most_common(limit * 4):
        phrase = " ".join(ngram)
        if phrase in seen:
            continue
        strength = score + sum(token_counts[word] for word in ngram)
        if strength < 8:
            continue
        if min(token_counts[word] for word in ngram) <= 1 and strength < 12:
            continue
        seen.add(phrase)
        ranked.append(
            {
                "phrase": phrase,
                "score": strength,
                "example": find_phrase_example(paragraphs, phrase),
            }
        )
        if len(ranked) >= limit:
            break
    return ranked


def _legacy_broken_summarize_excerpt(paragraphs: list[str], max_chars: int = 220) -> str:
    if not paragraphs:
        return ""
    excerpt = paragraphs[0]
    if len(excerpt) <= max_chars:
        return excerpt
    return excerpt[: max_chars - 1].rstrip() + "…"


def choose_focus_sentence(paragraphs: list[str]) -> str:
    for paragraph in paragraphs:
        if "|" in paragraph:
            continue
        if sum(char.isdigit() for char in paragraph) >= 4 and len(paragraph.split()) <= 10:
            continue
        for sentence in split_sentences(paragraph):
            sentence = sentence.strip()
            if 12 <= len(sentence.split()) <= 35:
                return sentence
    if not paragraphs:
        return ""
    fallback_sentences = split_sentences(paragraphs[0].strip())
    first_sentence = fallback_sentences[0].strip() if fallback_sentences else ""
    return first_sentence or paragraphs[0]


def summarize_excerpt(paragraphs: list[str], max_chars: int = 220) -> str:
    if not paragraphs:
        return ""
    excerpt = paragraphs[0]
    if len(excerpt) <= max_chars:
        return excerpt
    return excerpt[: max_chars - 3].rstrip() + "..."


def find_phrase_example(paragraphs: list[str], phrase: str) -> str:
    words = phrase.split()
    phrase_pattern = re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b", re.IGNORECASE)
    for paragraph in paragraphs:
        for sentence in split_sentences(paragraph):
            if phrase_pattern.search(sentence):
                return sentence
    return paragraphs[0] if paragraphs else ""


def analyze_difficulty(paragraphs: list[str]) -> tuple[int, str, dict[str, float | int]]:
    text = " ".join(paragraphs)
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    lower_tokens = [token.lower() for token in tokens]
    content_tokens = [token for token in lower_tokens if token not in STOPWORDS]
    sentences = [sentence for paragraph in paragraphs for sentence in split_sentences(paragraph)]
    sentence_count = max(1, len(sentences))
    word_count = max(1, len(tokens))
    unique_ratio = len(set(content_tokens)) / max(1, len(content_tokens))
    lexical_density = len(content_tokens) / word_count
    avg_sentence_length = word_count / sentence_count
    long_word_ratio = sum(1 for token in lower_tokens if len(token) >= 7) / word_count
    capitalized_ratio = sum(1 for token in tokens if token[:1].isupper()) / word_count

    raw_score = (
        avg_sentence_length * 1.8
        + lexical_density * 28
        + unique_ratio * 18
        + long_word_ratio * 85
        + capitalized_ratio * 12
    )
    score = max(1, min(100, round(raw_score)))
    if score < 32:
        level = "B1"
    elif score < 48:
        level = "B2"
    elif score < 66:
        level = "C1"
    else:
        level = "C2"

    metrics: dict[str, float | int] = {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 2),
        "lexical_density": round(lexical_density, 3),
        "unique_ratio": round(unique_ratio, 3),
        "long_word_ratio": round(long_word_ratio, 3),
        "capitalized_ratio": round(capitalized_ratio, 3),
    }
    return score, level, metrics
