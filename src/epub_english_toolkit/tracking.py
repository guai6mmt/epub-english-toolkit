from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .storage import ensure_dir, read_json, write_json


DEFAULT_TRACKER = {
    "version": 1,
    "items": {},
}


def load_tracker(path: Path) -> dict[str, Any]:
    ensure_dir(path.parent)
    if not path.exists():
        write_json(path, DEFAULT_TRACKER)
        return {"version": 1, "items": {}}
    try:
        return read_json(path)
    except json.JSONDecodeError:
        raw = path.read_text(encoding="utf-8")
        decoder = json.JSONDecoder()
        payload, _ = decoder.raw_decode(raw.lstrip())
        write_json(path, payload)
        return payload


def save_tracker(path: Path, tracker: dict[str, Any]) -> None:
    write_json(path, tracker)


def get_status_map(path: Path) -> dict[str, Any]:
    tracker = load_tracker(path)
    return tracker.get("items", {})


def set_item_status(
    path: Path,
    item_id: str,
    status: str,
    *,
    kind: str | None = None,
    pack_id: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    with tracker_lock(path):
        tracker = load_tracker(path)
        items = tracker.setdefault("items", {})
        if status == "pending":
            items.pop(item_id, None)
        else:
            items[item_id] = {
                "status": status,
                "kind": kind or items.get(item_id, {}).get("kind", ""),
                "pack_id": pack_id or items.get(item_id, {}).get("pack_id", ""),
                "note": note,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        save_tracker(path, tracker)
        return items.get(item_id, {"status": "pending"})


def annotate_status(item_id: str, status_map: dict[str, Any]) -> dict[str, Any]:
    payload = status_map.get(item_id, {})
    return {
        "status": payload.get("status", "pending"),
        "completed_at": payload.get("completed_at", ""),
        "note": payload.get("note", ""),
    }


@contextmanager
def tracker_lock(path: Path, timeout_seconds: float = 5.0):
    lock_path = path.with_suffix(path.suffix + ".lock")
    ensure_dir(lock_path.parent)
    start = time.time()
    soft_locked = False
    fd: int | None = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if lock_path.exists() and (time.time() - lock_path.stat().st_mtime) > timeout_seconds:
                try:
                    os.unlink(lock_path)
                    continue
                except PermissionError:
                    soft_locked = True
            if time.time() - start > timeout_seconds:
                soft_locked = True
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        if not soft_locked and fd is not None:
            os.close(fd)
            for _ in range(5):
                try:
                    os.unlink(lock_path)
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.05)
