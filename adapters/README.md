# Public result adapters

## Arena-Hard v0.1

`arena_hard.py` imports published judgments, not locally generated model answers or
new judge calls. Source: [lmarena-ai/arena-hard-auto](https://huggingface.co/datasets/lmarena-ai/arena-hard-auto),
revision `15f3746e21432264ce9b453999bde4f3c946d2e6`. The dataset card declares
Apache-2.0. Attribution and a license copy are in `realdata/arena_hard/`.

The fixed cohort is Claude 3 Opus, GPT-3.5 Turbo 0125, and Llama 3 70B Instruct,
each evaluated on all 500 prompts against the same GPT-4 0314 baseline by
GPT-4 1106 Preview. These are historical model results, not a current leaderboard.
The baseline is comparison context, not an additional scored candidate.

| Generic field | Published field / conversion |
| --- | --- |
| `task_id` | `arena-hard-v0.1:` + question `uid` |
| `model` | answer `model`, checked against judgment `model` |
| `run_id` | answer `ans_id`; both judge games share one generated answer |
| `instruction` | question `prompt`; checked against the answer's user message |
| `rubric_item_id` | constant `preference-vs-gpt-4-0314` |
| `rubric_item_text` | adapter-written explanation of preference scores plus the **complete baseline answer**, identical across models and games for this question |
| `output` | `messages[1].content.answer`, verbatim |
| `score` | candidate win `1`, tie `0.5`, loss `0`; `>>` and `>` collapse to the same preference direction |
| `judge_reasoning` | `games[i].judgment`, verbatim |
| `judge_run` | game index `1` or `2`; candidate is B in game 1 and A in game 2 |
| `error` | null; no candidate infrastructure error is supplied by this source |

The published `games[i].user_prompt` must exactly equal the reconstruction from
the question and both answers in the appropriate order. This rejects stale joins,
changed generations and reversed answer mapping. Unknown/missing scores fail;
they are never converted into zero credit. Duplicate UIDs and incomplete candidate
coverage also fail. All 1,500 supplied pairs and 3,000 games were accepted.

These are **pairwise preference observations**, not decomposed rubric criteria or
absolute correctness scores. A tie loses 0.5 generic units because blame treats
anything below 1 as lost credit. Those units are not benchmark rubric points.
No original five-level preference strength is used for instability: otherwise
"slightly better" versus "significantly better" could manufacture extra flips.

The two judgments swap answer order. They are explicit repeated evaluations of
the same answer pair, with an order intervention, **not identical-prompt stochastic
repeats**. `judge_unstable` therefore measures order sensitivity here, not a causal
proof of positional bias or repeatability at fixed prompt. The generic schema
does not encode prompt order as a separate covariate; game identity is documented
here and the raw games are retained for the hand-check sample.

No item-specific rubric was authored for this study. The common preference rubric
does not start with the literal requirement verbs that activate
`unstated_requirement`, so this dataset cannot validate that detector. Baseline
text is embedded as context, not turned into invented requirements. All three
candidate models losing to GPT-4 is a cohort fact, not evidence of a faulty item.

Run from the repository root (Python 3.11+ and `curl`, no login or packages):

```sh
python3 adapters/arena_hard.py --download
./blame report data/arena_hard/generic.jsonl --out data/arena_hard/full-report
python3 realdata/arena_hard/summarize.py
make test
```

Downloads and full reports remain in gitignored `data/`. `generic.manifest.json`
records pinned source URLs, SHA-256 hashes, byte counts and the generic file hash.
The summary script copies that manifest to `realdata/arena_hard/provenance.json`
and retains the aggregate counts and exactly the 20 audited drill-down items.
It also saves original source pairs for those items in `audit_evidence.json`.
The tracked reports explicitly disclose this reduction. To regenerate summaries
after a detector change, audit the selected items again if labels have changed;
the script refuses to silently substitute new verdicts.
