# blame

**blame found changed judge preferences in 500 of 1,500 answer pairs (33.3%) when answer order was swapped.** Of those, 268 pairs reversed winner outright; 232 changed between a tie and a win/loss. These are historical published Arena-Hard v0.1 results, not new model runs. [Read the findings and reproduction steps](realdata/FINDINGS.md).

One example: the same answer used a regex without a fixed video ID length. Before swapping answer order, the judge wrote:

> Assistant B's answer is slightly better because it does not assume a fixed length for the video IDs

After the swap, it preferred the other answer:

> Assistant B's answer is slightly better because it correctly assumes the length of the YouTube video ID

The candidate went from a win to a loss. Both explanations also noticed a real defect: neither regex specifically targeted `href` attributes. A judge issue and a model bug can coexist. [Source example and context](realdata/FINDINGS.md#1-the-same-regex-choice-wins-then-loses).

blame is a local Python CLI for reviewing lost eval credit. It sorts failed attempts by what the result files record: an infrastructure, setup or grader error the harness wrote down, two gradings of one output that disagree, a reference solution that failed or passed only sometimes, an item on which no supplied system scored above zero, a system that both passed and failed a task, a possible unstated requirement, and losses no rule explains. Reports include quoted evidence and counts so you can check each hypothesis. No model API calls, API keys or runtime dependencies.

**[Preview a trimmed real report](docs/report.html)**: download and open the HTML locally. It contains the full-run tables and one audited example, with expandable evidence, embedded styles and no scripts or external assets. GitHub's file view shows the HTML source. [Markdown report](realdata/arena_hard/report.md) is also readable on GitHub.

## Quickstart

Requires Python 3.11+ with `venv` and pip, and internet access for the build dependency. From a downloaded or cloned checkout, run these three commands (macOS/Linux):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/blame report fixtures/synthetic.jsonl --out demo
```

Open `demo/report.html` locally. JSON and Markdown versions are beside it. This synthetic demo has 36 scored observations and 21 lost observations; it is separate from the public Arena-Hard result above. On Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\blame.exe` for the last two commands.

Install from this checkout. The PyPI project named `blame` belongs to another tool; `pip install blame` does not install this project. The local distribution metadata is `blame-cli`; the console command is `blame`.

## Use your own results

| Input | What to pass | Status |
| --- | --- | --- |
| Generic JSONL | a `.jsonl` file | tested on synthetic fixtures and the public Arena-Hard conversion |
| Inspect v2 text JSON | a log from `inspect eval --log-format json` | a documented subset; fixture hand-written, not validated by `inspect_ai` |
| Harbor | a trial directory, a job directory or a directory of jobs | unverified against real harness output |
| SWE-bench harness | a run directory under `logs/evaluation`, or that directory | unverified against real harness output |

The format is detected per input; `--format` forces one. The Harbor and SWE-bench readers were written from the harness source code and tested only on hand-written fixtures, so check a report against your own files before relying on it. The two fixtures show the shape (run from the checkout):

```text
./blame report fixtures/harbor-job --out demo-harbor
./blame report fixtures/swebench-eval --out demo-swebench
```

Reports copy error messages, test output, log lines and patches from the result files. Absolute home-directory paths in that text are shortened to `~`, error text is cut after 2,000 characters and a patch after 20,000, and nothing else is removed, so read a report before sharing it. Harbor's own `harbor analyze` has a model read each trial against a rubric; blame makes no model calls and only sorts what the result files already record.

Binary Inspect `.eval` files, tool-only outputs and the SWE-bench public submissions layout are unsupported. Each generic record describes one task, model, generation run, rubric item, output, score in [0,1], and judge reasoning. Optional judge IDs identify repeated judgments of the same generation. Optional keys can name the agent, mark a reference-solution run, carry the harness error class and mark an attempt as never graded (`score: null`).

After activating the venv, the workflow is:

```text
blame report IN... --out DIR
blame label IN... --out labels.csv
blame score labels.csv
```

`label` leaves `human_label` blank. Fill it after reviewing the evidence, then `score` measures precision and recall on that labeled subset. It does not produce ground truth for you. See the [input schema, the Inspect, Harbor and SWE-bench mappings, the eleven labels and their rule strengths](docs/reference.md). To run the standard-library test suite, use `make test` (requires Make).

## What blame does not do

- **Prove who caused a failure.** Attribution is a hypothesis to check. `genuine_failure` is the schema's default label for an unclassified loss, not proof of model responsibility.
- **Establish real-world precision or recall.** Codex checked 20 fired verdicts: 12/12 disagreement flags and 8/8 cohort-loss flags matched their documented predicates. This was not independent human annotation. Default cases were not audited; no recall or eval-fault attribution precision was measured.
- **Diagnose positional bias from a swap alone.** Order changed between the two games. The result does not separate position effects from other judge variability or identify the correct winner.
- **Prove an eval item is wrong because everyone loses.** The run found 34 such prompts across three supplied candidates; GPT-4 0314 was their fixed comparator and was excluded from the scored cohort. Shared losses can reflect real candidate defects.
- **Say a task is broken, a grader is flaky or a model is at fault.** Result files support narrower statements: the harness recorded an error of a given type, two gradings of one output disagree, the reference solution did not pass or passed only sometimes, no supplied system scored above zero, a system both passed and failed a task. A flip between two attempts of a stochastic agent is not evidence about the grader. An `infra` label is only as right as the harness's record or its log heuristic.
- **Separate a real model failure from a reference problem.** When the reference fails on a task, that fact becomes the headline of every failed attempt on it, including attempts that failed on their own account.
- **Run anything.** blame never reruns a reference solution or a do-nothing agent. Run those with the harness and pass the result directories in; reference runs are read.
- **Understand requirements semantically or calibrate confidence.** The shipped reasoner checks literal anchors and abstains on some ambiguous wording. Confidence values are fixed heuristic strengths, not probabilities of correct attribution.

## Architecture

- `blame_cli.cli` implements report, label and score commands.
- `formats` holds one reader per input format; `inputs` and `model` validate the records.
- `detectors` applies deterministic rules and preserves overlapping matches.
- `Reasoner.missing_requirements` is the pluggable interface for a future LLM; the shipped implementation uses heuristics only.
- `reports` renders JSON, Markdown and self-contained HTML; `labels` handles CSV and label metrics.
- `adapters/arena_hard.py` converts published comparisons; `realdata/` keeps provenance and audited extracts.
- `tests` uses standard-library unittest; fixtures are synthetic or public.

## Assumptions

- Scores below 1 mean lost credit. Each judge observation is counted separately; repeated judging is not another generation attempt. Arena-Hard scores map relative preferences to win=1, tie=0.5, loss=0, not rubric correctness or leaderboard scores.
- Task, rubric, model and run IDs are comparable across supplied inputs. Judge instability needs explicit distinct judge IDs with unchanged generation, instruction and rubric. Missing models and runs cannot be inferred.
- Instructions include all requirements needed to assess the rubric. A nonempty error field with no `error_kind` represents an active failure.
- Inputs and reports fit in memory. This is a tool for local text eval review.
- There are no runtime or test dependencies. `setuptools>=77` is the sole build dependency: it builds the wheel, installs the console script and supports the MIT license metadata. pip supplies it in an isolated build environment.

## License

Code: [MIT](LICENSE), Copyright (c) 2026 Hari Naralasetty. The public Arena-Hard extracts retain their [Apache-2.0 license](realdata/arena_hard/LICENSE) and [source attribution](realdata/arena_hard/NOTICE.md). The HTML preview is a derived extract of the same public data.
