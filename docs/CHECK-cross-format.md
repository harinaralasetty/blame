# Independent check: feat/cross-format

Checked: branch `feat/cross-format` at `a82e9db` against `main` (`ce0a271`), 2026-11-18, Python 3.15.2, system `python3`, no installs, no network. Old and new code were run from `git archive` copies outside the repo.

## Verdict

**Fix first, but nothing blocks the 0.1.0 behaviour.** Backward compatibility holds exactly (byte-identical `labels.csv`, equal v1 JSON values, totals reproduce). No Python traceback was produced by any input I tried. The problems are all in the new readers and the new `by_task` text: seven should-fix items where the report states something the files do not support, or silently drops or double-counts data. Items 1 to 4 are the ones I would not merge without; 5 to 7 can be fixed or documented.

No blocker found.

## Findings

Reproductions use `B="python3 -m blame_cli"` run from a checkout. All were verified by running unless marked "read only".

### Should-fix

**1. SWE-bench: a stray `results.json` turns the parent directory into a "run" and the real result is lost.**
`blame_cli/formats/swebench.py:37-44` (`_is_run` accepts any directory that holds a `results.json`).
Input: `d/results.json` = `{"error_ids": []}`; `d/run1/m/i-1/report.json` = `{"i-1": {"resolved": false}}`; `d/run1/m/i-1/patch.diff`.
Command: `$B report d --out o` (exit 0).
Observed: one ungraded record with `task_id` "m", `model` "run1", `job_id` "d", label `unclassified_error` "no report.json". The graded instance `i-1` is not in the report. No warning.
Expected: `run1` read as the run (a `results.json` alone should not outrank a valid `report.json` one level deeper), or an error.

**2. Two gradings of one patch are counted as two attempts when the run directories share a name.**
`swebench.py:187-195` and `blame_cli/formats/harbor.py:204-220`: `job_id` is only the directory name.
Input: `p1/run/m/i-1/{report.json resolved false, patch.diff}` and `p2/run/m/i-1/{report.json resolved true, the same patch.diff}`.
Command: `$B report p1 p2 --out o` (also `p1/run p2/run`).
Observed: `scored_items` 2, `lost_items` 1, label `genuine_failure`, `judge_run` null, no warning. With the directories named `run1` and `run2` the same data gives `judge_unstable` 0.99.
Harbor analogue: `p1/job/t1__a` and `p2/job/t1__a` with the same `id`, rewards 0.0 and 1.0: both kept as separate scored attempts, no warning, although `docs/reference.md:108` says the first copy is kept with a warning.
Expected: same result whatever the run directories are called, or a warning that two inputs carry the same job name with different results.

**3. An attempt that was never graded is labelled `genuine_failure`.**
`harbor.py:164` (`kind = kind or "unknown"` keeps `agent`), `blame_cli/detectors.py:322` (default label for any record with no finding, including `score: null`).
Input (Harbor): a trial with `exception_info.exception_type: "AgentTimeoutError"` and no `verifier_result`. Generic: `{"task_id":"t","model":"m","run_id":"r","instruction":"i","rubric_item_id":"c","rubric_item_text":"x","output":"o","score":null,"judge_reasoning":"","error":"agent crashed","error_kind":"agent"}`.
Command: `$B report IN --out o`.
Observed: `ungraded_items` 1, verdict `genuine_failure` 0.50. The same happens for `policy_override.has_valid_reward: true` with `policy.has_valid_reward: false`, where the error text also contradicts itself ("policy_override has_valid_reward=true); Harbor does not count the recorded reward").
Expected: an ungraded attempt never gets the label whose name says the model failed; `unclassified_error` (or a distinct "ungraded" default) fits what the file records. `docs/reference.md:184` justifies the `agent` rule by "the harness counts that attempt as a valid failure", which is false when there is no score.

**4. `by_task[].reference` disagrees with the reference detectors.**
`blame_cli/reports.py:25-30,52` counts every scored reference record of the task; the detectors (`detectors.py:184-186,238-269`) leave out reference attempts with an excluded `error_kind`, an infra-rule match or another `task_version`.
Input (Harbor): one `oracle` trial with reward 0.0 and `exception_type: "ApiError"` plus `reward_valid: true`, and one failing candidate. Generic equivalents: a reference record with `score: 0` and `error: "boom"`; a reference record with `task_version: "v1"` beside a candidate with `"v2"`.
Observed: `by_task` says "passed 0 of 1 attempts" while no reference label fires and the verdict is `genuine_failure`. A reader sees "the reference failed" beside "no rule explains this".
Also: the count is of records, not attempts (a reference with three rubric items is "3 attempts").
Expected: the sentence counts the same attempts the rules use, or says how many were left out.

**5. `redact` damages patches and URLs.**
`blame_cli/formats/__init__.py:14`: the pattern matches `/home/` and `/Users/` anywhere, not only at the start of a path.
Reproduction: `python3 -c "from blame_cli.formats import redact; print(redact('diff --git a/src/home/views.py b/src/home/views.py')); print(redact('https://example.com/home/index.html'))"`.
Observed: `diff --git a/src~ b/src~` and `https://example.com~`.
Expected: repository paths such as `src/home/...` and URLs unchanged; only absolute home paths shortened. This changes the patch text shown as `output` for any repository with a `home` or `Users` directory (Django projects commonly have one). The `run_id` hash is taken from the raw file, so grouping is not affected.

**6. SWE-bench: a whitespace-only `patch.diff` is labelled `infra` 0.98; an empty patch listed in `results.json` is labelled `genuine_failure`.**
`detectors.py:38-51` (the 0.1.0 `empty_output` rule runs on any record with no `error_kind`), `swebench.py:142-144`.
Input: `run1/m/i-1/patch.diff` = `"  \n"`, `report.json` = `{"i-1": {"resolved": false}}`.
Observed: verdict `infra` 0.98. The same situation reported through `empty_patch_ids` gets `error_kind: "agent"` and `genuine_failure`.
Expected: one treatment for an empty patch; the harness does not call it an infrastructure failure.

**7. SWE-bench reader: wrong value types give a raw Python message, and one error path loses the explanation.**
- `swebench.py:66`: `tests_status.FAIL_TO_PASS = {"success": "abc", "failure": 7}` gives `blame: d: 'int' object is not iterable` (exit 2, no file named). A string value is silently iterated character by character. Expected: non-list values ignored or an error naming the file.
- `swebench.py:136,182`: `run1/results.json` with `error_ids` and no model directory, `$B report --format swebench run1`: "no readable SWE-bench result found"; the warning that ids could not be tied to a model is discarded. The recorded deviation "a run with only a summary can be read with `--format swebench`" is true only when a model directory exists.

### Nice-to-have

8. **`by_class` order changed.** v1 rows are no longer at indexes 0 to 4 (`judge_unstable` moved from 1 to 3). Values are equal by name. `docs/reference.md:139` says "schema 2 only adds keys"; add that row order changed.
9. **Mixed directory.** A directory holding both a Harbor trial and a SWE-bench run is read as Harbor; the SWE-bench data is ignored without a warning (`formats/__init__.py:30-36`).
10. **One bad Harbor trial aborts the job.** `agent_info: null`, numeric `task_name`, `exception_info` without a type, `model_info` without a name: exit 2 for the whole directory, while a non-JSON file is only skipped. Recorded deviation; inconsistent with "an unreadable result file is skipped". `exception_info: "boom"` (a string) is ignored and the trial reads as a clean failure (`harbor.py:86-91`).
11. **Corrupt `report.json` makes the instance vanish.** It is skipped with a warning and, because it is then in `seen`, its `error_ids` entry is not turned into an ungraded record (`swebench.py:168-172`; fixture instance `example__widgets-110`). A missing `report.json` gives an ungraded record. Recorded deviation.
12. **No cap on copied text.** A 3 MB exception message gives a 9 MB `report.json`/`report.html`; a 4 MB patch gives 8 MB each. Harbor test output is capped at 2,000 characters, error text and patches are not.
13. **`judge_unstable` 0.99 is the headline of an ungraded record** in a regrade group whose third run errored; its own `unclassified_error` is secondary.
14. **Strength depends on record shape.** Adding `"job_id":"j"` to two otherwise identical generic records lowers `item_everyone_loses` from 0.90 to 0.50 (`detectors.py:88-118`, `_v1_shaped`). Documented at `docs/reference.md:178`; it is a compatibility shim living in a detector.
15. **Symlinked run directory** is read as a second grading (`judge_run` 1 and 2, lost items doubled).
16. **Harbor trials without `id`** and the same trial name in two jobs are treated as one trial; the second is dropped with a warning even when rewards differ.
17. **Warning wording.** "run1/no results.json; ..." reads as a path (`swebench.py:123`). A directory holding only a truncated result gives "no reader recognises this directory" instead of naming the file.
18. **Non-UTF-8 JSONL** still reports the codec error without the file name (`inputs.py:42-43`, kept from 0.1.0 on purpose), while `docs/reference.md:15` says errors carry the input path.
19. **Docs drift.** `CHANGELOG.md:24` lists `--format auto|generic|inspect` (harbor and swebench missing). `docs/reference.md:33` still says "A nonempty error string indicates an infrastructure failure" without the `error_kind` exception. `REPORT.md:117` still shows "Ran 45 tests". `Makefile` `demo` does not build the two new demos that `.gitignore` names.
20. **Architecture notes.**
    - Import cycle inside the package: `formats/__init__.py:22` imports the readers at the bottom because they import `redact` from it. A `formats/_text.py` removes the cycle and the `noqa`.
    - `inputs.py:44` catches `TypeError`, `AttributeError` and `KeyError` and reports them as input errors. This is why finding 7 is not a traceback; it also hides real bugs in readers.
    - `inputs.py` is not a shim: it owns `load_inputs`, merge orchestration, de-duplication and cross-file checks. The only shim line is the `inspect_records` re-export (line 7).
    - `detectors.judge_unstable(record, peers)` is not used by `triage`.
    - `detect` then `load` parses an Inspect file twice.
    - `tests/test_golden.py:66` creates its temporary directory in the repository root during a test run.
21. **`.DS_Store`** is untracked in the repo root and not in `.gitignore`.

## What passed

Verified by running:

- **Backward compatibility.** `labels.csv` byte-identical old against new for `fixtures/synthetic.jsonl` (21 rows), `fixtures/inspect.json` (2 rows) and the local 3,000-record Arena-Hard file (1,826 rows). `report.json`: `items`, `scored_items`, `lost_items`, `lost_points`, `counting`, `confidence_note`, `warnings` equal; v1 `by_class` rows equal by name; v1 `by_model` keys equal.
  - Changed: `schema_version` 1 to 2; `by_class` row order (finding 8).
  - Added: top-level `ungraded_items`, `reference_items`, `by_task`; `by_class[].category` and `.ungraded_items`; six label keys and `ungraded_items` in each `by_model` row; six `by_class` rows.
  - Removed: none.
  - Markdown and HTML differ as documented (new columns, "Failed tasks", "rule strength").
- **Tests.** `make test` on a clean archive of HEAD: 129 run, OK, 1 skip (`test_golden.ArenaHardTotalsTests.test_published_totals_are_reproduced`, because `data/` is gitignored; it passes in the working copy). Base: 45, OK. `tests/golden/v1/*` equals what `ce0a271` produces.
- **Edits to old tests.** `tests/test_review_round1.py:56` compares through `Record.from_dict` instead of `asdict`: slightly weaker (no longer pins the JSON key set), covered by the byte-identical labels golden. `tests/test_workflow.py:30-31`: explicit mapping with zeros for the new labels, not weaker. Other old test files unchanged.
- **Counting.** For `synthetic`, `inspect`, `v2`, `harbor-job`, `swebench-eval` and all five together: lost and ungraded recomputed from `items` equal the headline numbers; `by_class` and `by_model` sums equal them per label; `by_task.labels` equals the count of matches. Harbor (7 scored, 6 lost, 5 ungraded, 3 reference) and SWE-bench (7, 6, 2, 2) recounted by hand from the raw fixture files. Outputs equal `tests/golden/*`.
- **Precedence.** One table, `blame_cli/model.py:18-30`; `labels.py`, `reports.py` and `detectors.py` derive from it; a label without a rule fails at import (`detectors.py:303`). No second ordering found by grep.
- **Docs commands.** Every `./blame`, `python3 -m blame_cli` and `make test` command in `README.md` and `docs/reference.md` ran from the archive with the stated result (36 scored, 21 lost for the demo; `report logs/evaluation` and `report run-a run-b` give equal items, different warning prefixes as documented). `label` and `score` work on Harbor and v2 input.
- **Honesty.** "unverified against real harness output" is in the README table, `docs/reference.md` (both mappings), `CHANGELOG.md`, `--help` and both module docstrings. The three fixture READMEs say hand-written. Version is 0.2.0 in `pyproject.toml` and `CHANGELOG.md`.
- **Robustness that held.** Empty directory, nested job parents, truncated JSON beside a good trial, bool/NaN/string/out-of-range rewards (ungraded, never scored), unlisted exception name (`unclassified_error` 0.40, never `infra`), non-UTF-8 test output and patches, all-`nop` job, forced wrong format, `resolved: "yes"`, bad `results.json`, path-like ids in `error_ids`, symlink loop, `.eval` file, conflicting `error_kind`, duplicate records.
- **Hygiene.** No personal paths, e-mail addresses, employer names or secrets in tracked files (only `/home/example` in fixtures and the redaction pattern). No caches or generated demo output tracked. Six commits, subjects 35 to 46 characters, each with a body and attribution line, authored with the personal address. `main` is still `ce0a271`. Working tree clean apart from the pre-existing untracked `.DS_Store` and this file.

Read only, not run: dependency direction (`formats -> model <- detectors <- reports <- cli` holds; `labels` imports only `model`); a fifth format costs one module, one `READERS` entry and docs (CLI choices derive from `FORMATS`).

Recorded deviations: acceptable except the three named above (summary-only run, finding 7; wrong-typed Harbor field aborts the job, finding 10; corrupt `report.json` skipped, finding 11) and the reference sentence (finding 4).

## Could not check

- **Real harness output.** No Harbor or SWE-bench run, package or network. Whether the field names and layout match is unknown. Two points from my own recollection, unverified, worth checking against the pinned SWE-bench commit before the reader is trusted: the harness, as I recall it, writes its run summary to the working directory as `<model>.<run_id>.json` rather than `<run_id>/results.json`, and I do not recall `infra_failure` or `infra_failure_reason` in `report.json`. The same caution applies to Harbor's `policy`, `policy_override` and `reward_valid` serialisation.
- **README quickstart** (`python3 -m venv`, `pip install .`) and the console script entry point: needs an install.
- **CI on Python 3.11 to 3.14**: only 3.15.2 was run locally; no remote, so no CI run exists.
- **Windows** paths and line endings.
- **Large inputs** beyond a few MB; performance was not measured.
