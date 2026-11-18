# Changelog

Notable changes to `blame`. Versions follow `pyproject.toml`.

## Unreleased

- Input parsers moved into `blame_cli/formats/` (`generic`, `inspect_json`) behind a
  small registry; `blame_cli/inputs.py` keeps `load_inputs` and `inspect_records`.
- One `LABELS` table in `blame_cli/model.py` is now the only source of label
  precedence. Golden files under `tests/golden/v1/` pin the 0.1.0 output.
- Generic JSONL reads five optional keys: `agent`, `role`, `error_kind`,
  `task_version`, `job_id`. `score` may be `null` when `error` is set; such a record
  is listed as ungraded. Records without these keys keep their 0.1.0 record IDs and
  `labels.csv` rows.
- `report.json` is `schema_version: 2`. New keys: `ungraded_items`,
  `reference_items`, `by_task`, `by_class[].category`, and `ungraded_items` in each
  `by_class` and `by_model` row. Values 0.1.0 reported are unchanged for existing
  inputs.
- Markdown and HTML reports gain a "Failed tasks" section, group by system (agent
  and model) and print `confidence` as "rule strength".
- `report` and `label` accept `--format auto|generic|inspect`.

## 0.1.0

- `blame report` reads generic JSONL and a subset of Inspect v2 text JSON and writes
  `report.json`, `report.md` and `report.html`.
- Four deterministic detectors (`infra`, `judge_unstable`, `item_everyone_loses`,
  `unstated_requirement`) and the default `genuine_failure`.
- `blame label` writes a labelling CSV; `blame score` reports precision and recall
  against human labels.
- `adapters/arena_hard.py` converts Arena-Hard v0.1 to generic JSONL for the study in
  `realdata/`.
