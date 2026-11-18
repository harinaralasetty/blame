"""Input formats. Each reader module turns one path into validated records.

A reader defines detect(path) -> bool and load(path) -> (records, warnings), and may
define merge(records) -> (records, warnings), applied once over all inputs of its format.
Readers import only the model, never detectors or reports.
"""

from pathlib import Path
import re

from ..model import Record


_HOME = re.compile(r"""(?:/Users/|/home/|[A-Za-z]:\\Users\\)[^/\\\s"'<>:;,)]+""")


def redact(text: str) -> str:
    """Replace home-directory prefixes with "~". Everything else is kept verbatim."""
    return _HOME.sub("~", text)


from . import generic, harbor, inspect_json  # noqa: E402  (readers import redact from this module)


# Detection order: the first reader whose detect() accepts the path wins.
READERS = {"harbor": harbor, "inspect": inspect_json, "generic": generic}
FORMATS = tuple(READERS)


def detect_format(path: Path) -> str:
    if path.is_dir():
        found = next((name for name, reader in READERS.items() if reader.detect(path)), None)
        if found is None:
            probes = "; ".join(reader.PROBE for reader in READERS.values() if hasattr(reader, "PROBE"))
            raise ValueError(f"no reader recognises this directory. Looked for: {probes}")
        return found
    if path.suffix == ".eval":
        raise ValueError("binary .eval files are unsupported; use Inspect text JSON")
    return next(name for name, reader in READERS.items() if reader.detect(path))


def load_path(path: Path, fmt: str = "auto") -> tuple[list[Record], list[str]]:
    return READERS[detect_format(path) if fmt == "auto" else fmt].load(path)
