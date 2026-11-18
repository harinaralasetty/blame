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
- Six new labels, eleven in all: `setup_error`, `grader_error`, `reference_flaky`,
  `reference_fails`, `attempts_flip`, `unclassified_error`. `by_class`, each
  `by_model` row and the `blame score` output grow by these six keys; `human_label`
  accepts them and 0.1.0 label files still score.
- Behaviour change: an input with repeated runs of one system on a task, including
  Inspect logs with epochs (`run_id/epoch-N`), can now get `attempts_flip` as the
  verdict where 0.1.0 said `genuine_failure`.
- A record with `error_kind` set is labelled from that class (`infra` at strength
  0.80) and the 0.1.0 "any error is infra" rule no longer applies to it.
- `item_everyone_loses` counts systems (agent and model), ignores ungraded and
  excluded attempts, abstains across task versions, and for records with optional
  keys scales its strength with the number of systems. Unchanged for 0.1.0 inputs.
- `fixtures/v2.jsonl` exercises every label; goldens in `tests/golden/v2.report.*`
  are rewritten only with `UPDATE_GOLDEN=1 make test`.
- New reader `harbor` (`--format harbor`, or detected for a directory): reads Harbor
  trial directories, one record per trial, with the reference agent `oracle`, the
  harness error class from a fixed name table and ungraded trials. It is unverified
  against real harness output: written from the Harbor source, tested on the
  hand-written `fixtures/harbor-job` only. Paths under a home directory in copied
  text are shortened to `~`.
- A directory as `IN` is no longer always an error; a directory no reader
  recognises is still one, and the message says what was looked for.

## 0.1.0

- `blame report` reads generic JSONL and a subset of Inspect v2 text JSON and writes
  `report.json`, `report.md` and `report.html`.
- Four deterministic detectors (`infra`, `judge_unstable`, `item_everyone_loses`,
  `unstated_requirement`) and the default `genuine_failure`.
- `blame label` writes a labelling CSV; `blame score` reports precision and recall
  against human labels.
- `adapters/arena_hard.py` converts Arena-Hard v0.1 to generic JSONL for the study in
  `realdata/`.
