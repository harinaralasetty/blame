# Input and detector reference

See the [README](../README.md) for setup, public findings and limits.

## Commands

```text
./blame report IN... --out DIR [--format auto|generic|inspect]
./blame label IN... --out labels.csv [--format auto|generic|inspect]
./blame score labels.csv
```

`--format` names the reader for every `IN`. The default `auto` detects it per input: a file ending `.eval` is rejected; a file holding one JSON object is `generic` if it has `task_id`, else `inspect` if it has `eval` or `samples`; anything else is read as generic JSONL. Readers live in `blame_cli/formats/`.

The executable is named `blame`; use `./blame` from this checkout or put this directory on PATH. `python3 -m blame_cli` is equivalent. Inputs may mix generic JSONL and Inspect text JSON. Errors return status 2 with the input path and, for JSONL, the line number. Files are read before any reports are written. Exact duplicate records are ignored with a warning.

`label` produces one row per lost or ungraded observation with a stable record ID, instruction, rubric, output, score, judge reasoning, predicted label, all detector matches, confidence, evidence, and an empty `human_label`. Fill only `human_label` with one of the five class names, then run `score`. Keep predictions and detector matches unchanged.

CSV display cells beginning with `=`, `+`, `-`, or `@` (including after whitespace), or a tab, carriage return or newline, receive a leading apostrophe to keep them as spreadsheet text. The separate `original_record_json` column retains the exact record as JSON, including the original output; record IDs do not change. Leave the apostrophes in place when labeling. This protects the generated export; spreadsheet software can alter escaping when saving it again.

`score` prints JSON with per-detector and per-verdict precision/recall, TP, FP, FN, support, and labeled/unlabeled row counts. Detector metrics count every independent detector match, including matches hidden by precedence. Verdict metrics evaluate the selected class. The default `genuine_failure` uses its selected verdict in both views. Each class is compared against the human label as a binary decision: precision = TP / (TP + FP), recall = TP / (TP + FN). Blank labels are skipped; zero denominators are `null`. Duplicate IDs, invalid labels, and inconsistent predictions fail validation. These metrics describe the labeled subset only; synthetic data cannot establish real precision.

CSV fields may contain up to `sys.maxsize` characters, matching the writer's Python string limit rather than the CSV reader's default 131,072-character cap. Available memory is the practical limit. Malformed CSV returns status 2 with the path and physical line number. Older labeling exports without `original_record_json` remain readable.

## Generic input

One JSON object per line, with these fields:

```json
{"task_id":"greeting:1","model":"alpha","run_id":"generation-1","instruction":"Write a greeting.","rubric_item_id":"formal","rubric_item_text":"Use a formal greeting.","output":"Yo.","score":0,"judge_reasoning":"Too informal.","judge_run":1,"error":null}
```

All fields except `score` and `judge_run` are strings; `error` may also be null or omitted. All fields except `judge_run` and `error` are required. Output and judge reasoning may be empty. `score` must be a finite number in [0,1], with 1 meaning full credit. `judge_run` is an optional integer or null. A nonempty error string indicates an infrastructure failure. Unknown extra fields, including `eval` and `samples`, are ignored on generic records. Records use newline delimiters (LF or CRLF); Unicode separators inside JSON strings remain part of the text.

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

## Report schema 2

`report.json` has `schema_version: 2`. For an input that uses none of the optional keys, every value 0.1.0 reported is unchanged; schema 2 only adds keys.

| Key | Meaning |
| --- | --- |
| `scored_items` | Candidate records with a score. |
| `lost_items`, `lost_points` | Scored candidate records below 1, and the sum of `1 - score` over scored candidate records. |
| `ungraded_items` | Candidate records with `score: null`. They appear in `items` with their error. |
| `reference_items` | Reference records. They are never counted above and never listed in `items`. |
| `by_class[]` | One row per label with `category`, `lost_items`, `lost_points` and `ungraded_items`. |
| `by_model[]` | One row per system. The key is still `model`; it holds the system string. |
| `by_task[]` | One row per task with a lost or ungraded attempt: `systems_attempted`, `systems_failed` (systems with a scored check below 1), `reference` ("passed n of m attempts" or "no reference run supplied"), `labels` (count of every detector match; the default label counts where no detector matched), `primary_label` (the most frequent verdict on the task, ties to the higher precedence), `category`, `max_confidence` and `next_step`. |
| `items[]` | Each lost or ungraded record with its verdict, evidence and all detector matches. `record` holds the eleven 0.1.0 keys plus any optional key that is set. |

Markdown and HTML show the same data. They print `confidence` as "rule strength", and a text field the format does not carry as "not available in this format". In HTML the per-task rows are a list under "Failed tasks".

## Detectors and confidence

All detectors are pure. `blame_cli/detectors.py:INFRA_RULES` is the single table of infrastructure rules and strengths. Rules check a nonempty error field, whitespace-only output, or a whole output shaped like a timeout, rate limit/429, HTTP 5xx/gateway, or missing-artifact error. Bare numbers such as `429` and `500` do not match. Text rules accept fixed failure phrases such as `request timed out`, `rate limit exceeded`, `HTTP 503`, and `500 Internal Server Error`, with optional terminal punctuation. Only timeout `: upstream` and missing-artifact `: filename` details are accepted. Explanatory trailing prose does not match. This trades recall for fewer false positives; an answer consisting only of an error phrase is still ambiguous.

Judge instability compares identical `(task, model, run, item, output)` with unchanged instruction and rubric text and at least two explicit judge IDs. Flip rate is the number of unequal-score pairs divided by all unordered pairs of distinct judge runs. Counts come from score frequencies once per identity group, without enumerating pairs. It includes successful observations when finding flips, but only emits verdicts for lost observations. Conflicting scores within the same judge ID are rejected during loading. Missing judge IDs never establish instability.

Everyone loses requires at least two distinct models and every supplied observation for `(task, item)` to score exactly zero across all supplied runs, with unchanged instruction and rubric text. Partial credit or any pass prevents a match. Evidence includes all model scores, run and observation counts. This describes the supplied cohort; it cannot prove the item is wrong.

The heuristic reasoner checks explicit requirement wording (`must`, `require`, `include`, `use`, `exactly`). It extracts numbers, quoted strings, a small unit vocabulary, and conservative entity proxies: multiword Title Case names and uppercase acronyms. Missing terms use case-insensitive whole-term comparison. Numbers compare as complete literal tokens, including signs, decimals, exponents and percent suffixes: `12` is absent from `12.5`, `-12` and `12%`. Examples (including plural `examples`), negations, prohibitions (`avoid`, `omit`, `exclude`) and alternatives cause abstention. The closest instruction sentence has the most word overlap with the rubric, with the first sentence winning ties. Missing terms and that exact sentence are quoted in evidence. The method cannot infer paraphrases or implied requirements and deliberately misses uncertain entities, including single Title Case names.

`Reasoner.missing_requirements(instruction, rubric)` is the small extension interface. Inject a replacement using `triage(records, reasoner=...)` or `build_report(..., reasoner=...)`. A future LLM implementation belongs behind that interface. The shipped implementation is deterministic; no LLM calls exist.

Precedence is infra, judge instability, everyone loses, unstated requirement, then genuine failure. JSON and HTML retain all detector matches. Confidence values are fixed evidence strengths, not calibrated probabilities: 0.94-0.99 for infra depending on the rule, 0.99 for observed judge disagreement, 0.90 for cohort zeros, 0.65 for missing literal anchors, and 0.50 for the default. Genuine failure means no detector fired; it is not proof that the model failed.

