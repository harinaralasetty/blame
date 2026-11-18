"""Load every input path, then apply the checks that span files."""

from pathlib import Path
from typing import Iterable

from .formats import load_path
from .formats.inspect_json import inspect_records  # noqa: F401  (kept importable from here)
from .model import Record


def load_inputs(paths: Iterable[str]) -> tuple[list[Record], list[str]]:
    records = []
    warnings = []
    seen = set()
    judges = {}
    for path in paths:
        try:
            loaded, notes = load_path(Path(path))
            warnings.extend(f"{path}: {note}" for note in notes)
            for record in loaded:
                if record.record_id in seen:
                    warnings.append(f"{path}: duplicate record {record.record_id[:12]} ignored.")
                    continue
                if record.judge_run is not None:
                    key = record.judge_key + (record.judge_run,)
                    if key in judges and judges[key] != record.score:
                        raise ValueError("conflicting scores for the same output and judge_run")
                    judges[key] = record.score
                records.append(record)
                seen.add(record.record_id)
        except UnicodeDecodeError:
            raise  # As before the format split: a file that is not UTF-8 reports the codec error alone.
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
    if not records:
        raise ValueError("no scored records found")
    return records, warnings
