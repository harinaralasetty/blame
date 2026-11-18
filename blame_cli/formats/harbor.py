"""Read Harbor trial results: a trial directory, a job directory or a directory of jobs.

Written from a reading of harbor-framework/harbor at commit
3ee9f53e6b459712fdec4e8ce6613d7aa5610299 and unverified against real harness output.
Only <trial>/result.json and <trial>/verifier/test-stdout.txt are read; `config`,
`trial_uri` and `exception_traceback` are never read.
"""

from dataclasses import replace
import json
import math
from pathlib import Path

from ..model import Record, validate
from ._text import ERROR_CHARS, clip, redact


PROBE = "Harbor (a result.json with trial_name and agent_info in the directory or up to two levels below it)"
TAIL = 2000

# Copied from src/harbor/models/trial/error_policy.py at the commit above, grouped by
# what the failure says about the attempt. A name that is not listed is "unknown".
_NAMES = {
    # Harbor counts the reward: the attempt ran and its result stands.
    "agent": (
        "NonZeroAgentExitCodeError", "AgentTimeoutError", "ContextWindowExceededError",
        "OutputTokenExceededError", "ContextLengthExceededError", "OutputLengthExceededError",
        "AgentSafetyRefusalError", "ContentPolicyViolationError",
    ),
    "grader": (
        "VerifierTimeoutError", "RewardFileNotFoundError", "RewardFileEmptyError", "VerifierOutputParseError",
    ),
    "infra": (
        "EnvironmentStartTimeoutError", "SandboxBuildFailedError", "AgentSetupTimeoutError", "HealthcheckError",
        "SandboxLikelyOutOfMemoryError", "MemoryLimitExceededError", "SSHAccessError", "GKEExecStreamClosedError",
        "GKEPodNotFoundError", "RuntimeRequestError", "AddTestsDirError", "DownloadVerifierDirError",
        "ApiError", "ApiRateLimitError", "ApiInternalServerError", "ApiOverloadedError",
        "ApiConnectionClosedError", "ApiResponseStalledError", "UnknownApiError", "NetworkConnectionError",
        "ApiConnectionError", "ApiUsageLimitError", "RateLimitError", "InternalServerError",
        "ServiceUnavailableError", "APIConnectionError", "APIError", "Timeout",
        "APIResponseValidationError",
    ),
    "setup": (
        "UnsupportedModelParametersError", "BadRequestError", "UnprocessableEntityError", "UnsupportedParamsError",
        "BudgetExceededError", "AgentAuthenticationError", "ModelNotFoundError",
        "ApiProviderResourceNotFoundError", "AgentVersionTooOldError", "AuthenticationError",
        "PermissionDeniedError", "NotFoundError", "ServiceOperationsUnsupportedError", "VercelScopeError",
        "DspyImportError", "MissingExtraError", "CancelledError",
    ),
    # Listed by Harbor with no valid reward; what it says about the attempt is unverified.
    "unknown": ("RegradeError",),
}
ERROR_KIND_BY_NAME = {name: kind for kind, names in _NAMES.items() for name in names}


def _read(file: Path) -> tuple[dict | None, str | None]:
    """(object, None), or (None, why it could not be read)."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, exc.strerror or "cannot be read"
    except ValueError:
        return None, "not valid UTF-8 JSON"
    return (data, None) if isinstance(data, dict) else (None, "not a JSON object")


def _is_trial(data: dict | None) -> bool:
    return isinstance(data, dict) and "trial_name" in data and "agent_info" in data


def _result_files(path: Path) -> list[Path]:
    return [file for pattern in ("result.json", "*/result.json", "*/*/result.json")
            for file in sorted(path.glob(pattern)) if file.is_file()]


def detect(path: Path) -> bool:
    return path.is_dir() and any(_is_trial(_read(file)[0]) for file in _result_files(path))


def _string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _exception(data: dict) -> dict | None:
    """The trial-level exception, else the first one recorded on a step."""
    steps = data.get("step_results")
    found = [data.get("exception_info"),
             *(step.get("exception_info") for step in (steps if isinstance(steps, list) else ()) if isinstance(step, dict))]
    if any(info is not None and not isinstance(info, dict) for info in found):
        raise ValueError("exception_info must be an object or null")
    return next((info for info in found if info is not None), None)


def _flag(data, key: str) -> bool | None:
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, bool) else None


def _failure(data: dict) -> tuple[str | None, str | None, bool]:
    """(error text, error_kind, whether Harbor counts a recorded reward)."""
    info = _exception(data)
    if info is None:
        valid = _flag(data, "reward_valid")
        return None, None, True if valid is None else valid
    name = _string(info, "exception_type")
    message = info.get("exception_message")
    text = f"Harbor {name}"
    if isinstance(message, str) and message.strip():
        text += ": " + redact(clip(message, ERROR_CHARS))
    kind = ERROR_KIND_BY_NAME.get(name, "unknown")
    valid = name not in ERROR_KIND_BY_NAME or kind == "agent"   # an unlisted name keeps Harbor's default
    # What Harbor recorded about the reward wins over the override: reward_valid, then the policy.
    recorded = [(label, flag) for label, flag in (("reward_valid", _flag(data, "reward_valid")),
                                                  ("the recorded policy", _flag(info.get("policy"), "has_valid_reward")))
                if flag is not None]
    if recorded:
        valid = recorded[0][1]
    override = _flag(info.get("policy_override"), "has_valid_reward")
    if override is not None:
        note = f"policy_override has_valid_reward={str(override).lower()}"
        if recorded and recorded[0][1] != override:
            note += f", overruled by {recorded[0][0]}"
        else:
            kind = "agent" if override else "unknown" if kind == "agent" else kind
            valid = override
        text += f" ({note})"
    return text, kind, valid


def _reward(data: dict, counted: bool) -> tuple[float | None, str | None, list[str]]:
    """(score, why there is none, notes for the grader text)."""
    verifier = data.get("verifier_result")
    rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
    if not isinstance(rewards, dict) or not rewards:
        return None, "no verifier reward recorded", []
    key = "reward" if "reward" in rewards else next(iter(rewards)) if len(rewards) == 1 else None
    others = sorted(str(name) for name in rewards if name != key)
    notes = [f"Scored reward key: {key}."] if key not in (None, "reward") else []
    if others and key is not None:
        notes.append("Other reward keys, not scored: " + ", ".join(f"{name}={rewards[name]!r}" for name in others) + ".")
    if key is None:
        return None, "no reward key to score among: " + ", ".join(others), notes
    value = rewards[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        return None, f"reward {key}={value!r} is not a number in [0, 1]", notes
    if not counted:
        return None, f"Harbor does not count the recorded reward ({key}={value!r}) for this trial", notes
    return float(value), None, notes


def _record(data: dict, trial_dir: Path) -> Record | None:
    info = data["agent_info"]
    if not isinstance(info, dict):
        raise ValueError("agent_info must be an object")
    agent = _string(info, "name")
    if agent == "nop":
        return None
    model = ""
    if info.get("model_info") is not None:
        if not isinstance(info["model_info"], dict):
            raise ValueError("agent_info.model_info must be an object or null")
        provider = info["model_info"].get("provider")
        model = _string(info["model_info"], "name")
        if isinstance(provider, str) and provider.strip():
            model = f"{provider}/{model}"
    trial = _string(data, "trial_name")
    ident = data.get("id")
    checksum = data.get("task_checksum")
    error, kind, counted = _failure(data)
    score, missing, notes = _reward(data, counted)
    if missing:
        error = f"{error}; {missing}" if error else missing
        kind = kind or "unknown"
    try:
        stdout = (trial_dir / "verifier" / "test-stdout.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        stdout = ""
    return validate(Record(
        task_id=_string(data, "task_name"), model=model,
        run_id=f"{trial}@{ident[:8]}" if isinstance(ident, str) and ident else trial,
        instruction=None, rubric_item_id="reward", rubric_item_text=None, output=None, score=score,
        judge_reasoning="\n".join([*notes, redact(stdout)[-TAIL:]]).strip("\n") if notes else redact(stdout)[-TAIL:],
        error=error, agent=agent, role="reference" if agent == "oracle" else "candidate", error_kind=kind,
        task_version=checksum if isinstance(checksum, str) and checksum else None,
        job_id=trial_dir.parent.name or None,
    ))


def load(path: Path) -> tuple[list[Record], list[str]]:
    root = path.resolve()
    records, warnings = [], []
    for file in _result_files(root):
        name = file.relative_to(root).as_posix()
        data, problem = _read(file)
        if problem:
            warnings.append(f"{name}: unreadable result file skipped ({problem}).")
            continue
        if not _is_trial(data):
            continue  # a job-level summary
        try:
            record = _record(data, file.parent)
        except ValueError as exc:
            warnings.append(f"{name}: trial skipped ({exc}).")
            continue
        if record is None:
            warnings.append(f"{name}: trial of the nop agent skipped; it is not a system under test.")
        else:
            records.append(record)
    if not records:
        raise ValueError("no readable Harbor trial result found" + (": " + " ".join(warnings) if warnings else ""))
    return records, warnings


def merge(loaded: list[tuple[Path, list[Record]]]) -> tuple[list[Record], list[str]]:
    """Keep the first copy of a trial that was supplied more than once; warn on mixed task checksums.

    A trial is its task, system and run_id, whatever the job directory is called.
    """
    kept, warnings = [], []
    first: dict[tuple, Record] = {}
    versions: dict[str, set] = {}
    for record in (record for _, records in loaded for record in records):
        earlier = first.setdefault(record.attempt_key, record)
        if earlier is not record:
            differ = "" if replace(record, job_id=earlier.job_id) == earlier else "; the copies differ"
            warnings.append(f"Harbor trial {record.run_id} of task {record.task_id} was supplied more than once; "
                            f"the first copy is kept{differ}.")
            continue
        kept.append(record)
        if record.task_version:
            versions.setdefault(record.task_id, set()).add(record.task_version)
    warnings.extend(f"Harbor task {task} has {len(found)} task checksums across the supplied trials."
                    for task, found in sorted(versions.items()) if len(found) > 1)
    return kept, warnings
