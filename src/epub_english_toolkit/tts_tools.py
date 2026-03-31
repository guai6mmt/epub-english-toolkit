from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any

from .storage import ensure_dir, write_text


def export_tts_assets(
    pack: dict[str, Any],
    article_lookup: dict[str, dict[str, Any]],
    output_dir: Path,
    *,
    create_audio: bool = False,
    voice_name: str = "",
) -> list[dict[str, str]]:
    ensure_dir(output_dir)
    exported: list[dict[str, str]] = []
    for task in pack["weekly_plan"]:
        article = article_lookup[task["article_id"]]
        script_text = build_shadowing_script(task, article)
        filename = safe_filename(task["task_id"])
        text_path = output_dir / f"{filename}.txt"
        write_text(text_path, script_text)
        audio_path = output_dir / f"{filename}.wav"
        if create_audio:
            synthesize_wav(script_text, audio_path, voice_name=voice_name)
        exported.append(
            {
                "task_id": task["task_id"],
                "text_path": str(text_path),
                "audio_path": str(audio_path) if create_audio else "",
            }
        )
    return exported


def safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\\\|?*]+', "-", value)


def build_shadowing_script(task: dict[str, Any], article: dict[str, Any]) -> str:
    paragraphs = article.get("paragraphs", [])
    max_paragraphs = 3 if task["task_type"] == "fast_read" else 5
    selected = paragraphs[:max_paragraphs]
    lines = [
        task["title"],
        "",
        "Shadowing sentence:",
        task["speaking_task"]["shadowing_sentence"],
        "",
        "Listening passage:",
        "",
        *selected,
        "",
        "Retell prompt:",
        task["speaking_task"]["retell"],
    ]
    return "\n".join(lines).strip() + "\n"


def synthesize_wav(text: str, output_path: Path, *, voice_name: str = "") -> None:
    ensure_dir(output_path.parent)
    voice_line = f"$synth.SelectVoice('{voice_name}')" if voice_name else ""
    escaped_text = text.replace("`", "``").replace("'", "''")
    escaped_output = str(output_path).replace("`", "``").replace("'", "''")
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
{voice_line}
$synth.SetOutputToWaveFile('{escaped_output}')
$synth.Speak('{escaped_text}')
$synth.Dispose()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
    )
