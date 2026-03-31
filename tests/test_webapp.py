from __future__ import annotations

import shutil
import unittest
from pathlib import Path
import sqlite3
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from epub_english_toolkit.web_db import create_upload_job, get_upload_job
from epub_english_toolkit.web_settings import WebSettings
from epub_english_toolkit.webapp import create_app, init_runtime, process_upload_job


LONG_PARAGRAPH = (
    "Governments, businesses and ordinary readers all respond differently when energy, politics and technology "
    "begin to reshape everyday life, and that tension creates useful material for advanced English learners. "
    "A well-written article explains the issue, compares competing arguments, provides evidence and ends with a "
    "measured judgement that can be reused in both speaking and writing practice. "
)


def build_long_epub(target: Path) -> None:
    article_a = "<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>Energy policy and urban change</h1>" + "".join(
        f"<p>{LONG_PARAGRAPH}</p>" for _ in range(8)
    ) + "</body></html>"
    article_b = "<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>Culture, tourism and identity</h1>" + "".join(
        f"<p>{LONG_PARAGRAPH}</p>" for _ in range(8)
    ) + "</body></html>"

    with ZipFile(target, "w", compression=ZIP_DEFLATED) as epub:
        epub.writestr("mimetype", "application/epub+zip")
        epub.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )
        epub.writestr(
            "content.opf",
            """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Web Weekly</dc:title>
    <dc:language>en</dc:language>
    <dc:publisher>Test Publisher</dc:publisher>
    <dc:date>2026-03-31T00:00:00+00:00</dc:date>
    <dc:description>Sample weekly issue.</dc:description>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="a1" href="article1.xhtml" media-type="application/xhtml+xml"/>
    <item id="a2" href="article2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="a1"/>
    <itemref idref="a2"/>
  </spine>
</package>
""",
        )
        epub.writestr(
            "toc.ncx",
            """<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="s1" playOrder="1">
      <navLabel><text>Business</text></navLabel>
      <content src="article1.xhtml"/>
    </navPoint>
    <navPoint id="s2" playOrder="2">
      <navLabel><text>Culture</text></navLabel>
      <content src="article2.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
""",
        )
        epub.writestr("article1.xhtml", article_a)
        epub.writestr("article2.xhtml", article_b)


class WebAppTests(unittest.TestCase):
    def test_upload_job_processing_and_dashboard(self) -> None:
        root = Path.cwd() / "test-output" / "web-runtime"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        memory_conn.row_factory = sqlite3.Row
        try:
            settings = WebSettings(
                project_root=Path.cwd(),
                data_root=root / "data",
                uploads_root=root / "data" / "uploads",
                library_root=root / "data" / "library",
                packs_root=root / "data" / "study_packs",
                tracker_path=root / "data" / "progress" / "tracker.json",
                database_path=root / "data" / "app.db",
                templates_root=Path.cwd() / "src" / "epub_english_toolkit" / "web_templates",
                static_root=Path.cwd() / "src" / "epub_english_toolkit" / "web_static",
                default_mode="ielts",
                default_focus_topics="politics,business,culture",
                basic_auth_username="",
                basic_auth_password="",
            )
            with patch("epub_english_toolkit.web_db.connect", return_value=memory_conn):
                init_runtime(settings)

                epub_path = settings.uploads_root / "sample.epub"
                build_long_epub(epub_path)
                job_id = create_upload_job(
                    settings.database_path,
                    filename="sample.epub",
                    stored_path=str(epub_path),
                    mode="ielts",
                    focus_topics="business,culture",
                    start_date="2026-03-31",
                    main_count=2,
                    short_count=0,
                )
                process_upload_job(settings, job_id)

                job = get_upload_job(settings.database_path, job_id)
                self.assertIsNotNone(job)
                assert job is not None
                self.assertEqual(job["status"], "completed")
                self.assertTrue((settings.library_root / job["book_id"] / "book.json").exists())
                self.assertTrue((settings.packs_root / job["pack_id"] / "pack.json").exists())

                client = TestClient(create_app(settings))
                response = client.get("/dashboard")
                self.assertEqual(response.status_code, 200)
                self.assertIn("Your Learning Dashboard", response.text)
        finally:
            memory_conn.close()
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
