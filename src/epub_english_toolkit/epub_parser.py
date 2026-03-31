from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .models import Article, Book
from .text_utils import (
    analyze_difficulty,
    estimate_reading_minutes,
    html_to_paragraphs,
    slugify,
    summarize_excerpt,
)


NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
}


SECTION_TAGS = {
    "politics": ["politics", "leaders", "united states", "europe", "asia", "china", "middle east", "the americas"],
    "business": ["business", "business & finance", "finance", "economic", "economy"],
    "science": ["science", "technology", "tech", "innovation"],
    "culture": ["culture", "books", "letters", "obituary", "christmas", "graphic detail"],
}


def import_epub(epub_path: str) -> tuple[Book, list[Article]]:
    epub_file = ZipFile(epub_path)
    try:
        opf_path = _find_opf_path(epub_file)
        opf_root = ET.fromstring(epub_file.read(opf_path))
        metadata = _parse_metadata(opf_root)
        nav_entries = _parse_navigation(epub_file, opf_path, opf_root)
        articles = _extract_articles(epub_file, nav_entries)
        book = Book(
            book_id=slugify(metadata["title"]),
            title=metadata["title"],
            source_path=epub_path,
            language=metadata.get("language", "en"),
            publisher=metadata.get("publisher", ""),
            published_at=metadata.get("date", ""),
            imported_at=datetime.now(timezone.utc).isoformat(),
            description=metadata.get("description", ""),
            sections=sorted({article.section for article in articles}),
            article_count=len(articles),
        )
        return book, articles
    finally:
        epub_file.close()


def _find_opf_path(epub_file: ZipFile) -> str:
    if "META-INF/container.xml" in epub_file.namelist():
        container_root = ET.fromstring(epub_file.read("META-INF/container.xml"))
        rootfile = container_root.find(".//{*}rootfile")
        if rootfile is not None:
            full_path = rootfile.attrib.get("full-path")
            if full_path:
                return full_path
    for name in epub_file.namelist():
        if name.endswith(".opf"):
            return name
    raise FileNotFoundError("Could not locate OPF manifest in EPUB")


def _parse_metadata(opf_root: ET.Element) -> dict[str, str]:
    metadata = opf_root.find("opf:metadata", NS)
    if metadata is None:
        return {}
    fields = {
        "title": metadata.findtext("dc:title", default="", namespaces=NS),
        "description": metadata.findtext("dc:description", default="", namespaces=NS),
        "publisher": metadata.findtext("dc:publisher", default="", namespaces=NS),
        "date": metadata.findtext("dc:date", default="", namespaces=NS),
        "language": metadata.findtext("dc:language", default="en", namespaces=NS),
    }
    return fields


def _parse_navigation(epub_file: ZipFile, opf_path: str, opf_root: ET.Element) -> list[dict[str, str | int]]:
    ncx_href = None
    manifest = opf_root.find("opf:manifest", NS)
    if manifest is not None:
        for item in manifest.findall("opf:item", NS):
            if item.attrib.get("media-type") == "application/x-dtbncx+xml":
                ncx_href = item.attrib.get("href")
                break
    if not ncx_href:
        raise FileNotFoundError("Could not locate NCX navigation file")

    ncx_path = str((PurePosixPath(opf_path).parent / ncx_href).as_posix()).lstrip("./")
    ncx_root = ET.fromstring(epub_file.read(ncx_path))
    entries: list[dict[str, str | int]] = []
    order = 0

    def walk(node: ET.Element, parent_section: str | None = None) -> None:
        nonlocal order
        label = node.findtext("ncx:navLabel/ncx:text", default="", namespaces=NS).strip()
        content = node.find("ncx:content", NS)
        src = content.attrib.get("src", "") if content is not None else ""
        children = node.findall("ncx:navPoint", NS)
        if children:
            next_section = label or parent_section or ""
            for child in children:
                walk(child, next_section)
            return

        order += 1
        entries.append(
            {
                "order": order,
                "section": parent_section or "General",
                "title": label or f"Article {order}",
                "href": str((PurePosixPath(ncx_path).parent / src).as_posix()),
            }
        )

    for nav_point in ncx_root.findall(".//ncx:navMap/ncx:navPoint", NS):
        walk(nav_point)
    return entries


def _extract_articles(epub_file: ZipFile, nav_entries: list[dict[str, str | int]]) -> list[Article]:
    articles: list[Article] = []
    seen_hrefs: set[str] = set()
    for entry in nav_entries:
        href = str(entry["href"])
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        try:
            markup = epub_file.read(href).decode("utf-8")
        except UnicodeDecodeError:
            markup = epub_file.read(href).decode("utf-8", errors="ignore")
        paragraphs = _clean_paragraphs(html_to_paragraphs(markup), str(entry["title"]))
        if not _looks_like_article(entry["title"], paragraphs):
            continue
        word_count = sum(len(paragraph.split()) for paragraph in paragraphs)
        difficulty_score, difficulty_level, difficulty_metrics = analyze_difficulty(paragraphs)
        title = _choose_title(str(entry["title"]), paragraphs)
        section = str(entry["section"])
        article = Article(
            article_id=f"{slugify(section)}-{slugify(title)}",
            book_id="",
            title=title,
            section=section,
            order=int(entry["order"]),
            href=href,
            word_count=word_count,
            reading_minutes=estimate_reading_minutes(word_count),
            paragraphs=paragraphs,
            tags=_infer_tags(section, title),
            excerpt=summarize_excerpt(paragraphs),
            difficulty_score=difficulty_score,
            difficulty_level=difficulty_level,
            difficulty_metrics=difficulty_metrics,
        )
        articles.append(article)

    if articles:
        book_id = _derive_book_id(articles)
        for article in articles:
            article.book_id = book_id
    return articles


def _derive_book_id(articles: list[Article]) -> str:
    section = articles[0].section if articles else "book"
    return slugify(re.sub(r"\s+", "-", section))


def _choose_title(nav_title: str, paragraphs: list[str]) -> str:
    if nav_title and nav_title.lower() != "unknown":
        return nav_title
    for paragraph in paragraphs[:2]:
        if len(paragraph.split()) <= 15:
            return paragraph
    return nav_title or "Untitled article"


def _looks_like_article(nav_title: str, paragraphs: list[str]) -> bool:
    if not paragraphs:
        return False
    if len(paragraphs) < 3:
        return False
    word_count = sum(len(paragraph.split()) for paragraph in paragraphs)
    if word_count < 120:
        return False
    heading_candidates = {paragraphs[0].strip().lower(), nav_title.strip().lower()}
    if any(candidate in {"the economist", "unknown"} for candidate in heading_candidates):
        return False
    return True


def _clean_paragraphs(paragraphs: list[str], nav_title: str) -> list[str]:
    cleaned: list[str] = []
    title_normalized = re.sub(r"\s+", " ", nav_title).strip().lower()
    title_slug = slugify(nav_title)
    for index, paragraph in enumerate(paragraphs):
        normalized = re.sub(r"\s+", " ", paragraph).strip()
        lower = normalized.lower()
        if not normalized:
            continue
        if index <= 1 and (lower == title_normalized or slugify(normalized) == title_slug):
            continue
        if _is_metadata_line(normalized):
            continue
        cleaned.append(normalized)
    return cleaned


def _is_metadata_line(paragraph: str) -> bool:
    if len(paragraph.split()) <= 2 and any(char.isdigit() for char in paragraph):
        return True
    if len(paragraph) <= 24 and sum(char.isdigit() for char in paragraph) >= 4:
        return True
    if "|" in paragraph and sum(char.isdigit() for char in paragraph) >= 2 and len(paragraph.split()) <= 12:
        return True
    if re.search(r"\b(19|20)\d{2}\b", paragraph) and len(paragraph.split()) <= 8:
        return True
    if any(token in paragraph.lower() for token in ("am", "pm", "上午", "下午")) and len(paragraph.split()) <= 8:
        return True
    return False


def _infer_tags(section: str, title: str) -> list[str]:
    normalized = f"{section} {title}".lower()
    tags: list[str] = []
    for tag, keywords in SECTION_TAGS.items():
        if any(keyword in normalized for keyword in keywords):
            tags.append(tag)

    title_lower = title.lower()
    if any(word in title_lower for word in ("war", "election", "government", "trump", "china", "iran")):
        tags.append("ielts-speaking")
    if any(word in title_lower for word in ("economy", "business", "market", "energy", "technology", "culture")):
        tags.append("ielts-writing")
    return sorted(set(tags))
