# blame

Did the model fail, or did your eval? A local Python CLI that groups lost rubric points into `infra`, `judge_unstable`, `item_everyone_loses`, `unstated_requirement`, and the default `genuine_failure`. Each verdict includes quoted evidence, relevant counts, and a confidence value.

## Quickstart

Requires Python 3.11+ and Make. Run from this directory:

```sh
make test
make demo
./blame label fixtures/synthetic.jsonl --out labels.csv
```

Open `demo/report.html` locally. `demo/report.md` and `demo/report.json` contain the same results. The demo also creates `demo-inspect/` from the hand-written Inspect fixture. There are no runtime or test dependencies outside the Python standard library, so no package installation or virtual environment is needed.

## Commands

```text
./blame report IN... --out DIR
./blame label IN... --out labels.csv
./blame score labels.csv
```

The executable is named `blame`; use `./blame` from this checkout or put this directory on PATH. `python3 -m blame_cli` is equivalent. Inputs may mix generic JSONL and Inspect text JSON. Errors return status 2 with the input path and, for JSONL, the line number. Files are read before any reports are written. Exact duplicate records are ignored with a warning.

`label` produces one row per lost observation with a stable record ID, instruction, rubric, output, score, judge reasoning, predicted label, all detector matches, confidence, evidence, and an empty `human_label`. Fill only `human_label` with one of the five class names, then run `score`. Keep predictions and detector matches unchanged.

`score` prints JSON with per-detector and per-verdict precision/recall, TP, FP, FN, support, and labeled/unlabeled row counts. Detector metrics count every independent detector match, including matches hidden by precedence. Verdict metrics evaluate the selected class. The default `genuine_failure` uses its selected verdict in both views. Each class is compared against the human label as a binary decision: precision = TP / (TP + FP), recall = TP / (TP + FN). Blank labels are skipped; zero denominators are `null`. Duplicate IDs, invalid labels, and inconsistent predictions fail validation. These metrics describe the labeled subset only; synthetic data cannot establish real precision.

## Generic input

One JSON object per line, with these fields:

```json
{"task_id":"greeting:1","model":"alpha","run_id":"generation-1","instruction":"Write a greeting.","rubric_item_id":"formal","rubric_item_text":"Use a formal greeting.","output":"Yo.","score":0,"judge_reasoning":"Too informal.","judge_run":1,"error":null}
```

All fields except `score` and `judge_run` are strings; `error` may also be null or omitted. All fields except `judge_run` and `error` are required. Output and judge reasoning may be empty. `score` must be a finite number in [0,1], with 1 meaning full credit. `judge_run` is an optional integer or null. A nonempty error string indicates an infrastructure failure. Unknown extra fields are ignored.

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
| `samples[].output.choices[0].message.tool_calls` | Reject a tool-only choice rather than treating it as an empty text failure. |
| `samples[].error.message` | Generic error on this sample's scored records. |
| `samples[].scores` keys | One rubric item per scorer, or per dictionary dimension as `scorer/dimension`. |
| `scores[scorer].value` | Numeric [0,1], bool, or `C`/`I` map to scores; dictionary values expand into separate records. Other values, including `P`, arrays and nonfinite numbers, are rejected. |
| `scores[scorer].explanation` | Generic judge reasoning, default empty. |
| `scores[scorer].metadata.rubric_item_text` | Optional convention for scalar rubric text. |
| `scores[scorer].metadata.rubric_items[dimension]` | Optional convention for dictionary rubric text. |
| `scores[scorer].metadata.judge_run`, then `samples[].metadata.judge_run` | Optional convention for repeated judge identity, otherwise null. |

The metadata keys above are application conventions in Inspect's free-form metadata, not built-in rubric fields. Without rubric metadata, the item text identifies the scorer and says the rubric is unavailable; the unstated requirement detector abstains with an input warning. Samples with no scores are omitted with a warning, without inventing zero scores. Header-only logs, unresolved attachments, and non-text content are rejected. Aggregate results, events, score history, plan, stats, targets, and other fields are not read. Input instructions must include any system or developer requirements needed to assess the rubric.

`fixtures/inspect.json` was hand-written using these documented field shapes. It was not produced or validated by an installed `inspect_ai`. No Inspect package was installed. Tests cover this fixture, chat input, text blocks, dictionary scores, fractional credit, missing rubric text, errors, and unsupported values.

## Detectors and confidence

All detectors are pure. `blame_cli/detectors.py:INFRA_RULES` is the single table of infrastructure rules and strengths. Rules check a nonempty error field, whitespace-only output, or a whole output shaped like a timeout, rate limit/429, HTTP 5xx/gateway, or missing-artifact error. Discussion of these errors inside an answer does not trigger a match. This trades recall for fewer false positives.

Judge instability compares identical `(task, model, run, item, output)` with unchanged instruction and rubric text and at least two explicit judge IDs. Flip rate is the number of unequal-score pairs divided by all unordered pairs of distinct judge runs. It includes successful observations when finding flips, but only emits verdicts for lost observations. Conflicting scores within the same judge ID are rejected during loading. Missing judge IDs never establish instability.

Everyone loses requires at least two distinct models and every supplied observation for `(task, item)` to score exactly zero across all supplied runs, with unchanged instruction and rubric text. Partial credit or any pass prevents a match. Evidence includes all model scores, run and observation counts. This describes the supplied cohort; it cannot prove the item is wrong.

The heuristic reasoner checks explicit requirement wording (`must`, `require`, `include`, `use`, `exactly`). It extracts numbers, quoted strings, a small unit vocabulary, and conservative entity proxies: multiword Title Case names and uppercase acronyms. Missing terms use case-insensitive whole-term comparison, never substring comparison. Examples, negations and alternatives cause abstention. The closest instruction sentence has the most word overlap with the rubric, with the first sentence winning ties. Missing terms and that exact sentence are quoted in evidence. The method cannot infer paraphrases or implied requirements and deliberately misses uncertain entities, including single Title Case names.

`Reasoner.missing_requirements(instruction, rubric)` is the small extension interface. Inject a replacement using `triage(records, reasoner=...)` or `build_report(..., reasoner=...)`. A future LLM implementation belongs behind that interface. The shipped implementation is deterministic; no LLM calls exist.

Precedence is infra, judge instability, everyone loses, unstated requirement, then genuine failure. JSON and HTML retain all detector matches. Confidence values are fixed evidence strengths, not calibrated probabilities: 0.94-0.99 for infra depending on the rule, 0.99 for observed judge disagreement, 0.90 for cohort zeros, 0.65 for missing literal anchors, and 0.50 for the default. Genuine failure means no detector fired; it is not proof that the model failed.

## Real demo excerpt

Trimmed from `demo/report.md` after running `make demo`:

```markdown
# blame report

Scored observations: 36. Lost items: 21. Lost points: 21.

Each scored observation below 1 is a lost item, including repeated judges.

Confidence values are fixed heuristic strengths, not calibrated probabilities.

## By class

| class | lost_items | lost_points |
| --- | --- | --- |
| infra | 4 | 4.0 |
| judge_unstable | 1 | 1.0 |
| item_everyone_loses | 6 | 6.0 |
| unstated_requirement | 4 | 4.0 |
| genuine_failure | 6 | 6.0 |
```

## Architecture

- `blame` and `blame_cli.cli` parse the three commands.
- `model` validates immutable records and builds stable record IDs.
- `inputs` maps generic and Inspect files to those records.
- `detectors` contains pure rules and the pluggable reasoner.
- `reports` builds one report structure and renders JSON, Markdown and static HTML.
- `labels` writes CSV and computes metrics against supplied human labels.
- `fixtures` contains synthetic data; `tests` uses standard-library unittest.

## Assumptions

- Every score below 1 represents lost credit. Each judge observation gets its own row, and lost points are `1 - score`; reports do not pretend repeated judging is a new generation attempt.
- Model and task IDs, rubric IDs and instructions are comparable across inputs. For Inspect, task/sample IDs must not contain `:`, and scorer/dimension names must not contain `/`, because those characters form namespaced IDs.
- All relevant rubric observations are supplied. Missing models or runs cannot be inferred; models absent from an item do not count toward its two-model minimum.
- A nonempty error field means an active failure, not an archived error that later recovered. Empty or null errors carry no signal.
- Reports are for small local text evals. All records and rendered reports are held in memory. HTML uses embedded CSS, escaped input and native details elements; it makes no network requests.
- Fixtures use only invented tasks and model names. `fixtures/build.py` can reproduce the 36 generic records: three tasks, three models, two judge runs, two rubric items per task. The default cases are deliberate negative controls.
