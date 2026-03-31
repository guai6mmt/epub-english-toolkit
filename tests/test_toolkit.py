from __future__ import annotations

import json
import shutil
import unittest
from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from epub_english_toolkit.epub_parser import import_epub
from epub_english_toolkit.integrations import export_anki, export_notion
from epub_english_toolkit.markdown_export import export_daily_markdown, export_pack_markdown
from epub_english_toolkit.reporting import build_daily_plan, build_progress_report
from epub_english_toolkit.study_pack import build_study_pack
from epub_english_toolkit.tracking import get_status_map, set_item_status
from epub_english_toolkit.tts_tools import export_tts_assets


ARTICLE_A = """
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>Energy policy is reshaping cities</h1>
<p>Governments are investing in transport, housing and power grids as energy prices rise across the world.</p>
<p>Supporters say faster reform can protect growth, while critics warn that rushed plans may create new inequalities.</p>
<p>For English learners, the article offers formal linking language, policy vocabulary and clear cause-and-effect structure.</p>
<p>These features make it useful for IELTS writing and speaking practice.</p>
<p>City leaders also have to explain why short-term disruption may be necessary if cleaner systems are to work in the future.</p>
<p>That creates a useful language pattern for learners: presenting a problem, weighing trade-offs and reaching a cautious judgement.</p>
<p>Analysts note that infrastructure stories often combine economics, politics and public communication, which makes them especially rich input.</p>
<p>Readers can therefore practise summarising evidence, identifying assumptions and producing their own response under time pressure.</p>
</body></html>
"""

ARTICLE_B = """
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>Why small museums are changing tourism</h1>
<p>Independent museums are drawing visitors who want slower travel and stronger local identity.</p>
<p>The movement has grown because travellers now value authentic stories, regional food and community events.</p>
<p>Writers often compare the economic benefits with the risk of turning culture into a marketing product.</p>
<p>The topic is especially useful for culture-heavy IELTS speaking questions.</p>
<p>Some curators worry that local traditions can become performance rather than lived experience once visitor numbers rise too quickly.</p>
<p>Others argue that careful tourism gives communities revenue, confidence and a reason to preserve regional memory.</p>
<p>The tension between cultural protection and commercial opportunity appears often in international journalism and exam discussion.</p>
<p>That makes the article a good source for vocabulary about heritage, identity, authenticity and public policy.</p>
</body></html>
"""


def build_sample_epub(target: Path) -> None:
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
    <dc:title>Sample Weekly</dc:title>
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
        epub.writestr("article1.xhtml", ARTICLE_A)
        epub.writestr("article2.xhtml", ARTICLE_B)


class ToolkitTests(unittest.TestCase):
    def test_end_to_end_exports_and_tracking(self) -> None:
        temp_root = Path.cwd() / "test-output"
        temp_root.mkdir(exist_ok=True)
        temp_dir = temp_root / "runtime"
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            root = temp_dir
            epub_path = root / "sample.epub"
            build_sample_epub(epub_path)

            book, articles = import_epub(str(epub_path))
            self.assertEqual(book.book_id, "sample-weekly")
            self.assertGreaterEqual(len(articles), 2)
            self.assertTrue(all(article.difficulty_level for article in articles))
            for article in articles:
                article.word_count = max(article.word_count, 220)
                article.reading_minutes = max(article.reading_minutes, 1)

            pack = build_study_pack(
                book=book,
                articles=articles,
                start_date=date(2026, 3, 31),
                focus_topics=["business", "culture"],
                main_count=0,
                short_count=2,
                mode="ielts",
            )
            pack_dict = pack.to_dict()
            self.assertEqual(pack_dict["mode"], "ielts")
            self.assertIn("task_id", pack_dict["weekly_plan"][0])
            self.assertIn("task2_prompt", pack_dict["weekly_plan"][0]["writing_task"])

            tracker_path = root / "tracker.json"
            first_task_id = pack_dict["weekly_plan"][0]["task_id"]
            set_item_status(tracker_path, first_task_id, "completed", kind="study", pack_id=pack.pack_id)
            status_map = get_status_map(tracker_path)

            plan = build_daily_plan([pack], date(2026, 3, 31), status_map)
            self.assertEqual(plan["totals"]["completed_study_tasks"], 1)

            report = build_progress_report([pack], status_map)
            self.assertEqual(report["completed_study_tasks"], 1)

            md_pack = root / "pack.md"
            export_pack_markdown(pack_dict, md_pack)
            self.assertTrue(md_pack.exists())

            md_daily = root / "daily.md"
            export_daily_markdown(plan, md_daily)
            self.assertTrue(md_daily.exists())

            anki_path = root / "anki.tsv"
            export_anki(pack_dict, anki_path)
            self.assertTrue(anki_path.exists())

            notion_path = root / "notion.csv"
            export_notion(pack_dict, notion_path)
            self.assertTrue(notion_path.exists())

            article_lookup = {article.article_id: article.to_dict() for article in articles}
            tts_assets = export_tts_assets(pack_dict, article_lookup, root / "tts", create_audio=False)
            self.assertEqual(len(tts_assets), len(pack_dict["weekly_plan"]))
            self.assertTrue(Path(tts_assets[0]["text_path"]).exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
