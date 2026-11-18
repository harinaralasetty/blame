"""Input formats. Each reader module turns one path into validated records.

A reader defines detect(path) -> bool and load(path) -> (records, warnings).
Readers import only the model, never detectors or reports.
"""

from pathlib import Path

from ..model import Record
from . import generic, inspect_json


# Detection order: the first reader whose detect() accepts the path wins.
READERS = {"inspect": inspect_json, "generic": generic}
FORMATS = tuple(READERS)


def detect_format(path: Path) -> str:
    if path.is_dir():
        found = next((name for name, reader in READERS.items() if reader.detect(path)), None)
        if found is None:
            raise ValueError("no reader recognises this directory")
        return found
    if path.suffix == ".eval":
        raise ValueError("binary .eval files are unsupported; use Inspect text JSON")
    return next(name for name, reader in READERS.items() if reader.detect(path))


def load_path(path: Path, fmt: str = "auto") -> tuple[list[Record], list[str]]:
    return READERS[detect_format(path) if fmt == "auto" else fmt].load(path)
