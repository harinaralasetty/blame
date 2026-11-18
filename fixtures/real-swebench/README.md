Real harness output: swebench 5.0.2, local Docker, macOS arm64, 2026-11-18.

Three runs of `python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Lite
--max_workers 1 --instance_ids <ids> --run_id <run> --predictions_path <predictions>`. Kept:
each run's `run.json`, each instance's `report.json`, `patch.diff` and `run_instance.log`,
and the per-model summary the harness writes beside `logs/`. `eval.sh` and `test_output.txt`
(434 KB each) are left out; the reader does not read them. The home directory in one
traceback was replaced with `/home/user`; nothing else was edited. No model was called.

The instance `sympy__sympy-20590` and its gold patch come from the SWE-bench Lite dataset
(the patch is the SymPy project's own fix). The wrong patch adds one unrelated text file.

| Directory | Run | Predictions | What the harness recorded |
| --- | --- | --- | --- |
| `run` | `blame-m7-gold` | `gold` | `sympy__sympy-20590` resolved |
| `run` | `blame-m7-demo` | `demo-model`: a wrong patch for `sympy__sympy-20590`, an empty patch for `django__django-11099` | one unresolved, one in `empty_patch_ids` with no instance directory |
| `all-errors` | `blame-m7-gold` | `gold` | the image had no arm64 build and was not pulled, so the only instance is in `error_ids` with a `run_instance.log` and no `report.json` |

What this output showed about the format, checked in `tests/test_real_swebench.py`:

- Instance results are under `logs/run_evaluation/<run_id>/<model_dir>/<instance_id>/` in
  the directory the harness ran in, not `logs/evaluation`.
- The summary is `<model_dir>.<run_id>.json` beside `logs/`, one per model; no
  `results.json` is written inside the run directory. Its id lists carry the names the
  reader expected (`empty_patch_ids`, `error_ids`, `incomplete_ids`).
- A run in which every instance errored has no `report.json` at all.
