Hand-written from source reading at commit 02e7a74ffd0b707aab73d203fe87bdc7c76afc8e, not harness output.

The commit is `SWE-bench/SWE-bench@02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`
(`swebench/harness/grading.py`, `run_evaluation.py`, `reporting.py`,
`infra_failure.py`, `constants/__init__.py`). No SWE-bench run produced these files
and the reader that parses them is unverified against real harness output. Every
instance id, model name, patch, test name and log line here is made up; nothing comes
from the SWE-bench dataset or from `SWE-bench/experiments`.

The directory is shaped like `logs/evaluation` after two runs:
`<run_id>/<model_dir>/<instance_id>/{report.json, patch.diff, run_instance.log}` and
`<run_id>/results.json`. `run-a` holds one model. `run-b` grades the same model again
and also holds `gold`, the reference patches; a real run has one model per predictions
file, so two model directories under one run id is unusual but possible.

| Instance | `run-a` | `run-b` |
| --- | --- | --- |
| `example__widgets-101` | not resolved | the same patch, resolved; `gold` resolved |
| `example__widgets-102` | not resolved | the same patch, not resolved; `gold` not resolved |
| `example__widgets-103` | `infra_failure` with reason `out_of_memory` | |
| `example__widgets-104` | in `empty_patch_ids` | in `empty_patch_ids`, and no model directory to tie it to |
| `example__widgets-105` | no `report.json`; a log with made-up home paths | |
| `example__widgets-106` | in `error_ids`, no directory | |
| `example__widgets-107`, `-109` | in `incomplete_ids` | |
| `example__widgets-108` | | reason `no_tests_collected` without `infra_failure`; no `patch.diff` |
| `example__widgets-110` | | a truncated `report.json`, skipped with a warning |

The expected report is `tests/golden/swebench.report.json` and
`tests/golden/swebench.report.md`.
