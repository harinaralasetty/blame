"""Validated records shared by readers and pure detectors."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math


@dataclass(frozen=True)
class LabelInfo:
    name: str
    category: str
    next_step: str


# The only source of precedence: the first label here with a finding is the verdict.
# The last label is the default when no detector fires.
LABELS = (
    LabelInfo("infra", "infra", "Rerun the attempt after checking the recorded error or output."),
    LabelInfo("judge_unstable", "grader", "Compare the gradings of this output before trusting either score."),
    LabelInfo("item_everyone_loses", "task", "Check the task and its checks against a known-good solution."),
    LabelInfo("unstated_requirement", "instruction", "Check whether the instruction states what the rubric requires."),
    LabelInfo("genuine_failure", "unexplained", "Read the output and the grader note; no rule explains this loss."),
)
CLASSES = tuple(label.name for label in LABELS)


ROLES = ("candidate", "reference")
ERROR_KINDS = ("infra", "setup", "grader", "agent", "unknown")


def system_name(agent: str | None, model: str) -> str:
    """The system under test: agent and model, whichever are set."""
    return " / ".join(part for part in (agent, model) if part)


@dataclass(frozen=True)
class Record:
    """One graded check of one attempt."""

    task_id: str
    model: str                       # may be "" only when agent is set
    run_id: str                      # identifies one attempt (generation, trial, epoch, patch)
    instruction: str | None          # None: the format does not carry it
    rubric_item_id: str
    rubric_item_text: str | None
    output: str | None               # None: not carried; "": known empty
    score: float | None              # None: never graded (requires error)
    judge_reasoning: str
    judge_run: int | None = None     # repeated grading of the same output
    error: str | None = None
    agent: str | None = None
    role: str = "candidate"          # one of ROLES
    error_kind: str | None = None    # one of ERROR_KINDS; None keeps the v1 rule (an error is infra)
    task_version: str | None = None
    job_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        """Generic JSONL: every v1 text field is required; v2 keys are optional."""
        if not isinstance(data, dict):
            raise ValueError("record must be an object")
        fields = (
            "task_id", "model", "run_id", "instruction", "rubric_item_id",
            "rubric_item_text", "output", "judge_reasoning",
        )
        for field in fields:
            if field not in data or not isinstance(data[field], str):
                raise ValueError(f"{field} must be a string")
            if field not in ("output", "judge_reasoning") and not data[field].strip():
                raise ValueError(f"{field} must not be empty")
        error = data.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("error must be a string or null")
        score = data.get("score")
        if score is None and "score" in data and error and error.strip():
            pass  # never graded; the error says why
        elif (isinstance(score, bool) or not isinstance(score, (int, float))
                or not 0 <= score <= 1 or not math.isfinite(score)):
            raise ValueError("score must be a finite number in [0, 1]")
        else:
            score = float(score)
        judge = data.get("judge_run")
        if judge is not None and type(judge) is not int:
            raise ValueError("judge_run must be an integer or null")
        extra = {}
        for field in ("agent", "role", "error_kind", "task_version", "job_id"):
            value = data.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string or null")
            extra[field] = value
        return validate(cls(**{field: data[field] for field in fields}, score=score,
                            judge_run=judge, error=error, **extra))

    @property
    def system(self) -> str:
        return system_name(self.agent, self.model)

    @property
    def item_key(self) -> tuple:
        return self.task_id, self.rubric_item_id

    @property
    def attempt_key(self) -> tuple:
        return self.task_id, self.system, self.run_id

    @property
    def judge_key(self) -> tuple:
        return (self.task_id, self.model, self.run_id, self.rubric_item_id,
                self.output, self.instruction, self.rubric_item_text)

    @property
    def record_id(self) -> str:
        # Includes the score and context, so changed inputs cannot silently reuse labels.
        data = json.dumps(record_dict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode()).hexdigest()


V1_FIELDS = tuple(Record.__dataclass_fields__)[:11]


def record_dict(record: Record) -> dict:
    """The v1 keys always; a v2 key only when it is not the default.

    This keeps record ids and label files of v1 data unchanged.
    """
    data = asdict(record)
    defaults = Record.__dataclass_fields__
    return {key: value for key, value in data.items()
            if key in V1_FIELDS or value != defaults[key].default}


def validate(record: Record) -> Record:
    """The checks every reader's records must pass. Raises ValueError."""
    for field in ("task_id", "run_id", "rubric_item_id"):
        value = getattr(record, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must not be empty")
    if not (record.model or record.agent):
        raise ValueError("model or agent must be set")
    if record.score is None:
        if not (record.error and record.error.strip()):
            raise ValueError("a record without a score needs an error")
    elif (isinstance(record.score, bool) or not isinstance(record.score, (int, float))
            or not math.isfinite(record.score) or not 0 <= record.score <= 1):
        raise ValueError("score must be a finite number in [0, 1]")
    if record.role not in ROLES:
        raise ValueError("role must be one of: " + ", ".join(ROLES))
    if record.error_kind is not None and record.error_kind not in ERROR_KINDS:
        raise ValueError("error_kind must be null or one of: " + ", ".join(ERROR_KINDS))
    return record


@dataclass(frozen=True)
class Finding:
    label: str
    confidence: float
    evidence: dict
