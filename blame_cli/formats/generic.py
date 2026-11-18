"""Read generic JSONL: one record object per line."""

import json
from pathlib import Path

from ..model import Record


def detect(path: Path) -> bool:
    # The fallback for any file that no earlier format claimed.
    return path.is_file()


def load(path: Path) -> tuple[list[Record], list[str]]:
    content = path.read_text(encoding="utf-8")
    loaded = []
    for number, line in enumerate(content.split("\n"), 1):
        if not line.strip():
            continue
        try:
            loaded.append(Record.from_dict(json.loads(line)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"line {number}: {exc}") from exc
    return loaded, []
