# blame on published public results

Run date: 2026-10-29. This run used existing public model outputs and judgments;
it made no model API calls and required no login. These are real published eval
results, rather than blame's synthetic fixtures. They do not represent production
outcomes or the current best models.

**blame found changed judge preferences in 500 of 1,500 answer pairs (33.3%) when
answer order was swapped.** Of those, 268 pairs reversed winner outright; 232
changed between a tie and a win/loss. It also identified 34 prompts where all three
supplied candidates lost to a fixed baseline in both orders. The second finding
does not establish faulty eval items.

## Dataset, access and license

Used one dataset: [Arena-Hard-Auto, v0.1 published answers and judgments](https://huggingface.co/datasets/lmarena-ai/arena-hard-auto/tree/15f3746e21432264ce9b453999bde4f3c946d2e6/data/arena-hard-v0.1),
at immutable Hugging Face revision `15f3746e21432264ce9b453999bde4f3c946d2e6`.
The [dataset card](https://huggingface.co/datasets/lmarena-ai/arena-hard-auto/blob/15f3746e21432264ce9b453999bde4f3c946d2e6/README.md)
declares **Apache-2.0**. A [license copy](arena_hard/LICENSE), unchanged
[source card](arena_hard/SOURCE_README.md), and attribution in
[NOTICE.md](arena_hard/NOTICE.md) accompany the retained extracts. Attribution:
Tianle Li, Wei-Lin Chiang, Evan Frick, Lisa Dunlap, Tianhao Wu, Banghua Zhu,
Joseph E. Gonzalez and Ion Stoica, *From Crowdsourced Data to High-Quality
Benchmarks: Arena-Hard and BenchBuilder Pipeline* (2024),
[paper](https://arxiv.org/abs/2406.11939).

The cohort was fixed before inspecting verdicts: Claude 3 Opus 20240229,
GPT-3.5 Turbo 0125, and Llama 3 70B Instruct. Each has all 500 prompts, one
generated answer per prompt, and two GPT-4 1106 Preview judgments against the
same GPT-4 0314 baseline answer. The baseline is context, not a fourth scored
candidate. All 1,500 pairs / 3,000 games were accepted, with no omissions,
deduplication warnings or invented scores. Downloads total about 29.8 MB and
remain under gitignored `data/arena_hard/`.

Candidate checks: [lmsys/mt_bench_human_judgments](https://huggingface.co/datasets/lmsys/mt_bench_human_judgments/blob/main/README.md)
declares CC-BY-4.0, but its published fields omit judge explanations and separate
order-swap games. The linked richer [MT-Bench Space card](https://huggingface.co/spaces/lmsys/mt-bench/blob/main/README.md)
declares only `license: other`; that is not a basis for applying the human dataset's
CC license to every Space file. Arena-Hard was selected for its explicit data
license and full explanations plus repeated comparisons. No MT-Bench records
were included in the run.

## Mapping and reproducibility

[Adapter and field mapping](../adapters/README.md) describes every field.
The adapter checks each stored judge prompt against the exact question and both
published answers in the expected order. Thus a stale answer join or incorrectly
swapped A/B label cannot silently create a disagreement. Source URL, byte count
and SHA-256 for each downloaded file, plus the generic JSONL hash, are in
[provenance.json](arena_hard/provenance.json).

Scores map candidate win to 1, tie to 0.5, and loss to 0. Strong and slight
preferences collapse to the same direction. This preserves preference direction,
not the original five-level scale. These are relative preference scores rather
than itemized rubric correctness scores. The reported 1,609 lost units are sums
of `1 - score` across both judging games; they are not original benchmark rubric
points, independent generation failures, or leaderboard scores.

Both games use identical answer text and baseline context. Game 1 places the
candidate in B; game 2 places it in A. `judge_run=1/2` therefore describes an
explicit **order intervention**, not two stochastic repeats at an identical
prompt. Disagreement demonstrates sensitivity of the comparison procedure; it
does not isolate causal positional bias from other judge variability or determine
which winner is objectively right. There are no identical-order repeat samples
in this experiment.

From the repository root:

```sh
python3 adapters/arena_hard.py --download
./blame report data/arena_hard/generic.jsonl --out data/arena_hard/full-report
python3 realdata/arena_hard/summarize.py
make test
```

The CLI wrote full Markdown, JSON and HTML reports (roughly 24–28 MB each) to
`data/arena_hard/full-report/`. To skip large files, the retained
[report.md](arena_hard/report.md) and [report.json](arena_hard/report.json) keep
**all aggregate counts and exactly the 20 audited drill-down items**. They
explicitly mark the other 1,806 lost observations as omitted. Original two-game
source pairs for the sample, including reasoning from games receiving full
credit, and all three models' raw game scores are in
[audit_evidence.json](arena_hard/audit_evidence.json). No raw bulk data or full
HTML report is included under `realdata/`.

## Full-run numbers

| Selected verdict | Lost observations | Lost preference units | Distinct underlying groups |
| --- | ---: | ---: | --- |
| `infra` | 0 | 0 | 0 |
| `judge_unstable` | 606 | 490 | 500 answer pairs |
| `item_everyone_loses` | 204 | 204 | 34 prompts, 3 candidates × 2 games each |
| `unstated_requirement` | 0 | 0 | 0 |
| `genuine_failure` (default) | 1,016 | 915 | not independently validated |
| Total below full credit | 1,826 | 1,609 | observations, not distinct items |

1,174 of the 3,000 observations received full credit. The 500 changed comparisons
split into 268 loss↔win, 126 tie↔win, and 106 loss↔tie. Only the below-full-credit
side is reported, so a loss↔tie pair contributes two flagged rows and a loss↔win
pair contributes one. This accounts for the 606 flagged observations. There
were no overlapping detector matches in this run.

| Candidate | Scored observations | Below full credit | Judge disagreement rows | Cohort-loss rows | Default rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude 3 Opus 20240229 | 1,000 | 487 | 221 | 68 | 198 |
| GPT-3.5 Turbo 0125 | 1,000 | 794 | 176 | 68 | 550 |
| Llama 3 70B Instruct | 1,000 | 545 | 209 | 68 | 268 |

## Hand-check of 20 fired verdicts

[handcheck.csv](arena_hard/handcheck.csv) records item, model, detector, verdict,
yes/no correctness, explanation, game and stable record ID for all 20.
The review was performed by Codex through direct inspection of the source
question, candidate, comparator, both judgment explanations and scores. It is
**not independent human annotation or expert adjudication**, and generated code
was not deployed or executed.

Selection was deterministic, before labeling: four distinct `judge_unstable`
answer pairs per candidate, sorted by SHA-256(task_id), then eight distinct
`item_everyone_loses` prompts sorted by SHA-256(task_id + model). Within a pair
the first reported lost game is selected. There are 18 distinct prompts among
the 20 rows because two prompts recur across candidate strata. No unfavorable
cases were replaced. The selection code is in
[summarize.py](arena_hard/summarize.py).

Correctness means the **documented predicate and its scope are supported**:
same generation/context with genuinely different preference scores for
`judge_unstable`; all six supplied observations zero with unchanged context for
`item_everyone_loses`. I also inspected the explanations for substantive concerns
and recorded them in `why`. A cohort-loss label is marked yes when that literal
cohort fact is true, even when the model answers have real defects. The separate
`eval_fault_supported` column explicitly says the cohort fact does not establish
eval fault.

| Detector / default | Audited | Correct | Incorrect | Sample precision | What was validated |
| --- | ---: | ---: | ---: | ---: | --- |
| `infra` | 0 | 0 | 0 | N/A | No fired cases; no estimate |
| `judge_unstable` | 12 | 12 | 0 | 100% (12/12) | Real changes of relative preference on unchanged answer pairs |
| `item_everyone_loses` | 8 | 8 | 0 | 100% (8/8) | All supplied candidate scores zero; **not** precision for bad items |
| `unstated_requirement` | 0 | 0 | 0 | N/A | No applicable item-specific requirement rubrics here |
| `genuine_failure` | 0 | 0 | 0 | N/A | Default cases were outside the fired-verdict sample |

These high sample precisions are narrow and partly mechanical: both fired
detectors describe relationships already present in supplied scores. They check
mapping and evidence fidelity, not the truth of the judge's assessment. They
cannot justify “100% accurate eval blame.” Even under a hypothetical independent
random-sample model, Wilson 95% intervals would be approximately 75.8–100% for
12/12 and 67.6–100% for 8/8; the actual stratification and repeated prompts mean
those are illustrations of small-sample uncertainty, not validated population
intervals. There is no measured recall, no audited default-case precision, and
no independent gold label for eval-fault attribution. Zero flags from a detector
is not evidence of zero false negatives.

## Three revealing examples

### 1. The same regex choice wins, then loses

Sample 4; prompt `8e6c723dd4564008b0ad488a65d1e000`, Claude 3 Opus.
The request is:

> write a python script that reads from stdin and extracts all watch?v= hrefs and prints youtube watch urls

The candidate uses `r'watch\?v=([a-zA-Z0-9_-]+)'`; the baseline constrains the ID
to `{11}` characters. With the candidate in B, the judge says:

> Assistant B's answer is slightly better because it does not assume a fixed length for the video IDs

After swapping, it prefers the baseline, now B:

> Assistant B's answer is slightly better because it correctly assumes the length of the YouTube video ID

Both raw scores are `B>A`, but those labels refer to different actual models:
the candidate goes from 1 to 0. `judge_unstable` is useful here. Both judge
explanations also notice that neither regex specifically targets `href`
attributes, so instability and a model defect can coexist. The flag does not
exonerate either answer.

### 2. A judge issue can coexist with an obvious model bug

Sample 9; prompt `beefc3c330484a25b1f49ae18002084e`, Llama 3 70B.
The candidate's ShuffleSplit example ends with:

> print("Average accuracy:", np.mean(scores))

There is no `import numpy as np` in its imports. In game 1 the judge nevertheless
says:

> The code will work as expected and demonstrates the use of ShuffleSplit effectively.

It awards a tie. In game 2 it notices:

> The code is missing an import statement for `numpy` as `np` is used at the end of the code snippet.

It now prefers the baseline (candidate score 0). The disagreement detector is
right about the scoring change, but calling these lost points purely “eval
failure” would conceal the candidate's own missing import. No package execution
was needed to verify that `np` is undefined in the supplied snippet.

### 3. Everyone loses, while the judge also gets arithmetic wrong

Sample 19; prompt `8358c05bf55149deb3b7a3e7297dc584`, Llama 3 70B.
The user requests a deck with exactly 40 cards. The candidate labels its sections:

> **Units (20):**
> **Spells (10):**
> **Landmarks (10):**

The game-1 judge says:

> it includes 20 units, 10 spells, and 10 landmarks, which totals 50 cards

Those counts total 40. This is a visible error in the judge rationale regardless
of card legality. The same rationale also alleges invented cards; this audit
does not independently verify the card database or endorse the deck. All three
candidate models receive zero in both orders, so `item_everyone_loses` is
literally correct for the supplied cohort. But that detector does not diagnose
arithmetic, and shared losses alone cannot tell us whether the item is faulty.
The rationale error is a separate discovery from reading its evidence.

Each example is retained in both the report drill-down and the original
`audit_evidence.json` pairs; sample IDs join those files to the CSV. Source text
is quoted verbatim; the analysis and converted scores are additions made here.

## Detector changes and tests

No detector implementation bug was established in this run, so
`blame_cli/detectors.py` was left unchanged. Wrong judge reasoning is input data,
not a detector implementation bug. The cohort semantics and lack of a
domain-specific requirement rubric are limitations, not grounds to change
detectors until they produce more flattering results.

Four adapter tests check every score/order mapping, rejection of missing scores,
rejection of stale prompt/answer joins, unchanged-generation identity, and the
difference between the same actual winner after a swap versus a genuine reversal.
`make test` passes **85 tests**. Any later detector fix should have a failing
regression test first, as requested.

## Implications for the README and LinkedIn story

The defensible claim is: **“I ran blame on 1,500 public Arena-Hard answer pairs.
It surfaced 500 cases where GPT-4's preference changed across answer-order swaps.
I inspected 20 fired verdicts; all matched the documented evidence predicates.
The audit also exposed incorrect judge reasoning.”** Cite this directory and
state that these are historical published results and an agent-conducted audit.

The broader “Did the model fail, or did your eval?” framing should remain a
question and a triage workflow, not a promised causal classifier. This run
supports useful judge-review leads. It does not validate attribution of all
lost points, all five classes, “bad rubric” detection, production reliability,
or calibrated confidence. Keep the README's 0.99 values described as fixed
evidence strengths, not accuracy estimates. Call the default “unclassified loss”
in explanatory prose, even while its schema label remains `genuine_failure`.

The 34 cohort-loss prompts are useful review candidates. They cannot support a
claim that 34 eval questions are wrong: GPT-4 0314 was deliberately excluded
from the scored candidate cohort because it is their comparator. Include that
choice wherever reporting the cohort result. Conversely, a judge-disagreement
flag should not erase a real candidate error, as the missing-NumPy example shows.
An independent, larger labeled sample including default cases, a genuine
item-specific rubric dataset, and fixed-order repeated judges would be needed
to substantiate a stronger attribution story.
