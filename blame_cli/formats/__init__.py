"""Input formats. Each reader module turns one path into validated records.

A reader defines detect(path) -> bool and load(path) -> (records, warnings), and may
define merge(loaded) -> (records, warnings), applied once over the (path, records) pairs of all
inputs of its format.
Readers import only the model, never detectors or reports.
"""

from pathlib import Path

from ..model import Record
from . import generic, harbor, inspect_json, swebench
from ._text import redact  # noqa: F401  (part of this package's interface)


# Detection order: the first reader whose detect() accepts the path wins.
READERS = {"harbor": harbor, "swebench": swebench, "inspect": inspect_json, "generic": generic}
FORMATS = tuple(READERS)


def detect_format(path: Path) -> str:
    if path.is_dir():
        found = next((name for name, reader in READERS.items() if reader.detect(path)), None)
        if found is None:
            probes = "; ".join(reader.PROBE for reader in READERS.values() if hasattr(reader, "PROBE"))
            near = sorted(file.relative_to(path).as_posix() for depth in range(4) for name in ("result.json", "report.json")
                          for file in path.glob("*/" * depth + name))
            hint = f" Found {near[0]}, which could not be read as either." if near else ""
            raise ValueError(f"no reader recognises this directory. Looked for: {probes}.{hint}")
        return found
    if path.suffix == ".eval":
        raise ValueError("binary .eval files are unsupported; use Inspect text JSON")
    return next(name for name, reader in READERS.items() if reader.detect(path))


def load_path(path: Path, fmt: str = "auto") -> tuple[list[Record], list[str]]:
    return READERS[detect_format(path) if fmt == "auto" else fmt].load(path)
