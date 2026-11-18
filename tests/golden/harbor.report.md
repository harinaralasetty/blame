# blame report

Scored observations: 7. Lost items: 6. Lost points: 6. Ungraded attempts: 5. Reference results (not counted): 3.

Each scored observation below 1 is a lost item, including repeated judges. 5 attempts were never graded and are listed as ungraded.

Confidence values are fixed heuristic strengths, not calibrated probabilities.

## By class

| class | category | lost_items | lost_points | ungraded_items |
| --- | --- | --- | --- | --- |
| infra | infra | 0 | 0 | 1 |
| setup_error | setup | 0 | 0 | 1 |
| grader_error | grader | 0 | 0 | 1 |
| judge_unstable | grader | 0 | 0 | 0 |
| reference_flaky | grader | 4 | 4.0 | 0 |
| reference_fails | task | 2 | 2.0 | 2 |
| item_everyone_loses | task | 0 | 0 | 0 |
| unstated_requirement | instruction | 0 | 0 | 0 |
| attempts_flip | unexplained | 0 | 0 | 0 |
| unclassified_error | unexplained | 0 | 0 | 0 |
| genuine_failure | unexplained | 0 | 0 | 0 |

## By model

| model | scored_items | lost_items | lost_points | ungraded_items | infra | setup_error | grader_error | judge_unstable | reference_flaky | reference_fails | item_everyone_loses | unstated_requirement | attempts_flip | unclassified_error | genuine_failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-code / example/model-a | 3 | 3 | 3.0 | 3 | 0 | 0 | 1 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 0 |
| codex / model-b | 4 | 3 | 3.0 | 2 | 1 | 1 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |

## Input warnings

- fixtures/harbor-job: parse-log__bad1/result.json: unreadable result file skipped (not valid UTF-8 JSON).
- fixtures/harbor-job: sort-numbers__nop1/result.json: trial of the nop agent skipped; it is not a system under test.

## Failed tasks

One row per task with a lost or ungraded attempt. The label is the most frequent verdict on the task; `labels` counts every detector match.

| task_id | systems_attempted | systems_failed | reference | primary_label | category | rule strength | labels | next_step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| parse-log | 2 | 2 | passed 0 of 1 attempts | reference_fails | task | 0.75 | infra 1, setup_error 1, grader_error 1, reference_fails 7, item_everyone_loses 2, unclassified_error 2 | Rerun the reference before scoring systems on this task. |
| sort-numbers | 2 | 2 | passed 1 of 2 attempts | reference_flaky | grader | 0.85 | reference_flaky 4, attempts_flip 2, unclassified_error 1 | Rerun the reference solution several times before scoring systems on this task. |

## Lost item drill-down

### parse-log / claude-code / example/model-a / reward

Verdict: reference_fails; rule strength: 0.75; score: 0; run: parse-log__aaa1@0000000a; judge_run: None.

Record: 56c22bca3be37836933f79b27695c19e202341a78f2a41deff65ca778ac576fb

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q>FAILED tests/test_parse.py::test_timestamps<br>1 failed in 0.50s<br></q>

error: <q>None</q>

- observed: <q>"The reference solution did not pass in 1 of 1 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "parse-log__ref1@00000009", "score": 0.0}]</q>
- task_version: <q>"same as this attempt"</q>

Detector matches: reference_fails, item_everyone_loses

### parse-log / claude-code / example/model-a / reward

Verdict: grader_error; rule strength: 0.85; score: not graded; run: parse-log__aaa2@0000000b; judge_run: None.

Record: 0fb1ecb9b006666e7a0a2f8e1b96880c2c9038751360cd579f01c213aaf3633a

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor RewardFileNotFoundError: No reward file found at /logs/verifier/reward.txt; no verifier reward recorded</q>

- observed: <q>"The harness recorded that the verifier did not produce a result for this attempt."</q>
- error: <q>"Harbor RewardFileNotFoundError: No reward file found at /logs/verifier/reward.txt; no verifier reward recorded"</q>

Detector matches: grader_error, reference_fails

### parse-log / claude-code / example/model-a / reward

Verdict: reference_fails; rule strength: 0.75; score: not graded; run: parse-log__aaa3@0000000c; judge_run: None.

Record: a9050065b28e8cc89a00c345a4f37df62e312ec944e853b9819ac9f486d1fc7c

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor CustomHarnessError: post-run hook failed; Harbor does not count the recorded reward (reward=1) for this trial</q>

- observed: <q>"The reference solution did not pass in 1 of 1 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "parse-log__ref1@00000009", "score": 0.0}]</q>
- task_version: <q>"same as this attempt"</q>

Detector matches: reference_fails, unclassified_error

### parse-log / claude-code / example/model-a / reward

Verdict: reference_fails; rule strength: 0.75; score: not graded; run: parse-log__aaa4@0000000d; judge_run: None.

Record: 16ec6493ed609fff773cd58aa8e1bb6c7b0a983c05786f9d48c6ff4e193b6a4e

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>no reward key to score among: precision, recall</q>

- observed: <q>"The reference solution did not pass in 1 of 1 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "parse-log__ref1@00000009", "score": 0.0}]</q>
- task_version: <q>"same as this attempt"</q>

Detector matches: reference_fails, unclassified_error

### parse-log / codex / model-b / reward

Verdict: infra; rule strength: 0.80; score: not graded; run: parse-log__bbb1@0000000e; judge_run: None.

Record: 4e127810ebf62a3c399e125a11f5d5e5f2749ff406af2c289f9c60b2ac89004b

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor EnvironmentStartTimeoutError: Environment did not start in 600 s; see ~/.cache/harbor/build.log; no verifier reward recorded</q>

- observed: <q>"The harness classified this attempt's error as an infrastructure fault."</q>
- rule: <q>"error_kind"</q>
- quote: <q>"Harbor EnvironmentStartTimeoutError: Environment did not start in 600 s; see ~/.cache/harbor/build.log; no verifier reward recorded"</q>

Detector matches: infra, reference_fails

### parse-log / codex / model-b / reward

Verdict: setup_error; rule strength: 0.85; score: not graded; run: parse-log__bbb2@0000000f; judge_run: None.

Record: a9817bff57137ff883cca6047daec520da2f342928019b7a1228403be2b89bf8

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor AuthenticationError: Invalid API key for provider example; no verifier reward recorded</q>

- observed: <q>"The harness recorded a setup or configuration error for this attempt."</q>
- error: <q>"Harbor AuthenticationError: Invalid API key for provider example; no verifier reward recorded"</q>

Detector matches: setup_error, reference_fails

### parse-log / codex / model-b / reward

Verdict: reference_fails; rule strength: 0.75; score: 0; run: parse-log__bbb3@00000010; judge_run: None.

Record: d3668480b476c2385c3119deb73d8a34bfcdd1b1dde059954821c34bea2e8b93

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor NonZeroAgentExitCodeError: Agent exited with code 2</q>

- observed: <q>"The reference solution did not pass in 1 of 1 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "parse-log__ref1@00000009", "score": 0.0}]</q>
- task_version: <q>"same as this attempt"</q>

Detector matches: reference_fails, item_everyone_loses

### sort-numbers / claude-code / example/model-a / reward

Verdict: reference_flaky; rule strength: 0.85; score: 0; run: sort-numbers__aaa1@00000003; judge_run: None.

Record: 8f9ef7844337854fc5e767fa3a65c962ec8f1f0a368e3ee0a3fda0e2c8b05b6d

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q>Other reward keys, not scored: tests_passed=0.4.<br>collected 5 items<br>FAILED tests/test_sort.py::test_large_input - read ~/work/out.txt<br>3 failed, 2 passed in 1.20s</q>

error: <q>None</q>

- observed: <q>"The reference solution passed 1 of 2 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "sort-numbers__ref1@00000001", "score": 1.0}, {"system": "oracle", "run_id": "sort-numbers__ref2@00000002", "score": 0.0}]</q>

Detector matches: reference_flaky

### sort-numbers / claude-code / example/model-a / reward

Verdict: reference_flaky; rule strength: 0.85; score: 0; run: sort-numbers__aaa2@00000004; judge_run: None.

Record: 94a0a3860526f4230a46545efc20feace4ac8156360a5fd7d5821d1aaf42fbbc

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q>5 failed in 0.90s<br></q>

error: <q>Harbor AgentTimeoutError: Agent execution timed out after 600 seconds</q>

- observed: <q>"The reference solution passed 1 of 2 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "sort-numbers__ref1@00000001", "score": 1.0}, {"system": "oracle", "run_id": "sort-numbers__ref2@00000002", "score": 0.0}]</q>

Detector matches: reference_flaky

### sort-numbers / codex / model-b / reward

Verdict: reference_flaky; rule strength: 0.85; score: 0; run: sort-numbers__bbb2@00000006; judge_run: None.

Record: 8e472ea0859783a76f6d4bfdd8a484856c48ad1cda0e7e67b896c0febb6e4fd4

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor ApiRateLimitError: 429 from provider (policy_override has_valid_reward=true)</q>

- observed: <q>"The reference solution passed 1 of 2 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "sort-numbers__ref1@00000001", "score": 1.0}, {"system": "oracle", "run_id": "sort-numbers__ref2@00000002", "score": 0.0}]</q>

Detector matches: reference_flaky, attempts_flip

### sort-numbers / codex / model-b / reward

Verdict: reference_flaky; rule strength: 0.85; score: 0; run: sort-numbers__bbb3@00000007; judge_run: None.

Record: 1c51af4757e97746584370f43a019672c4ed6a9192eb7fb4fccf43505c3ee246

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>Harbor WeirdSandboxError: sandbox reported state 7</q>

- observed: <q>"The reference solution passed 1 of 2 attempts."</q>
- reference_runs: <q>[{"system": "oracle", "run_id": "sort-numbers__ref1@00000001", "score": 1.0}, {"system": "oracle", "run_id": "sort-numbers__ref2@00000002", "score": 0.0}]</q>

Detector matches: reference_flaky, attempts_flip, unclassified_error
