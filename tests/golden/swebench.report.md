# blame report

Scored observations: 7. Lost items: 6. Lost points: 6. Ungraded attempts: 2. Reference results (not counted): 2.

Each scored observation below 1 is a lost item, including repeated judges. 2 attempts were never graded and are listed as ungraded.

Confidence values are fixed heuristic strengths, not calibrated probabilities.

## By class

| class | category | lost_items | lost_points | ungraded_items |
| --- | --- | --- | --- | --- |
| infra | infra | 1 | 1.0 | 0 |
| setup_error | setup | 0 | 0 | 0 |
| grader_error | grader | 0 | 0 | 0 |
| judge_unstable | grader | 1 | 1.0 | 0 |
| reference_flaky | grader | 0 | 0 | 0 |
| reference_fails | task | 2 | 2.0 | 0 |
| item_everyone_loses | task | 0 | 0 | 0 |
| unstated_requirement | instruction | 0 | 0 | 0 |
| attempts_flip | unexplained | 0 | 0 | 0 |
| unclassified_error | unexplained | 1 | 1.0 | 2 |
| genuine_failure | unexplained | 1 | 1.0 | 0 |

## By model

| model | scored_items | lost_items | lost_points | ungraded_items | infra | setup_error | grader_error | judge_unstable | reference_flaky | reference_fails | item_everyone_loses | unstated_requirement | attempts_flip | unclassified_error | genuine_failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| example__model-a | 7 | 6 | 6.0 | 2 | 1 | 0 | 0 | 1 | 0 | 2 | 0 | 0 | 0 | 3 | 1 |

## Input warnings

- fixtures/swebench-eval: run-a/results.json: 2 instances have no prediction (incomplete_ids) and are not in the report.
- fixtures/swebench-eval: run-b/example__model-a/example__widgets-108: no patch.diff; the run id run-b stands in for the patch.
- fixtures/swebench-eval: run-b/example__model-a/example__widgets-110/report.json: unreadable result file skipped (not a JSON report for this instance).
- fixtures/swebench-eval: run-b/results.json: 1 empty-patch or error ids could not be tied to a model directory and were skipped.

## Failed tasks

One row per task with a lost or ungraded attempt. The label is the most frequent verdict on the task; `labels` counts every detector match.

| task_id | systems_attempted | systems_failed | reference | primary_label | category | rule strength | labels | next_step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| example__widgets-101 | 1 | 1 | passed 1 of 1 attempts | judge_unstable | grader | 0.99 | judge_unstable 1 | Compare the gradings of this output before trusting either score. |
| example__widgets-102 | 1 | 1 | passed 0 of 1 attempts | reference_fails | task | 0.60 | reference_fails 2 | Rerun the reference before scoring systems on this task. |
| example__widgets-103 | 1 | 1 | no reference run supplied | infra | infra | 0.80 | infra 1 | Rerun the attempt after checking the recorded error or output. |
| example__widgets-105 | 1 | 0 | no reference run supplied | unclassified_error | unexplained | 0.40 | unclassified_error 1 | Read the recorded error; the format does not classify it. |
| example__widgets-104 | 1 | 1 | no reference run supplied | genuine_failure | unexplained | 0.50 | genuine_failure 1 | Read the output and the grader note; no rule explains this loss. |
| example__widgets-106 | 1 | 0 | no reference run supplied | unclassified_error | unexplained | 0.40 | unclassified_error 1 | Read the recorded error; the format does not classify it. |
| example__widgets-108 | 1 | 1 | no reference run supplied | unclassified_error | unexplained | 0.40 | unclassified_error 1 | Read the recorded error; the format does not classify it. |

## Lost item drill-down

### example__widgets-101 / example__model-a / resolved

Verdict: judge_unstable; rule strength: 0.99; score: 0; run: patch:364d4af8f531; judge_run: 1.

Record: 665d306ae08831b1fcac4766a528128f5a170c8519b1596973fb98b4d9fdcc5c

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>diff --git a/widgets/scale.py b/widgets/scale.py<br>--- a/widgets/scale.py<br>+++ b/widgets/scale.py<br>@@ -1,2 +1,2 @@<br> def scale(value):<br>-    return value<br>+    return value * 2<br></q>

judge_reasoning: <q>patch_exists: true. patch_successfully_applied: true.<br>FAIL_TO_PASS: 0 passed, 1 failed (tests/test_scale.py::test_double).<br>PASS_TO_PASS: 1 passed, 0 failed.<br>FAIL_TO_FAIL: 0 passed, 0 failed.<br>PASS_TO_FAIL: 0 passed, 0 failed.</q>

error: <q>None</q>

- output_quote: <q>"diff --git a/widgets/scale.py b/widgets/scale.py\n--- a/widgets/scale.py\n+++ b/widgets/scale.py\n@@ -1,2 +1,2 @@\n def scale(value):\n-    return value\n+    return value * 2\n"</q>
- judge_scores: <q>[{"judge_run": 1, "score": 0.0}, {"judge_run": 2, "score": 1.0}]</q>
- different_score_pairs: <q>1</q>
- judge_pairs: <q>1</q>
- flip_rate: <q>1.0</q>

Detector matches: judge_unstable

### example__widgets-102 / example__model-a / resolved

Verdict: reference_fails; rule strength: 0.60; score: 0; run: patch:c81836ef4ef3; judge_run: 1.

Record: af38197c86f955235c91aab499a973df79840f2969eec221986b64440dc9b6d4

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>diff --git a/widgets/trim.py b/widgets/trim.py<br>--- a/widgets/trim.py<br>+++ b/widgets/trim.py<br>@@ -1,2 +1,2 @@<br> def trim(value):<br>-    return value<br>+    return value.strip()<br></q>

judge_reasoning: <q>patch_exists: true. patch_successfully_applied: true.<br>FAIL_TO_PASS: 0 passed, 2 failed (tests/test_trim.py::test_tabs, tests/test_trim.py::test_newline).<br>PASS_TO_PASS: 1 passed, 1 failed (tests/test_trim.py::test_inner).<br>FAIL_TO_FAIL: 0 passed, 0 failed.<br>PASS_TO_FAIL: 0 passed, 0 failed.</q>

error: <q>None</q>

- observed: <q>"The reference solution did not pass in 1 of 1 attempts."</q>
- reference_runs: <q>[{"system": "gold", "run_id": "patch:1a97f9a32c0f", "score": 0.0}]</q>
- task_version: <q>"task version not available"</q>

Detector matches: reference_fails

### example__widgets-103 / example__model-a / resolved

Verdict: infra; rule strength: 0.80; score: 0; run: patch:bea26aa65518; judge_run: None.

Record: 4d59745f0571bf2984771592749062f6103e24d4376ccd8d8a3f60808102f632

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>diff --git a/widgets/join.py b/widgets/join.py<br>--- a/widgets/join.py<br>+++ b/widgets/join.py<br>@@ -1,2 +1,2 @@<br> def join(value):<br>-    return value<br>+    return ''.join(value)<br></q>

judge_reasoning: <q>patch_exists: true. patch_successfully_applied: false.<br>The harness found no parseable test output.</q>

error: <q>SWE-bench log pattern: out_of_memory</q>

- observed: <q>"The harness classified this attempt's error as an infrastructure fault."</q>
- rule: <q>"error_kind"</q>
- quote: <q>"SWE-bench log pattern: out_of_memory"</q>

Detector matches: infra

### example__widgets-105 / example__model-a / resolved

Verdict: unclassified_error; rule strength: 0.40; score: not graded; run: patch:f002f9743640; judge_run: None.

Record: b39c15a6a1cde044311cde9e5df9835e9ad80eb351abe0853c5ec93f0b0be084

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>diff --git a/widgets/split.py b/widgets/split.py<br>--- a/widgets/split.py<br>+++ b/widgets/split.py<br>@@ -1,2 +1,2 @@<br> def split(value):<br>-    return value<br>+    return value.split()<br></q>

judge_reasoning: <q></q>

error: <q>Intermediate patch written to ~/logs/patch.diff<br>Applying patch<br>Traceback (most recent call last):<br>  File "~/harness/run.py", line 10<br>EvaluationError: example__widgets-105: container exited before the tests ran</q>

- observed: <q>"The harness recorded an error that the format does not classify."</q>
- error: <q>"Intermediate patch written to ~/logs/patch.diff\nApplying patch\nTraceback (most recent call last):\n  File \"~/harness/run.py\", line 10\nEvaluationError: example__widgets-105: container exited before the tests ran"</q>

Detector matches: unclassified_error

### example__widgets-104 / example__model-a / resolved

Verdict: genuine_failure; rule strength: 0.50; score: 0; run: patch:empty; judge_run: None.

Record: 88122b3c5a4cf72c2c4a0138e88a2a76c2ef9853801c78b4394b33462b5a63c8

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q></q>

judge_reasoning: <q></q>

error: <q>empty patch</q>

- score: <q>0.0</q>
- rubric_quote: <q>null</q>
- output_quote: <q>""</q>
- judge_reasoning_quote: <q>""</q>
- note: <q>"No precision-first detector fired. Default, not a proven model failure."</q>
- error: <q>"empty patch"</q>

Detector matches: 

### example__widgets-106 / example__model-a / resolved

Verdict: unclassified_error; rule strength: 0.40; score: not graded; run: run-a; judge_run: None.

Record: a960b0bd575bd0198cbdd36f16ce49a25ef56faf7e07c1d3ee387fea445ce4f9

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q></q>

error: <q>no report.json</q>

- observed: <q>"The harness recorded an error that the format does not classify."</q>
- error: <q>"no report.json"</q>

Detector matches: unclassified_error

### example__widgets-102 / example__model-a / resolved

Verdict: reference_fails; rule strength: 0.60; score: 0; run: patch:c81836ef4ef3; judge_run: 2.

Record: a2603ad7c972a44fdb7563b7ee537d54f64165df6355281cdec12994c3823121

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>diff --git a/widgets/trim.py b/widgets/trim.py<br>--- a/widgets/trim.py<br>+++ b/widgets/trim.py<br>@@ -1,2 +1,2 @@<br> def trim(value):<br>-    return value<br>+    return value.strip()<br></q>

judge_reasoning: <q>patch_exists: true. patch_successfully_applied: true.<br>FAIL_TO_PASS: 0 passed, 2 failed (tests/test_trim.py::test_tabs, tests/test_trim.py::test_newline).<br>PASS_TO_PASS: 1 passed, 1 failed (tests/test_trim.py::test_inner).<br>FAIL_TO_FAIL: 0 passed, 0 failed.<br>PASS_TO_FAIL: 0 passed, 0 failed.</q>

error: <q>None</q>

- observed: <q>"The reference solution did not pass in 1 of 1 attempts."</q>
- reference_runs: <q>[{"system": "gold", "run_id": "patch:1a97f9a32c0f", "score": 0.0}]</q>
- task_version: <q>"task version not available"</q>

Detector matches: reference_fails

### example__widgets-108 / example__model-a / resolved

Verdict: unclassified_error; rule strength: 0.40; score: 0; run: run-b; judge_run: None.

Record: 7362124114f01b0820b1450f414705615e5e995009e7aa766d736769f5a8be4e

instruction: <q>not available in this format</q>

rubric_item_text: <q>not available in this format</q>

output: <q>not available in this format</q>

judge_reasoning: <q>patch_exists: true. patch_successfully_applied: false.<br>The harness found no parseable test output.</q>

error: <q>SWE-bench log pattern: no_tests_collected</q>

- observed: <q>"The harness recorded an error that the format does not classify."</q>
- error: <q>"SWE-bench log pattern: no_tests_collected"</q>

Detector matches: unclassified_error
