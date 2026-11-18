# Input and detector reference

See the [README](../README.md) for setup, public findings and limits.

## Commands

```text
./blame report IN... --out DIR [--format auto|generic|harbor|inspect|swebench]
./blame label IN... --out labels.csv [--format auto|generic|harbor|inspect|swebench]
./blame score labels.csv
```

`--format` names the reader for every `IN`. The default `auto` detects it per input, first match wins: a directory is `harbor` if a `result.json` in it, one level down or two levels down is an object with `trial_name` and `agent_info`, else `swebench` if a `report.json` two or three levels down has exactly one top-level key, equal to the name of the directory holding it, whose value has a true or false `resolved`, and is otherwise an error that names both things looked for; a file ending `.eval` is rejected; a file holding one JSON object is `generic` if it has `task_id`, else `inspect` if it has `eval` or `samples`; anything else is read as generic JSONL. Readers live in `blame_cli/formats/`.

The executable is named `blame`; use `./blame` from this checkout or put this directory on PATH. `python3 -m blame_cli` is equivalent. Inputs may mix formats. Errors return status 2 with the input path and, for JSONL, the line number. Files are read before any reports are written. Exact duplicate records are ignored with a warning.

`label` produces one row per lost or ungraded observation with a stable record ID, instruction, rubric, output, score, judge reasoning, predicted label, all detector matches, confidence, evidence, and an empty `human_label`. Fill only `human_label` with one of the eleven labels listed under [Labels](#labels), then run `score`. Label files written by 0.1.0 still score. Keep predictions and detector matches unchanged.

CSV display cells beginning with `=`, `+`, `-`, or `@` (including after whitespace), or a tab, carriage return or newline, receive a leading apostrophe to keep them as spreadsheet text. The separate `original_record_json` column retains the exact record as JSON, including the original output; record IDs do not change. Leave the apostrophes in place when labeling. This protects the generated export; spreadsheet software can alter escaping when saving it again.

`score` prints JSON with per-detector and per-verdict precision/recall, TP, FP, FN, support, and labeled/unlabeled row counts. Detector metrics count every independent detector match, including matches hidden by precedence. Verdict metrics evaluate the selected class. The default `genuine_failure` uses its selected verdict in both views. Each class is compared against the human label as a binary decision: precision = TP / (TP + FP), recall = TP / (TP + FN). Blank labels are skipped; zero denominators are `null`. Duplicate IDs, invalid labels, and inconsistent predictions fail validation. These metrics describe the labeled subset only; synthetic data cannot establish real precision.

CSV fields may contain up to `sys.maxsize` characters, matching the writer's Python string limit rather than the CSV reader's default 131,072-character cap. Available memory is the practical limit. Malformed CSV returns status 2 with the path and physical line number. Older labeling exports without `original_record_json` remain readable.

## Generic input

One JSON object per line, with these fields:

```json
{"task_id":"greeting:1","model":"alpha","run_id":"generation-1","instruction":"Write a greeting.","rubric_item_id":"formal","rubric_item_text":"Use a formal greeting.","output":"Yo.","score":0,"judge_reasoning":"Too informal.","judge_run":1,"error":null}
```

All fields except `score` and `judge_run` are strings; `error` may also be null or omitted. All fields except `judge_run` and `error` are required. Output and judge reasoning may be empty. `score` must be a finite number in [0,1], with 1 meaning full credit. `judge_run` is an optional integer or null. A nonempty error string indicates an infrastructure failure, unless the optional key `error_kind` is set: then that class is used instead (see Labels). Unknown extra fields, including `eval` and `samples`, are ignored on generic records. Records use newline delimiters (LF or CRLF); Unicode separators inside JSON strings remain part of the text.

Optional keys, each a non-empty string, null or absent:

| Key | Meaning |
| --- | --- |
| `agent` | The agent or scaffold that ran the model. Reports group by system: agent and model joined with ` / `. |
| `role` | `candidate` (default) or `reference`. A reference record is a run of the task's reference solution; it is not counted as a system under test. |
| `error_kind` | How the harness classified the error: `infra`, `setup`, `grader`, `agent` or `unknown`. Records of one attempt must agree on it. |
| `task_version` | A task checksum or revision. |
| `job_id` | The job or harness run the attempt belongs to. |

`score` may be `null` when the attempt was never graded; `error` must then say why. Such a record is listed as ungraded and adds nothing to lost items or lost points. A record that leaves every optional key out keeps the record ID it had in 0.1.0, so existing label files still match.

## Inspect JSON mapping

Use text JSON from `inspect eval --log-format json`. Binary `.eval` files are unsupported. This adapter implements the fields below from the [Inspect log reference](https://inspect.aisi.org.uk/reference/inspect_ai.log.html), [Score reference](https://inspect.aisi.org.uk/reference/inspect_ai.scorer.html#score), and [ModelOutput reference](https://inspect.aisi.org.uk/reference/inspect_ai.model.html#modeloutput).

| Read field | Mapping or purpose |
| --- | --- |
| `version` | Require log version 2. |
| `status`, top-level `error.message` | Warn on incomplete logs; never attach a global error to every scored sample. |
| `eval.task`, `samples[].id` | Generic task ID is `task:sample_id`, so each sample is a separate task instance across models. `eval.task_id` is not read. |
| `eval.model` | Generic model. |
| `eval.run_id`, `samples[].epoch` | Generic run ID is `run_id/epoch-N`; missing epoch defaults to 1. Epochs describe generation attempts, not repeated judges. |
| `samples[].invalidation` | Reject invalidated samples. |
| `samples[].input` | Instruction string, or newline-joined `content` of input chat messages. Only text content is accepted. Generated message history is not read. |
| `samples[].output.completion` | Prefer this serialized text if present. |
| `samples[].output.choices[0].message.content` | Otherwise use the first choice text. String or `{type: "text", text: "..."}` blocks; absent choices produce empty output. |
| `samples[].output.choices[].message.tool_calls` | Reject any tool-only choice even when serialized `completion` is present. |
| `samples[].error.message` | Generic error on this sample's scored records. |
| `samples[].scores` keys | One rubric item per scorer, or per dictionary dimension as `scorer/dimension`. |
| `scores[scorer].value` | Numeric [0,1], bool, or `C`/`I` map to scores; dictionary values expand into separate records. Other values, including `P`, arrays and nonfinite numbers, are rejected. |
| `scores[scorer].explanation` | Generic judge reasoning, default empty. |
| `scores[scorer].metadata.rubric_item_text` | Optional convention for scalar rubric text. |
| `scores[scorer].metadata.rubric_items[dimension]` | Optional convention for dictionary rubric text. |
| `scores[scorer].metadata.judge_run`, then `samples[].metadata.judge_run` | Optional convention for repeated judge identity, otherwise null. |

The metadata keys above are application conventions in Inspect's free-form metadata, not built-in rubric fields. Without rubric metadata, the item text identifies the scorer and says the rubric is unavailable; the unstated requirement detector abstains with an input warning. Samples with no scores are omitted with a warning, without inventing zero scores. Header-only logs, unresolved attachments, and non-text content are rejected. Aggregate results, events, score history, plan, stats, targets, and other fields are not read. Input instructions must include any system or developer requirements needed to assess the rubric.

`fixtures/inspect.json` was hand-written using these documented field shapes. It was not produced or validated by an installed `inspect_ai`. No Inspect package was installed. Tests cover this fixture, chat input, text blocks, dictionary scores, fractional credit, missing rubric text, errors, and unsupported values.

## Harbor mapping

**The Harbor reader was checked against real output of Harbor 0.24.0 only** (six small local Docker jobs, `fixtures/real-harbor`, `tests/test_real_harbor.py`): passing and failing trials, the `oracle` and `nop` agents, an agent timeout and an image that fails to build. No other error class, environment or Harbor version was produced. It was written from a reading of the Harbor source at [`harbor-framework/harbor@3ee9f53e6b459712fdec4e8ce6613d7aa5610299`](https://github.com/harbor-framework/harbor/tree/3ee9f53e6b459712fdec4e8ce6613d7aa5610299) (`src/harbor/models/trial/result.py`, `trial/paths.py`, `trial/error_policy.py`, `verifier/result.py`, `agent/name.py`, `trial/trial.py`). `fixtures/harbor-job` is hand-written from that reading. Harbor 0.24.0 writes no `policy`, `policy_override` or `reward_valid`, so those rows of the mapping are covered by the hand-written fixture only. A failed image build is recorded there as a plain `RuntimeError`, which the name table does not list: the trial is ungraded with `error_kind` `unknown`, and when `agent_setup` and `agent_execution` are both null the error text adds that the agent never started.

`IN` is a trial directory, a job directory, or a directory of job directories. Only `<trial_dir>/result.json` and `<trial_dir>/verifier/test-stdout.txt` are read; a job-level `result.json` is passed over. Each trial gives one record.

| Harbor field | Record field |
| --- | --- |
| `task_name` | `task_id`. The task's `source` is not added, so local and registry runs of one task join. |
| `task_checksum` | `task_version`. A warning is given when one task has more than one. |
| `agent_info.name` | `agent`. `oracle` gives `role: "reference"`. A `nop` trial is skipped with a warning. |
| `agent_info.model_info.provider`, `/`, `.name` | `model`; the provider is optional, and the model is `""` when there is no `model_info`. |
| name of the directory holding the trial directory | `job_id` |
| `trial_name`, `@`, first 8 characters of `id` | `run_id`; the bare trial name when `id` is missing. |
| `verifier_result.rewards["reward"]`; if absent and exactly one key exists, that key | `rubric_item_id: "reward"` and `score`. Other keys are listed in `judge_reasoning` and never scored. |
| no rewards, no key to choose, or a value that is not a number in [0, 1] | `score: null`, `error` says which, `error_kind: "unknown"` unless an exception sets it. |
| `exception_info`, else the first `step_results[].exception_info`: `exception_type`, `exception_message` | `error` is `Harbor <type>: <message>`; the message is cut after 2,000 characters, with a note of how many were left out. |
| `exception_type` looked up in the name table below | `error_kind` |
| `exception_info.policy_override.has_valid_reward` when set | `true` gives `agent`; `false` on an `agent` name gives `unknown`. The override is quoted in `error`. When `reward_valid` or the recorded `policy` says the opposite, that recorded value wins, the name table gives the class and `error` says the override was overruled. |
| whether Harbor counts the reward: the first present of `reward_valid`, `exception_info.policy.has_valid_reward`, then the override or the name table | not counted gives `score: null`. A name outside the table counts, which is Harbor's default. |
| `verifier/test-stdout.txt`, last 2,000 characters | `judge_reasoning` |
| not in `result.json` | `instruction`, `rubric_item_text` and `output` are `null`. |

`config`, `trial_uri` and `exception_traceback` are never read. In the text that is copied (exception messages and the test output), an absolute home path (`/Users/<name>`, `/home/<name>` or `C:\Users\<name>` at the start of a path, also after `file://`) is shortened to `~`. A `home` or `Users` directory inside a relative path or a URL, such as `src/home/views.py`, is left alone. Everything else is copied as written, so read a report before sharing it.

Name table, copied from `error_policy.py` at that commit. The same table is used for every file, whatever Harbor version wrote it:

- `agent`, where Harbor counts the reward: `NonZeroAgentExitCodeError`, `AgentTimeoutError`, `ContextWindowExceededError`, `OutputTokenExceededError`, `ContextLengthExceededError`, `OutputLengthExceededError`, `AgentSafetyRefusalError`, `ContentPolicyViolationError`.
- `grader`: `VerifierTimeoutError`, `RewardFileNotFoundError`, `RewardFileEmptyError`, `VerifierOutputParseError`.
- `infra`: `EnvironmentStartTimeoutError`, `SandboxBuildFailedError`, `AgentSetupTimeoutError`, `HealthcheckError`, `SandboxLikelyOutOfMemoryError`, `MemoryLimitExceededError`, `SSHAccessError`, `GKEExecStreamClosedError`, `GKEPodNotFoundError`, `RuntimeRequestError`, `AddTestsDirError`, `DownloadVerifierDirError`, `ApiError`, `ApiRateLimitError`, `ApiInternalServerError`, `ApiOverloadedError`, `ApiConnectionClosedError`, `ApiResponseStalledError`, `UnknownApiError`, `NetworkConnectionError`, `ApiConnectionError`, `ApiUsageLimitError`, `RateLimitError`, `InternalServerError`, `ServiceUnavailableError`, `APIConnectionError`, `APIError`, `Timeout`, `APIResponseValidationError`.
- `setup`: `UnsupportedModelParametersError`, `BadRequestError`, `UnprocessableEntityError`, `UnsupportedParamsError`, `BudgetExceededError`, `AgentAuthenticationError`, `ModelNotFoundError`, `ApiProviderResourceNotFoundError`, `AgentVersionTooOldError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `ServiceOperationsUnsupportedError`, `VercelScopeError`, `DspyImportError`, `MissingExtraError`, `CancelledError`.
- `unknown`: `RegradeError` (its meaning was not checked; the reward is not counted, as in Harbor's table) and every name not listed.

A `result.json` that cannot be read, or that has a wrong field type (an empty `task_name`, `agent_info: null`, an `exception_info` that is not an object or has no type), is skipped with one warning naming the file; the other trials are still read. A directory with no readable trial is an error that lists those warnings. When the same trial (same task, system and `run_id`) is supplied more than once, whatever the job directories are called, the first copy is kept with a warning, which also says when the copies differ. Harbor retries reuse the trial name and replace the earlier attempt, so several trials of one system on one task in a job are separate attempts, and `attempts_flip` compares them.

## SWE-bench mapping

**The SWE-bench reader was checked against real output of swebench 5.0.2 only** (`fixtures/real-swebench`, `tests/test_real_swebench.py`): one SWE-bench Lite instance graded with the gold patch and with a wrong patch, one empty patch, and a run in which the only instance errored before grading. It was written from a reading of the harness source at [`SWE-bench/SWE-bench@02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`](https://github.com/SWE-bench/SWE-bench/tree/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e) (`swebench/harness/grading.py`, `run_evaluation.py`, `reporting.py`, `infra_failure.py`, `constants/__init__.py`, `utils.py`). `fixtures/swebench-eval` is hand-written from that reading.

Only the harness layout is read: `<run_id>/<model_dir>/<instance_id>/{report.json, patch.diff, run_instance.log}` under `logs/run_evaluation` in the directory the harness ran in, and the run summary. swebench 5.0.2 writes one summary per model beside `logs/`, named `<model_dir>.<run_id>.json`; it is read when the run directory sits under `logs/run_evaluation`. A `results.json` inside the run directory is read as a summary too. `IN` is one run directory, a directory of run directories, or the harness's working directory or its `logs/` (then `logs/run_evaluation` is read). A run directory with `run.json` and instance logs but no `report.json` (every instance errored) is still a run. The layout decides which: a directory with a `report.json` two levels down is a run, and a `results.json` marks a run only where no report says otherwise. A `results.json` beside the run directories is not read, with a warning. The layout of the public submissions repository is not read. Each instance gives one record.

| SWE-bench source | Record field |
| --- | --- |
| instance directory name, which is also the single key of `report.json` | `task_id` |
| `<model_dir>` name | `model`; `role: "reference"` when it is `gold`. |
| `<run_id>` directory name, taken from the resolved path | `job_id`. When two different run directories share a name, parent directory names are added until they differ (`p1/run`, `p2/run`). |
| `patch:` and the first 12 hex characters of the SHA-256 of `patch.diff` | `run_id`. When the file is missing the `job_id` is used and a warning is given. |
| `patch.diff` | `output`, cut after 20,000 characters with a note of how many were left out. The `run_id` hash is of the whole file. |
| `resolved` | `rubric_item_id: "resolved"`; `score` 1 or 0. |
| `infra_failure: true`, with `infra_failure_reason` | `error_kind: "infra"`, `error` is `SWE-bench log pattern: <reason>`. The score stays 0, as in the harness. |
| `infra_failure_reason` set and `infra_failure: false` | `error_kind: "unknown"`, the same `error` text. |
| `patch_exists`, `patch_successfully_applied`, `tests_status` counts and up to 20 failed test names per group | `judge_reasoning`. `patch_successfully_applied: false` is worded as "no parseable test output", which is what the harness means by it. |
| `results.json` `empty_patch_ids`, or a `patch.diff` that is empty or only white space (unless the report says resolved or flags a log pattern) | a record with `output: ""`, `score: 0`, `error: "empty patch"`, `error_kind: "agent"`, `run_id: "patch:empty"`. The harness counts an empty patch as submitted and not resolved. |
| `results.json` `error_ids`, or an instance directory, without a readable `report.json` | `score: null`, `error` is the last 5 lines of `run_instance.log`, cut after 2,000 characters (or `no report.json`, or `report.json could not be read`), `error_kind: "unknown"`. |
| `tests_status` group whose `success` or `failure` is not a list of strings | the group is left out of `judge_reasoning`, with a warning naming the `report.json`. |
| `results.json` `incomplete_ids` | one warning with the count. |
| no `results.json` in a run | a warning: empty patches and harness errors without an instance directory are not visible. |
| not in the results | `instruction`, `rubric_item_text`, `agent` and `task_version` are `null`. |

An id from `results.json` is given to a model only when the run has one model directory or the instance directory exists under a model; otherwise it is skipped and counted in one warning. A `report.json` that cannot be read as a report for its instance (not JSON, another key, or a `resolved` that is not true or false) is skipped with one warning naming the file; if `results.json` lists the instance in `error_ids` it is still reported as not graded, otherwise it is left out. A directory with no readable result is an error that lists the warnings. Patches, log lines and test names are copied with absolute home paths shortened to `~`, by the same rule as in the Harbor mapping, so a repository path such as `a/src/home/views.py` in a patch is unchanged; the `run_id` is the hash of the file as written.

Records for the same instance, model and patch under different run directories are gradings of one output. They get `judge_run` 1, 2, ... in job-name order, so `judge_unstable` reports a patch that one run resolved and another did not. A run is its resolved directory, not its name: two runs called `run` under different parents are paired like any other two runs, and a run supplied twice (also through a symbolic link) is read once, with a warning. `blame report logs/evaluation` and `blame report logs/evaluation/run-a logs/evaluation/run-b` give the same items.

## Report schema 2

`report.json` has `schema_version: 2`. For an input that uses none of the optional keys, every value 0.1.0 reported is unchanged; schema 2 only adds keys. The row order of `by_class` changed: rows follow the precedence table under Labels, so the five 0.1.0 rows are no longer at indexes 0 to 4 (`judge_unstable` moved from index 1 to 3). Read rows by `class`, not by position.

| Key | Meaning |
| --- | --- |
| `scored_items` | Candidate records with a score. |
| `lost_items`, `lost_points` | Scored candidate records below 1, and the sum of `1 - score` over scored candidate records. |
| `ungraded_items` | Candidate records with `score: null`. They appear in `items` with their error. |
| `reference_items` | Reference records. They are never counted above and never listed in `items`. |
| `by_class[]` | One row per label with `category`, `lost_items`, `lost_points` and `ungraded_items`. |
| `by_model[]` | One row per system. The key is still `model`; it holds the system string. |
| `by_task[]` | One row per task with a lost or ungraded attempt: `systems_attempted`, `systems_failed` (systems with a scored check below 1), `reference` ("passed n of m attempts", counting the reference attempts the reference rules used for the failed results of this task, an attempt passing when all of its used results pass; then "; k left out (harness error, not graded or another task version)" when some were not used; "no usable reference attempt" when none was; or "no reference run supplied"), `labels` (count of every detector match; the default label counts where no detector matched), `primary_label` (the most frequent verdict on the task, ties to the higher precedence), `category`, `max_confidence` and `next_step`. |
| `items[]` | Each lost or ungraded record with its verdict, evidence and all detector matches. `record` holds the eleven 0.1.0 keys plus any optional key that is set. |

Markdown and HTML show the same data. They print `confidence` as "rule strength", and a text field the format does not carry as "not available in this format". In HTML the per-task rows are a list under "Failed tasks".

## Detector details

All detectors are pure. `blame_cli/detectors.py:INFRA_RULES` is the single table of infrastructure rules and strengths. Rules check a nonempty error field, whitespace-only output, or a whole output shaped like a timeout, rate limit/429, HTTP 5xx/gateway, or missing-artifact error. Bare numbers such as `429` and `500` do not match. Text rules accept fixed failure phrases such as `request timed out`, `rate limit exceeded`, `HTTP 503`, and `500 Internal Server Error`, with optional terminal punctuation. Only timeout `: upstream` and missing-artifact `: filename` details are accepted. Explanatory trailing prose does not match. This trades recall for fewer false positives; an answer consisting only of an error phrase is still ambiguous.

Judge instability compares identical `(task, model, run, item, output)` with unchanged instruction and rubric text and at least two explicit judge IDs. Flip rate is the number of unequal-score pairs divided by all unordered pairs of distinct judge runs. Counts come from score frequencies once per identity group, without enumerating pairs. It includes successful observations when finding flips, but only emits verdicts for lost observations. Conflicting scores within the same judge ID are rejected during loading. Missing judge IDs never establish instability.

Everyone loses requires at least two distinct models and every supplied observation for `(task, item)` to score exactly zero across all supplied runs, with unchanged instruction and rubric text. Partial credit or any pass prevents a match. Evidence includes all model scores, run and observation counts. This describes the supplied cohort; it cannot prove the item is wrong.

The heuristic reasoner checks explicit requirement wording (`must`, `require`, `include`, `use`, `exactly`). It extracts numbers, quoted strings, a small unit vocabulary, and conservative entity proxies: multiword Title Case names and uppercase acronyms. Missing terms use case-insensitive whole-term comparison. Numbers compare as complete literal tokens, including signs, decimals, exponents and percent suffixes: `12` is absent from `12.5`, `-12` and `12%`. Examples (including plural `examples`), negations, prohibitions (`avoid`, `omit`, `exclude`) and alternatives cause abstention. The closest instruction sentence has the most word overlap with the rubric, with the first sentence winning ties. Missing terms and that exact sentence are quoted in evidence. The method cannot infer paraphrases or implied requirements and deliberately misses uncertain entities, including single Title Case names.

`Reasoner.missing_requirements(instruction, rubric)` is the small extension interface. Inject a replacement using `triage(records, reasoner=...)` or `build_report(..., reasoner=...)`. A future LLM implementation belongs behind that interface. The shipped implementation is deterministic; no LLM calls exist.

## Labels

Only failed candidate records are triaged: a score below 1, or no score. Each detector returns at most one match and every match is kept in `matches`; the verdict is the first match in the order below, which is `blame_cli/model.py:LABELS`, the only precedence table. Strengths are fixed rule strengths, not calibrated probabilities.

| Label | Category | Fires when | Strength |
| --- | --- | --- | --- |
| `infra` | infra | `error_kind` is unset and the record has a nonempty error or an `INFRA_RULES` output match; or `error_kind` is `infra` | 0.94-0.99 by rule; 0.80 for `error_kind` |
| `setup_error` | setup | `error_kind` is `setup` | 0.85 |
| `grader_error` | grader | `error_kind` is `grader` | 0.85 |
| `judge_unstable` | grader | two or more `judge_run` gradings of the same output disagree | 0.99 |
| `reference_flaky` | grader | reference attempts on this task and check include a pass and a scored failure | 0.85 |
| `reference_fails` | task | one or more scored reference failures and no reference pass | 0.90 with two or more failures; 0.75 with one; at most 0.60 when a task version is unset |
| `item_everyone_loses` | task | two or more systems, every scored attempt at zero | 0.90 for records without optional keys; otherwise 0.50 for 2 systems, 0.70 for 3 or 4, 0.90 for 5 or more |
| `unstated_requirement` | instruction | the rubric requires a literal term the instruction never mentions | 0.65 |
| `attempts_flip` | unexplained | another attempt (a different `run_id`) of the same system on the same task and check scored 1 | 0.40 |
| `unclassified_error` | unexplained | `error_kind` is `unknown`, or `error_kind` is `agent` and the attempt has no score | 0.40 |
| `genuine_failure` | unexplained | no detector matched | 0.50 |

`genuine_failure` means no detector fired; it is not proof that the model failed. A graded attempt with an `agent` error gets no label of its own: the harness counts that attempt as a valid failure, and its error text is shown in the evidence of whichever verdict it gets. An attempt with no score never gets `genuine_failure`: with an `agent` error it is `unclassified_error`, because the files do not say whether it would have passed.

Attempts with `error_kind` `infra`, `setup` or `grader` are left out of every comparison between attempts (the reference rules, `item_everyone_loses`, `attempts_flip`); they count as no evidence, never as failures. The reference rules and `attempts_flip` also leave out an attempt the 0.1.0 infra rules match; `item_everyone_loses` keeps it, as 0.1.0 did. Attempts with no score never count as a pass or a fail. `unknown` and `agent` attempts stay in.

Reference rules compare only reference attempts whose `task_version` does not differ from the record's; when either version is unset the evidence says "task version not available". `item_everyone_loses` abstains when its cohort has more than one `task_version`. A reference label describes the task, so it becomes the verdict of every failed candidate attempt on that task, including real failures.

Every `next_step` in `by_task` is an instruction to check something. The labels state what the result files record; they do not establish that a task, a test or a model is at fault.

## Known limitations

Found by the independent check in `docs/CHECK-cross-format.md` (finding numbers in brackets) and not fixed:

- A directory holding both a Harbor trial and a SWE-bench run is read as Harbor; the SWE-bench data is ignored without a warning. Pass the two directories separately. (9)
- In a group of gradings of one output, a grading that errored and has no score gets `judge_unstable` as its headline when the other gradings disagree; its own error label is listed under the detector matches. (13)
- `item_everyone_loses` gives 0.90 to records without optional keys and scales with the number of systems otherwise, so adding an optional key such as `job_id` to 0.1.0-shaped records can lower its strength. This keeps 0.1.0 outputs unchanged. (14)
- Harbor trials without an `id` are told apart only by trial name, so the same trial name for one task and system in two jobs is treated as one trial and the second is dropped with a warning, even when the rewards differ. (16)
- A generic JSONL file that is not UTF-8 gives the codec error without the file name, as in 0.1.0. (18)
- The Harbor and SWE-bench readers were checked against one harness version each (Harbor 0.24.0, swebench 5.0.2) on a few small runs; most error classes were not produced.
- A Harbor directory that holds only `nop` trials is an error (exit 2), and one such directory given as its own `IN` fails the whole command; give the parent directory of the jobs instead, and the `nop` trials are skipped with a warning.
- Harbor systems are told apart by agent name and model only. Two configurations of one agent (different agent kwargs) are one system, so their trials on a task count as attempts of the same system.
