Hand-written from source reading at commit 3ee9f53e6b459712fdec4e8ce6613d7aa5610299, not harness output.

The commit is `harbor-framework/harbor@3ee9f53e6b459712fdec4e8ce6613d7aa5610299`
(`src/harbor/models/trial/result.py`, `trial/error_policy.py`, `verifier/result.py`,
`agent/name.py`). No Harbor run produced these files and the reader that parses them
is unverified against real harness output. Every name, path, id and message here is
made up; there is no third-party data.

The directory is shaped like one Harbor job: a job-level `result.json` and one
directory per trial holding `result.json` and sometimes `verifier/test-stdout.txt`.
Two tasks, the `oracle` reference and two agents.

| Trial | What it covers |
| --- | --- |
| `sort-numbers__ref1`, `__ref2` | the reference passes once and fails once |
| `sort-numbers__aaa1` | a failure with an extra reward key and a home path in the test output |
| `sort-numbers__aaa2` | `AgentTimeoutError`: an error Harbor counts as a valid failure |
| `sort-numbers__bbb1` | a pass |
| `sort-numbers__bbb2` | an infrastructure exception with `policy_override.has_valid_reward: true` |
| `sort-numbers__bbb3` | an exception name Harbor does not list, no recorded policy |
| `sort-numbers__nop1` | a `nop` agent trial, skipped |
| `parse-log__ref1` | the reference fails |
| `parse-log__aaa1` | a plain failure |
| `parse-log__aaa2` | `RewardFileNotFoundError`: a verifier error, no reward |
| `parse-log__aaa3` | an unlisted exception whose recorded policy says the reward is not valid |
| `parse-log__aaa4` | two reward keys and none named `reward` |
| `parse-log__bbb1` | `EnvironmentStartTimeoutError` with a home path in the message |
| `parse-log__bbb2` | `AuthenticationError`: a setup error |
| `parse-log__bbb3` | an exception recorded on a step, not on the trial |
| `parse-log__bad1` | a truncated `result.json`, skipped with a warning |

Each trial file also carries `config`, `trial_uri` and `exception_traceback` with
made-up home paths. The reader never reads those keys, and the paths it does copy
are shortened to `~`. The expected report is `tests/golden/harbor.report.json` and
`tests/golden/harbor.report.md`.
