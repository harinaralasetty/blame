# Review of PLAN-cross-format.md (v0.2 plan)

Reviewed against `main` at `ce0a271` on 2026-11-18. Independent review; no code or plan text was changed.

## How this was checked

- Baseline: `PYTHONDONTWRITEBYTECODE=1 make test` gives `Ran 45 tests in 0.498s, OK` on Python 3.15.2. The plan's count is right; `realdata/FINDINGS.md:235` is stale as the plan says.
- Every file and line reference in plan section 1 (P1 to P5) was opened and is accurate.
- A throwaway simulation of the planned `attempts_flip` rule was run over `fixtures/synthetic.jsonl`, `fixtures/inspect.json` and the local Arena-Hard `generic.jsonl` (results in finding 14).
- Upstream sources were read at the commits the plan cites, read-only, from the public raw and API endpoints:
  - `harbor-framework/harbor@3ee9f53e` (Apache-2.0): `models/trial/result.py`, `models/trial/paths.py`, `trial/error_policy.py`, `trial/trial.py`, `trial/multi_step.py`, `models/verifier/result.py`, `analyze/analyzer.py`, `job.py`, and the full repo tree.
  - `SWE-bench/SWE-bench@02e7a74f` (MIT): `harness/grading.py`, `harness/run_evaluation.py`, `harness/reporting.py`, `harness/infra_failure.py`, `harness/utils.py`, `harness/constants/__init__.py`.
  - `SWE-bench/experiments@40f164d5`: README, tree, licence lookup.
  - `UKGovernmentBEIS/inspect_ai@8012060c`: `log/_log.py`, `scorer/_metric.py`.
- Not checked: no pydantic model was executed and no real Harbor `result.json` or SWE-bench run directory was produced, so serialised shapes are verified by reading source only. Inspect `EvalError.message` and `ModelOutput.completion` (used by today's reader) were not re-read at the pinned commit.

Severity: **blocker** = building from the plan as written produces a wrong verdict, a broken acceptance check or an unverifiable release. **should-fix** = wrong or misleading in a realistic case, cheap to fix in the plan. **nice-to-have** = scope or polish.

## Findings

### 1. Blocker. An unclassified error becomes an `infra` headline that outranks everything (sections 3, 5, 10)

Plan: `error_kind == "unknown"` fires `infra` at 0.60; the headline is the first finding in `LABELS` order, and confidence plays no part in precedence.

Failure scenario: a SWE-bench instance whose model patch imports a missing module. The harness regex `missing_module` (`infra_failure.py`, ambiguous tier) sets `infra_failure_reason` with `infra_failure: false`. Plan maps that to `unknown`, the detector emits `infra` at 0.60, and because `infra` is first in precedence the headline says infrastructure for what is a model bug. If the `gold` run failed on the same instance, `reference_fails` at 0.95 is pushed to `matches` behind a 0.60 guess. Worse, section 5 excludes every attempt "that carries an `infra` finding" from cross-attempt comparisons, so these attempts also drop out of `item_everyone_loses`, `reference_*` and `attempts_flip`.

Change: `unknown` must never produce `infra`. Give it its own label placed just above `genuine_failure` (for example `unclassified_error`, category unexplained, with the raw error as evidence), or fold it into the `genuine_failure` evidence. Only `error_kind == "infra"` (and the v1 `None` rule) may fire `infra`, and only those attempts are excluded from cross-attempt comparisons. Rewrite the section 10 mitigation line, which currently promises "never `infra` at high confidence" while still awarding the `infra` headline.

### 2. Blocker. The Harbor error rule gives two different verdicts for the same exception, and contradicts Harbor's own default (section 4 Harbor, section 10)

Verified: `error_policy.py` defines `UNKNOWN_ERROR_POLICY = ErrorPolicy(should_retry=True, should_grade=True, has_valid_reward=True)`. Harbor treats an unlisted exception as a valid reward.

Failure scenario: a trial ends with a custom `MyToolCrashError`. With the serialised `policy` present, the plan's rule reads `has_valid_reward == true` and maps to `agent`. From a file without the `policy` key (older Harbor, hand-edited, or a fork) the same exception maps to `unknown` and then `infra` 0.60. Same input fact, two verdicts, decided by file age.

A second problem in the same row: "other listed names -> `infra`" puts user-configuration and cancellation errors under infrastructure (`AgentAuthenticationError`, `ModelNotFoundError`, `BudgetExceededError`, `BadRequestError`, `CancelledError`, `UnsupportedModelParametersError`). And `has_valid_reward` is a scoring policy, not a cause: `AgentTimeoutError` is counted valid by Harbor but can be caused by a slow sandbox; `MemoryLimitExceededError` is counted invalid but can be caused by the agent.

Change (this resolves the conflict the plan leaves open):
1. Classify by the pinned name table first. The table is the tool's own statement and is the same for every file.
2. Honour an explicit `policy_override` when present, and record that in evidence.
3. A name not in the table is `unknown` whether or not a serialised `policy` exists. Put Harbor's `has_valid_reward` value in the evidence, do not turn it into a kind.
4. Use the serialised `policy` only to decide whether the reward is usable (`score` vs `None`), which is what it means.
5. Split the invalid-reward names into `infra` (sandbox, network, provider 5xx, rate limit) and a new kind `config` or `cancelled` (auth, model not found, bad request, budget, cancelled), or map the second group to `unknown`. Do not call them infra.
6. State in the docs that `agent` means "Harbor counts this reward", not "the agent caused it".

### 3. Blocker. The SWE-bench reader cannot see the three most common non-test failures (section 4 SWE-bench, section 10)

Verified at the pinned commit:
- Empty or `None` patches are filtered out before any instance runs (`run_evaluation.py:627-638`) and `reporting.py` skips them, so they have no instance directory and no `report.json`. The plan's `patch_is_None == true` row is effectively dead in the harness layout.
- A patch that fails to apply raises `EvaluationError` (`run_evaluation.py:332-335`); no `report.json` is written. The instance lands in `error_ids`.
- `reporting.py:make_run_report` writes `logs/evaluation/<run_id>/results.json` with `schema_version: 2`, `empty_patch_ids`, `error_ids`, `incomplete_ids`, `infra_failure_ids`, `ambiguous_failure_ids`, `failure_reasons`, `submitted_ids`, `resolved_ids`, `unresolved_ids`. The plan does not know this file exists; section 10 only recalls an older `<model>.<run_id>.json` name and says the summary is ignored.

Failure scenario: a harness run of 300 instances with 40 empty patches and 25 apply failures. `blame report logs/evaluation/run1` reports 235 scored attempts and silently drops 65 failures, so the lost count disagrees with the harness's own summary on day one. In the submission layout the 25 apply failures appear as "prediction present, no report.json" -> `unknown` -> `infra` (finding 1), blaming infrastructure for a malformed model patch.

Change: read the run-level `results.json` when present and treat it as the list of submitted instances: `empty_patch_ids` -> `agent` "empty patch"; `error_ids` without a report -> a record with `score=None` and the last lines of `run_instance.log` as the error, kind `unknown` (not infra); `incomplete_ids` -> warning with a count. When no summary and no `all_preds.jsonl` is present, emit a warning that empty patches and harness errors are not visible. Add both cases to the fixture. Make sure format detection does not confuse this `results.json` with anything else, and correct the section 10 note.

### 4. Blocker. SWE-bench `run_id` from the command-line directory name is wrong in three ordinary cases (section 4 SWE-bench, section 3)

- `blame report .` gives `Path(".").name == ""`, which fails the non-empty `run_id` rule. The reader must `resolve()` first, and that then leaks a host directory name into the report.
- `blame report logs/evaluation` holds several harness runs. All get `run_id="evaluation"`, so two gradings of the same instance and model share one `attempt_key` with possibly different scores and no `judge_run` to tell them apart.
- Two harness runs over the same predictions are re-gradings of one output, the cleanest grader-flake signal SWE-bench offers. Under the plan they are two attempts, so a flip is labelled `attempts_flip` 0.40 "unexplained" although section 5 itself says a re-graded identical output points at the grader.

Change: take `run_id` from the layout's `<run_id>` path component in the harness layout and from the entry directory name in the submission layout; never from the raw CLI argument. Read `patch.diff` (written beside every `report.json`, `run_evaluation.py:290-291`) as `output`. When two harness runs carry the same patch for one instance and model, emit them as one attempt with `judge_run` 1..n so the existing `judge_unstable` detector handles the flip. Take `model` from `all_preds.jsonl` `model_name_or_path` when available, falling back to the directory name.

### 5. Blocker. "Existing tests pass unmodified" and "v2 is a superset of v1" are false as written (sections 2, 6, 7, 8)

Concrete breaks:
- `tests/test_workflow.py:30-31` asserts `{row["class"]: row["lost_items"] for row in report["by_class"]} == dict(zip(CLASSES, (4, 1, 6, 4, 6)))`. With nine `CLASSES` in the new order the right side pairs the counts with the first five new names (`infra, grader_error, judge_unstable, reference_flaky, reference_fails`) and the left side has nine rows. The test fails at M5.
- `tests/test_detectors.py` calls `item_everyone_loses(record, peers)` and `judge_unstable(record, peers)` directly. Section 5 says all detectors take `(record, index, reasoner)`. That breaks at M1, the "behaviour identical" milestone.
- `tests/test_review_round1.py:56` compares `asdict(record)` with stored JSON; the plan replaces `asdict` with `record_dict` in report output without saying which the item `record` uses.
- `by_class` is a list that grows from five rows to nine; each `by_model` row gains four keys; `blame score` output (`per_detector`, `per_verdict`) gains four keys. None of these are listed among the "additive keys" in section 6.
- `scored_items = len(records)` and the `counting` sentence ("Each scored observation below 1 is a lost item") become untrue once `score=None` records exist. The plan defines `lost_points` and `ungraded_items` but not `scored_items` or `lost_items`.
- `by_model` groups by `record.model`. For Harbor that is `""` for the oracle and identical for two agents on the same model.
- `docs/reference.md` says "one of the five class names".

Change: say plainly that schema 2 is a compatible extension for v1 inputs, not a superset, and define the v1 projection exactly: for a v1 input, `by_class` filtered to the five v1 names in v1 order equals the v1 golden; `by_model` rows compared on v1 keys; items compared on v1 keys. Keep the two-argument detector functions as thin wrappers so M1 really leaves tests untouched. List the tests that will be edited in M5 (`test_workflow.py:30-31` at least) and why. Define: `scored_items` counts records with a score, `ungraded_items` counts `score=None`, `lost_items` counts scored records below 1, and decide whether ungraded records appear in the drill-down (they should, they carry the error). Group the per-system table by `system` and keep a `model` key for v1.

### 6. Blocker. No real file of either new format is required before release (sections 7, 8, 10)

The plan admits no real Harbor `result.json` was examined and that the two computed fields are assumed to serialise. All fixtures are hand-written from the same reading of the source that produced the mapping, so the tests can only confirm the author's belief about the format. A wrong belief ships green.

What was confirmed by source reading: Harbor writes `trial_dir/result.json` via `model_dump_json(indent=4)` with no exclude (`trial.py:677`), and Harbor's own analyzer reads the same name, so `result.json` is right and the `results.json` docstring is the mistake. Pydantic v2 includes computed fields in that call, so `reward_valid` and `exception_info.policy` should be present. That is still inference.

Change: add an acceptance check to M3 and M4 that each reader has been run on at least one real, harness-produced input, with the command, harness version and outcome recorded in the commit message or the fixture README. Sources:
- Harbor: the repo tree at the pinned commit contains no sample `result.json` (4,941 paths checked), so one must be generated: a single oracle or `nop` trial on a small example task (needs Docker, one container, within the machine limits). The generated file is the project's own output and may be committed after path and config scrubbing (finding 11).
- SWE-bench: run the harness with `predictions_path gold` on one or two instances; the output is the project's own. Alternatively download one entry's logs from a submitter repo or the public submissions bucket for a local check only, without committing it.
- `SWE-bench/experiments` has no licence file (the GitHub licence endpoint returns Not Found). Do not copy its data into `realdata/`. M7 may keep derived counts with provenance, or needs permission first.

If generating a real sample is not possible for a format, ship that format marked "experimental, not tested on harness output" in README and `--help`.

### 7. Should-fix. One record per Harbor reward key inflates and misreads results (section 4 Harbor)

`rewards` is `dict[str, float | int]`, unbounded. Harbor's own pass test is `rewards.get("reward", 0) == 1.0 and reward_valid` (`analyze/analyzer.py:63-68`). A verifier that writes `{"reward": 0, "tests_passed": 3, "runtime_s": 41.2}` yields, under the plan, one failed record, one skipped-with-warning record and another skipped record per trial, and a verifier writing `{"reward": 1, "style": 0.4}` reports a lost item for a trial Harbor calls passed. If every value is outside [0,1], no record is produced and the trial vanishes, since "no rewards at all -> score None" does not cover it.

Change: emit one record per trial with `rubric_item_id="reward"` from the `reward` key. If `reward` is absent and exactly one key exists, use it. Otherwise emit `score=None` with an explanatory error and list the keys in `judge_reasoning`. Put other keys in the grader note. Extra-key records can be an opt-in later.

### 8. Should-fix. The multi-step row is dead or self-contradictory (section 4 Harbor)

`multi_step.py:92` sets the trial-level `verifier_result` from the steps (last step, or per-key mean), so trial-level rewards normally exist for multi-step trials. When they are absent, `reward_valid` is false, and the row below sets `score=None` for the same records the step row just scored.

Change: cut `step:<name>/reward:<key>` records from 0.2. Keep reading `step_results[].exception_info` for the error text only.

### 9. Should-fix. Prefixing `task_id` with `source` breaks the oracle join (section 4 Harbor)

`source` is the dataset name from the task config and is `None` for a local path. An oracle run from a local checkout gets `task_id="fix-bug"`; agent runs from the registry get `task_id="my-dataset/fix-bug"`. They never share an `item_key`, so `reference_fails` and `reference_flaky` never fire in the most likely workflow (author validates locally, agents run from the dataset).

Change: `task_id = task_name` (already `org/name` for package tasks). Use `task_checksum` as the guard, and warn when one `task_id` appears with more than one checksum. Keep `source` out of the key.

### 10. Should-fix. Harbor detection and dedupe gaps (section 4 auto-detection)

- Passing a parent `jobs/` directory: `DIR/*/result.json` are job-level results (no `trial_name`), so detection falls through to the SWE-bench probe and then errors, although the input is plainly Harbor. Probe one level deeper or raise "this looks like a directory of Harbor jobs; pass the job directories".
- Passing the same job twice under different parent names, or a copy, duplicates every attempt because `run_id` is `parent/trial_name`. `TrialResult.id` is a UUID: dedupe on it.
- Retried trials reuse the trial name and the earlier attempt is removed, so "attempts" in a job are distinct trials, never retries. Say so in the docs so nobody reads `attempts_flip` as retry behaviour.
- `--format` is one flag for all `IN...`; with mixed inputs the user cannot force one path. Document that forcing applies to every input.

### 11. Should-fix. The privacy promise cannot be kept as worded (section 4 contract, M3 check)

The contract says a reader never copies absolute host paths. The same table copies `exception_message` and the last 2,000 characters of `verifier/test-stdout.txt`; both routinely contain absolute paths, and tracebacks or provider errors can contain environment values. `trial_uri` is a `file://` URI of the host path. The M3 check "report contains no absolute path" passes on a hand-written fixture and fails on real output.

Change: narrow the promise to "never reads `config`, `trial_uri` or `exception_traceback`", and either redact home-directory prefixes in copied text or state in README that error messages and test output are copied verbatim and reports should be reviewed before sharing. Add a fixture trial whose message contains a path and assert the documented behaviour.

### 12. Should-fix. SWE-bench `infra_failure` is a regex heuristic, not a harness fact (sections 4, 5)

`infra_failure.py` calls itself advisory. The environment tier includes `out_of_memory` (`Cannot allocate memory|OutOfMemoryError|^Killed$`) and `network_unreachable`; a model patch that allocates without bound, or a test that the patch makes hang or fetch a host, triggers them. The plan gives these `infra` at 0.97, close to the v1 rule's 0.99 for an explicit harness error.

Change: for SWE-bench use a lower fixed strength (0.75 is defensible) and put the reason name in the evidence with the words "log pattern match". Reserve 0.97 for formats where the harness itself raised a typed infrastructure exception.

Related naming trap: `patch_successfully_applied` is set true only after parseable test output was found (`grading.py`), so `false` covers apply failure, reset failure, test errors, timeouts and missing markers. The `judge_reasoning` summary must say "no parseable test output" and not "patch failed to apply".

### 13. Should-fix. Reference and cohort detectors claim more than the evidence (section 5)

- `reference_fails` at 0.95 fires on a single failed oracle attempt with no pass. One run cannot tell a broken task from a flaky one. Use 0.95 only with two or more reference failures; a single failure gets a lower value (0.75) and evidence "1 reference attempt".
- The version guard passes when both versions are unset, which is always the case for SWE-bench. A `gold` run on another dataset revision then labels every candidate failure `reference_fails`. Keep the rule but lower the strength when no version is available and say "task version not available" in the evidence.
- Category `test` for `reference_fails` asserts the test is the broken part; the plan's own false-positive column says the reference may be. Name the category `task`.
- `item_everyone_loses` at 0.90 with a cohort of two weak agents on a hard task is the standard false positive, and open question 5 proposes keeping 0.90. For v1 data keep it. For records with `agent` set (new formats), scale by cohort: 2 systems 0.50, 3 to 4 systems 0.70, 5 or more 0.90, and always show the system count.
- Both reference labels are facts about the task. They will be the headline on every candidate failure of that task, including real model failures. The per-task table must say that, and `by_task.labels` should count findings (all `matches`), not only headlines, or a coexisting judge issue and model bug collapse into one label at the task level.
- An oracle attempt hit by infra is excluded (good); state explicitly that excluded reference attempts count as "no reference evidence", not as failures.

### 14. Should-fix. `attempts_flip` backwards compatibility: no published number changes, but say why (sections 6, 7)

Simulated on current data: `fixtures/synthetic.jsonl` (36 scored, 21 lost, classes 4/1/6/4/6) has no `(task, item, model)` group with two `run_id`s; `fixtures/inspect.json` has none; Arena-Hard `generic.jsonl` reproduces 3000 / 1826 / 1609 and 606 / 204 / 1016, with 1,500 groups and none having two `run_id`s. So `attempts_flip` changes zero headlines, no golden report, no `handcheck.csv` verdict, and `summarize.py` (which selects by `judge_unstable` and `item_everyone_loses` and checks record ids) is unaffected.

It does change any real Inspect log with epochs (`run_id/epoch-N`) and any generic file with repeated runs. That is the intended behaviour change; the changelog entry should name Inspect epochs explicitly. Also add the simulation as a test: "no v1 fixture or study input has a group that can trigger `attempts_flip`", so the claim stays checked.

The Arena-Hard check depends on a gitignored local file. Make the test skip with a visible message when the file is absent and state in the plan that CI does not cover it.

### 15. Should-fix. Wording rules for the report and docs (sections 5, 6, 9)

The "cannot support" list in section 5 is good and must be enforced in output. Rules to add:
- Never write "broken test", "bad task", "flaky grader" or "model at fault" as a statement. Each label sentence starts from the observed fact: "No supplied system scored above zero (N systems)", "The reference solution did not pass in M of M attempts", "This system passed K of N attempts".
- Every `next_step` is an instruction to check, not a conclusion: "Rerun the reference before scoring systems on this task", not "Fix the task".
- Confidence is shown as "rule strength" with a one-line legend, never as a probability or percentage of being right.
- Any label derived from a harness heuristic names the heuristic ("SWE-bench log pattern", "Harbor error policy").
- The per-task table header carries the cohort: systems attempted and whether a reference run was supplied. With no reference run, print "no reference run supplied" instead of leaving the cell empty.
- README must not say the tool "finds broken tasks" or "separates model errors from eval errors" for the new formats until a real case study exists. Say it "sorts failed attempts by what the result files record".
- For Harbor, mention `harbor analyze` and state the difference in one sentence.

### 16. Should-fix. M1 is not behaviour-identical as scoped, and its check is partly uncheckable (section 8)

M1 bundles a file move, a registry, a new precedence table, a new index and changed detector signatures. With the signature change, the 45 tests do not pass unmodified (finding 5). `make demo` byte-identity is a good check; add the three items that make it trustworthy: capture the "before" copy from a clean checkout of `ce0a271`, compare `demo/` and `demo-inspect/` with `diff -r`, and also compare `labels.csv` from `blame label`. The Arena-Hard check is local-only.

Change: M1 = move parsers verbatim, add the registry and shim, `LABELS` table with five labels, goldens, CHANGELOG, test count. Move `Index` and the new detector signature to M5 where they are needed, keeping the old function names as wrappers. That makes M1 a pure move that the existing suite proves.

### 17. Should-fix. Flat `Record` is defensible; `run_id` carrying job and attempt is debt that should be bounded now (section 3)

Flat is the right call for 0.2: every detector groups by key and the label files depend on `record_id`. The weak part is `run_id` as an opaque string holding "job/trial". Concrete ambiguity: nothing in the model says which attempts belong to one job, so "the reference from this job" cannot be told from "a reference from last month", and the SWE-bench cases in finding 4 follow from the same gap. Shared per-attempt facts (`error`, `error_kind`) are repeated on every record of the attempt and can disagree.

Change: add one optional v2 field `job_id: str | None` (Harbor job directory name, SWE-bench harness run id, Inspect eval run id) and keep `run_id` as the attempt within it. It costs one field now and avoids parsing a slash-separated string later. `validate` should reject records sharing an `attempt_key` with different `error_kind`.

### 18. Nice-to-have. Cuts (sections 3, 4, 5, 8)

- `role="noop"`: parsed, used by no detector. Cut until a detector needs it; map `nop` to `candidate` with a warning, or skip it.
- Harbor step records (finding 8) and extra reward keys (finding 7).
- `LabelInfo.next_step` rendered in three places: keep it in the per-task table only.
- M7: cut from the 0.2 plan; it has a licence problem (finding 6) and is not needed for release.
- Consider shipping Harbor first and SWE-bench in 0.2.1, or the reverse. Two new formats, four new detectors and a schema bump in one release is the largest risk in the plan; each format already needs its own real-sample check.
- SWE-bench submission layout can wait if the harness layout plus `results.json` is done properly.

### 19. Nice-to-have. Smaller items

- `detectors.infra` calls `record.output.strip()`; with `output=None` it raises. The plan says "None-safe detectors" in M2; name this line so it is not missed, and add a test with `output=None` and `instruction=None` through all three renderers.
- Auto-detection rule 1 for SWE-bench ("only top-level key equals its parent directory name") is sound for both layouts. Add the negative test: a generic project directory containing some unrelated `report.json` must produce the "neither format" error, not a crash.
- Oracle by name: `agent_info.name == "oracle"` and directory `gold` are correct for the pinned sources (`utils.py:44-61` sets `model_name_or_path: "gold"`). Add `--reference NAME` later if users name theirs differently; documented risk is enough for 0.2.
- CI covers 3.11 to 3.13 while local runs are on 3.15. Add 3.14 to CI when touching it, since directory walking and `Path` behaviour are now on the hot path.
- Source line count is 683 by `wc`, not 682.
- Inspect field claims in section 4 are correct at the pinned commit.

## Verdict

**Build after fixing blockers.**

The restructure-not-rewrite call is right and the architecture in section 2 is clean. The blockers are all in the plan text, not in the approach: findings 1 and 2 (unclassified errors must not become `infra`; one deterministic Harbor error rule), 3 and 4 (SWE-bench summary file, empty and unapplied patches, `run_id` source), 5 (honest compatibility statement and the tests that will change), and 6 (one real harness-produced input per format before release). None needs a re-plan. Fix them in the plan, then build M1.

## What the plan got right and must not lose

- Small restructure instead of a rewrite, with `formats/` named to keep top-level `adapters/` valid and `inputs.py` kept as a shim so existing imports hold.
- Flat record with keys instead of nested containers, and `record_dict` omitting default v2 fields so every existing `record_id` and label file stays valid.
- One `LABELS` table as the single source of precedence, replacing the three copies found in P4.
- The reader contract: never invent a score, skip with a warning, deterministic order, local files only, no `config` blob.
- Keeping every finding in `matches` under one headline, which is what lets a grader issue and a model bug coexist.
- The explicit "what results alone cannot support" list, `genuine_failure` as an unexplained default, and `attempts_flip` attributing nothing.
- The honest "unverified items" section. Every item in it was worth checking, and most checked out: `result.json` is the right file name, the cited Harbor, SWE-bench and Inspect field names exist as stated, `gold` is the reference marker, and the submission layout matches the experiments README.
- Execution checks left out, with the route (run oracle and `nop` in the harness, feed the directories back) stated.
- Goldens generated from untouched code before any change, one commit per milestone, docs in the same commit.
- Pinned upstream commits with file names for every mapping.
