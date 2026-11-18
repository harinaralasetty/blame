# Changelog

Notable changes to `blame`. Versions follow `pyproject.toml`.

## Unreleased

- Input parsers moved into `blame_cli/formats/` (`generic`, `inspect_json`) behind a
  small registry; `blame_cli/inputs.py` keeps `load_inputs` and `inspect_records`.
- One `LABELS` table in `blame_cli/model.py` is now the only source of label
  precedence. Output for existing inputs is byte-identical to 0.1.0; golden files
  under `tests/golden/v1/` pin it.

## 0.1.0

- `blame report` reads generic JSONL and a subset of Inspect v2 text JSON and writes
  `report.json`, `report.md` and `report.html`.
- Four deterministic detectors (`infra`, `judge_unstable`, `item_everyone_loses`,
  `unstated_requirement`) and the default `genuine_failure`.
- `blame label` writes a labelling CSV; `blame score` reports precision and recall
  against human labels.
- `adapters/arena_hard.py` converts Arena-Hard v0.1 to generic JSONL for the study in
  `realdata/`.
