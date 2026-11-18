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


@dataclass(frozen=True)
class Record:
    task_id: str
    model: str
    run_id: str
    instruction: str
    rubric_item_id: str
    rubric_item_text: str
    output: str
    score: float
    judge_reasoning: str
    judge_run: int | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
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
        score = data.get("score")
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not 0 <= score <= 1 or not math.isfinite(score)):
            raise ValueError("score must be a finite number in [0, 1]")
        judge = data.get("judge_run")
        if judge is not None and type(judge) is not int:
            raise ValueError("judge_run must be an integer or null")
        error = data.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("error must be a string or null")
        return cls(**{field: data[field] for field in fields}, score=float(score),
                   judge_run=judge, error=error)

    @property
    def item_key(self) -> tuple:
        return self.task_id, self.rubric_item_id

    @property
    def judge_key(self) -> tuple:
        return (self.task_id, self.model, self.run_id, self.rubric_item_id,
                self.output, self.instruction, self.rubric_item_text)

    @property
    def record_id(self) -> str:
        # Includes the score and context, so changed inputs cannot silently reuse labels.
        data = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass(frozen=True)
class Finding:
    label: str
    confidence: float
    evidence: dict
