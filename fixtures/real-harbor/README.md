Real harness output: Harbor 0.24.0, local Docker environment, macOS arm64, 2026-11-18.

Six jobs, each `harbor run -p <task> -a <agent> -n 1 -o jobs --job-name <job>`. Only each
job's and trial's `result.json` and the trial's `verifier/test-stdout.txt` are kept. Local
paths in `trial_uri`, messages and tracebacks were replaced with `/work`, `/tmp` and
`/home/user`; nothing else was edited. No model was called and there is no third-party data.

The tasks were scaffolded with `harbor init -t`:

- `hello`: write `hello` to `/app/hello.txt`; `tests/test.sh` prints PASS or FAIL and writes the reward.
- `broken`: the same task with `RUN exit 7` in its Dockerfile, so the image never builds.
- `slow`: the same task with `[agent] timeout_sec = 5.0`.

`scripted` is a model-less custom agent (`-a scripted_agent:ScriptedAgent --ak cmd=...`) that
runs one shell command in the environment.

| Job | Agent | Task | What Harbor recorded |
| --- | --- | --- | --- |
| `oracle-run` | `oracle` | `hello` | reward 1.0 |
| `nop-run` | `nop` | `hello` | reward 0.0 |
| `broken-run` | `oracle` | `broken` | `RuntimeError` from `docker compose build`, no verifier result |
| `cand-wrong` | `scripted` (`-k 2`, writes `goodbye`) | `hello` | two trials, reward 0.0 each |
| `cand-broken` | `scripted` | `broken` | `RuntimeError` from `docker compose build`, no verifier result |
| `cand-slow` | `scripted` (`sleep 60`) | `slow` | `AgentTimeoutError`, reward 0.0 |

What this output showed about the format, checked in `tests/test_real_harbor.py`:

- `exception_info` holds `exception_type`, `exception_message`, `exception_traceback` and
  `occurred_at`. This version writes no `policy`, `policy_override` or `reward_valid`.
- A failed image build is a plain `RuntimeError`, not `SandboxBuildFailedError`, so the
  exception name alone does not say what failed. `agent_setup` and `agent_execution` are
  null in that case.
