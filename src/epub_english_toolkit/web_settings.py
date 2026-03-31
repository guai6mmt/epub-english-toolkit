from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class WebSettings:
    project_root: Path
    data_root: Path
    uploads_root: Path
    library_root: Path
    packs_root: Path
    tracker_path: Path
    database_path: Path
    templates_root: Path
    static_root: Path
    default_mode: str
    default_focus_topics: str
    basic_auth_username: str
    basic_auth_password: str


def load_web_settings() -> WebSettings:
    project_root = Path(os.getenv("EPUB_TOOLKIT_PROJECT_ROOT", Path.cwd())).resolve()
    data_root = Path(os.getenv("EPUB_TOOLKIT_DATA_ROOT", project_root / "web_data")).resolve()
    uploads_root = Path(os.getenv("EPUB_TOOLKIT_UPLOADS_ROOT", data_root / "uploads")).resolve()
    library_root = Path(os.getenv("EPUB_TOOLKIT_LIBRARY_ROOT", data_root / "library")).resolve()
    packs_root = Path(os.getenv("EPUB_TOOLKIT_PACKS_ROOT", data_root / "study_packs")).resolve()
    tracker_path = Path(os.getenv("EPUB_TOOLKIT_TRACKER_PATH", data_root / "progress" / "tracker.json")).resolve()
    database_path = Path(os.getenv("EPUB_TOOLKIT_DATABASE_PATH", data_root / "app.db")).resolve()
    templates_root = project_root / "src" / "epub_english_toolkit" / "web_templates"
    static_root = project_root / "src" / "epub_english_toolkit" / "web_static"

    return WebSettings(
        project_root=project_root,
        data_root=data_root,
        uploads_root=uploads_root,
        library_root=library_root,
        packs_root=packs_root,
        tracker_path=tracker_path,
        database_path=database_path,
        templates_root=templates_root,
        static_root=static_root,
        default_mode=os.getenv("EPUB_TOOLKIT_DEFAULT_MODE", "ielts"),
        default_focus_topics=os.getenv("EPUB_TOOLKIT_DEFAULT_FOCUS_TOPICS", "politics,business,culture"),
        basic_auth_username=os.getenv("EPUB_TOOLKIT_WEB_USER", ""),
        basic_auth_password=os.getenv("EPUB_TOOLKIT_WEB_PASSWORD", ""),
    )
