from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from .integrations import export_anki, export_notion
from .markdown_export import export_daily_markdown, export_pack_markdown
from .reporting import build_daily_plan, build_progress_report
from .services import (
    create_study_pack,
    import_book,
    load_article_lookup,
    load_pack,
    load_packs,
)
from .tracking import get_status_map, set_item_status
from .tts_tools import export_tts_assets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epub-english-toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-epub", help="Import one EPUB into the local library.")
    import_parser.add_argument("--epub", required=True, help="Path to the source EPUB file.")
    import_parser.add_argument("--library", default="data/library", help="Library directory.")

    pack_parser = subparsers.add_parser("make-study-pack", help="Create a weekly study pack from a book.")
    pack_parser.add_argument("--book-id", required=True, help="Imported book ID.")
    pack_parser.add_argument("--library", default="data/library", help="Library directory.")
    pack_parser.add_argument("--output", default="data/study_packs", help="Study pack output directory.")
    pack_parser.add_argument("--start-date", required=True, help="Study start date (YYYY-MM-DD).")
    pack_parser.add_argument("--focus-topics", nargs="*", default=[], help="Optional focus topics.")
    pack_parser.add_argument("--main-count", type=int, default=2, help="Number of deep-read articles.")
    pack_parser.add_argument("--short-count", type=int, default=3, help="Number of fast-read articles.")
    pack_parser.add_argument("--mode", choices=["general", "ielts"], default="general", help="Study mode.")

    plan_parser = subparsers.add_parser("daily-plan", help="Build a study plan for one day.")
    plan_parser.add_argument("--packs", default="data/study_packs", help="Study pack directory.")
    plan_parser.add_argument("--date", required=True, help="Target date (YYYY-MM-DD).")
    plan_parser.add_argument("--tracker", default="data/progress/tracker.json", help="Completion tracker path.")

    report_parser = subparsers.add_parser("progress-report", help="Summarise existing study packs.")
    report_parser.add_argument("--packs", default="data/study_packs", help="Study pack directory.")
    report_parser.add_argument("--tracker", default="data/progress/tracker.json", help="Completion tracker path.")

    status_parser = subparsers.add_parser("set-status", help="Mark a study or review item as completed or pending.")
    status_parser.add_argument("--id", required=True, help="Tracker item ID from daily-plan or exported markdown.")
    status_parser.add_argument("--status", choices=["completed", "pending"], default="completed")
    status_parser.add_argument("--kind", choices=["study", "review"], default=None)
    status_parser.add_argument("--pack-id", default=None)
    status_parser.add_argument("--note", default="")
    status_parser.add_argument("--tracker", default="data/progress/tracker.json", help="Completion tracker path.")

    pack_md_parser = subparsers.add_parser("export-pack-markdown", help="Export one pack as Markdown.")
    pack_md_parser.add_argument("--pack-id", required=True)
    pack_md_parser.add_argument("--packs", default="data/study_packs")
    pack_md_parser.add_argument("--tracker", default="data/progress/tracker.json")
    pack_md_parser.add_argument("--output", default="exports/markdown")

    daily_md_parser = subparsers.add_parser("export-daily-markdown", help="Export one daily plan as Markdown.")
    daily_md_parser.add_argument("--date", required=True)
    daily_md_parser.add_argument("--packs", default="data/study_packs")
    daily_md_parser.add_argument("--tracker", default="data/progress/tracker.json")
    daily_md_parser.add_argument("--output", default="exports/markdown")

    anki_parser = subparsers.add_parser("export-anki", help="Export pack vocabulary as Anki TSV.")
    anki_parser.add_argument("--pack-id", required=True)
    anki_parser.add_argument("--packs", default="data/study_packs")
    anki_parser.add_argument("--output", default="exports/anki")

    notion_parser = subparsers.add_parser("export-notion", help="Export pack tasks as Notion CSV.")
    notion_parser.add_argument("--pack-id", required=True)
    notion_parser.add_argument("--packs", default="data/study_packs")
    notion_parser.add_argument("--tracker", default="data/progress/tracker.json")
    notion_parser.add_argument("--output", default="exports/notion")

    tts_parser = subparsers.add_parser("export-tts", help="Export TTS text and optional WAV files for one pack.")
    tts_parser.add_argument("--pack-id", required=True)
    tts_parser.add_argument("--packs", default="data/study_packs")
    tts_parser.add_argument("--library", default="data/library")
    tts_parser.add_argument("--output", default="exports/tts")
    tts_parser.add_argument("--audio", action="store_true", help="Generate WAV files with Windows System.Speech.")
    tts_parser.add_argument("--voice-name", default="", help="Optional Windows voice name.")

    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "import-epub":
        handle_import(Path(args.epub), Path(args.library))
    elif args.command == "make-study-pack":
        handle_study_pack(
            book_id=args.book_id,
            library=Path(args.library),
            output=Path(args.output),
            start_date=date.fromisoformat(args.start_date),
            focus_topics=args.focus_topics,
            main_count=args.main_count,
            short_count=args.short_count,
            mode=args.mode,
        )
    elif args.command == "daily-plan":
        plan = build_daily_plan(
            load_packs(Path(args.packs)),
            date.fromisoformat(args.date),
            get_status_map(Path(args.tracker)),
        )
        print_json(plan)
    elif args.command == "progress-report":
        report = build_progress_report(load_packs(Path(args.packs)), get_status_map(Path(args.tracker)))
        print_json(report)
    elif args.command == "set-status":
        result = set_item_status(
            Path(args.tracker),
            args.id,
            args.status,
            kind=args.kind,
            pack_id=args.pack_id,
            note=args.note,
        )
        print_json({"id": args.id, **result})
    elif args.command == "export-pack-markdown":
        pack = load_pack(Path(args.packs), args.pack_id, Path(args.tracker))
        path = Path(args.output) / f"{args.pack_id}.md"
        export_pack_markdown(pack, path)
        print_json({"pack_id": args.pack_id, "output_path": str(path)})
    elif args.command == "export-daily-markdown":
        plan = build_daily_plan(
            load_packs(Path(args.packs)),
            date.fromisoformat(args.date),
            get_status_map(Path(args.tracker)),
        )
        path = Path(args.output) / f"daily-{args.date}.md"
        export_daily_markdown(plan, path)
        print_json({"date": args.date, "output_path": str(path)})
    elif args.command == "export-anki":
        pack = load_pack(Path(args.packs), args.pack_id)
        path = Path(args.output) / f"{args.pack_id}.tsv"
        export_anki(pack, path)
        print_json({"pack_id": args.pack_id, "output_path": str(path)})
    elif args.command == "export-notion":
        pack = load_pack(Path(args.packs), args.pack_id, Path(args.tracker))
        path = Path(args.output) / f"{args.pack_id}.csv"
        export_notion(pack, path)
        print_json({"pack_id": args.pack_id, "output_path": str(path)})
    elif args.command == "export-tts":
        pack = load_pack(Path(args.packs), args.pack_id)
        article_lookup = load_article_lookup(Path(args.library), pack["book_id"])
        output_dir = Path(args.output) / args.pack_id
        exported = export_tts_assets(
            pack,
            article_lookup,
            output_dir,
            create_audio=args.audio,
            voice_name=args.voice_name,
        )
        print_json({"pack_id": args.pack_id, "output_dir": str(output_dir), "assets": exported})


def handle_import(epub_path: Path, library: Path) -> None:
    print_json(import_book(epub_path, library))


def handle_study_pack(
    book_id: str,
    library: Path,
    output: Path,
    start_date: date,
    focus_topics: list[str],
    main_count: int,
    short_count: int,
    mode: str,
) -> None:
    print_json(
        create_study_pack(
            book_id=book_id,
            library_root=library,
            packs_root=output,
            start_date=start_date,
            focus_topics=focus_topics,
            main_count=main_count,
            short_count=short_count,
            mode=mode,
        )
    )


def print_json(payload: dict) -> None:
    import json

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
