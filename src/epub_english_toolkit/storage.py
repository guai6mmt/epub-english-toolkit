from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    ensure_dir(path.parent)
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    temp_file = Path(temp_path)
    try:
        with open(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        try:
            temp_file.replace(path)
        except PermissionError:
            path.write_text(content, encoding="utf-8", newline="\n")
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink(missing_ok=True)
            except PermissionError:
                pass
