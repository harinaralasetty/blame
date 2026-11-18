"""Pure, precision-first detectors. None perform I/O or call an LLM."""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import re
from typing import Callable, Protocol, Sequence

from .model import CLASSES, Finding, Record, record_dict


# The single source of truth for infrastructure rules, including non-regex rules.
# Regex rules require the whole stripped output to look like an error message.
INFRA_RULES = (
    ("error_field", None, 0.99),
    ("empty_output", None, 0.98),
    ("timeout", r"(?:error:\s*)?(?:(?:request|connection|operation)\s+)?(?:timed?\s*out|timeout(?:error)?)(?::\s*upstream)?[.!]?", 0.95),
    ("rate_limit", r"(?:error:\s*)?(?:rate[ -]limit(?:ed| exceeded)|too many requests|http(?: error)?\s*:?\s*429(?:\s+too many requests)?|429\s+too many requests)[.!]?", 0.96),
    ("server_error", r"(?:error:\s*)?(?:(?:http(?: error)?|status(?: code)?)\s*[:=]?\s*5\d\d(?:\s+(?:internal server error|bad gateway|service unavailable|gateway timeout))?|5\d\d\s+(?:internal server error|bad gateway|service unavailable|gateway timeout)|bad gateway|gateway timeout|internal server error|service unavailable)[.!]?", 0.96),
    ("missing_artifact", r"(?:error:\s*)?(?:missing (?:required )?artifact|(?:required )?artifact (?:is )?(?:missing|not found))(?::\s*[\w./\\-]+)?[.!]?", 0.94),
)


# Attempts the harness says ended for one of these reasons are no evidence about the
# task or the system, so cross-attempt detectors leave them out.
EXCLUDED_KINDS = ("infra", "setup", "grader")


def infra(record: Record) -> Finding | None:
    if record.score == 1:
        return None
    if record.error_kind is not None:
        # The harness classified the error; its class replaces the v1 text rules.
        if record.error_kind != "infra":
            return None
        return Finding("infra", 0.80, {
            "observed": "The harness classified this attempt's error as an infrastructure fault.",
            "rule": "error_kind", "quote": record.error})
    for name, pattern, confidence in INFRA_RULES:
        if name == "error_field":
            matched = bool(record.error and record.error.strip())
            quote = record.error
        elif record.output is None:
            continue  # The format does not carry the output, so output rules cannot apply.
        elif name == "empty_output":
            matched = not record.output.strip()
            quote = record.output
        else:
            matched = re.fullmatch(pattern, record.output.strip(), re.I | re.S) is not None
            quote = record.output
        if matched:
            return Finding("infra", confidence, {"rule": name, "quote": quote})
    return None


def _judge_disagreement(peers: Sequence[Record]) -> dict | None:
    """Summarize one identity group without enumerating judge pairs."""
    runs: dict[int, set[float]] = defaultdict(set)
    for peer in peers:
        if peer.judge_run is not None and peer.score is not None:
            runs[peer.judge_run].add(peer.score)
    # Conflicting scores within a judge run do not establish independent judging.
    if any(len(scores) != 1 for scores in runs.values()):
        return None
    values = sorted((run, next(iter(scores))) for run, scores in runs.items())
    frequencies = Counter(score for _, score in values)
    pairs = len(values) * (len(values) - 1) // 2
    flips = pairs - sum(count * (count - 1) // 2 for count in frequencies.values())
    if not flips:
        return None
    return {
        "judge_scores": [{"judge_run": run, "score": score} for run, score in values],
        "different_score_pairs": flips, "judge_pairs": pairs,
        "flip_rate": flips / pairs,
    }


def _judge_finding(record: Record, summary: dict | None) -> Finding | None:
    if record.score == 1 or record.judge_run is None or summary is None:
        return None
    return Finding("judge_unstable", 0.99, {"output_quote": record.output, **summary})


def judge_unstable(record: Record, peers: Sequence[Record]) -> Finding | None:
    key = record.judge_key
    return _judge_finding(record, _judge_disagreement([p for p in peers if p.judge_key == key]))


def _v1_shaped(record: Record) -> bool:
    return (record.agent is None and record.error_kind is None and record.task_version is None
            and record.job_id is None)


def item_everyone_loses(record: Record, peers: Sequence[Record]) -> Finding | None:
    group = [p for p in peers if p.item_key == record.item_key and p.role == "candidate"
             and p.score is not None and p.error_kind not in EXCLUDED_KINDS]
    models = sorted({p.system for p in group})
    if (record.score != 0 or record.error_kind in EXCLUDED_KINDS or len(models) < 2
            or any(p.score != 0 for p in group)):
        return None
    if any((p.instruction, p.rubric_item_text) !=
           (record.instruction, record.rubric_item_text) for p in group):
        return None
    if len({p.task_version for p in group}) > 1:
        return None
    evidence = {
        "rubric_quote": record.rubric_item_text,
        "models": models, "model_count": len(models), "observation_count": len(group),
        "run_count": len({(p.system, p.run_id) for p in group}),
        "zero_count": len(group),
        "scores_by_model": {m: [p.score for p in group if p.system == m] for m in models},
        "scope": "All supplied observations only; this does not prove a bad item.",
    }
    if all(_v1_shaped(p) for p in group):
        return Finding("item_everyone_loses", 0.90, evidence)
    # With agents, versions or harness errors in play, a small cohort says less.
    strength = 0.50 if len(models) == 2 else 0.70 if len(models) <= 4 else 0.90
    return Finding("item_everyone_loses", strength, {
        "observed": f"No supplied system scored above zero ({len(models)} systems).", **evidence})


class Reasoner(Protocol):
    """An LLM can implement this method later; callers inject it into triage()."""

    def missing_requirements(self, instruction: str, rubric: str) -> dict | None:
        """Return missing_terms and closest_instruction_sentence, or abstain."""
        ...


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


NUMBER = r"(?<![\w.+-])[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?%?(?!\w|\.\d)"


def _contains(text: str, term: str) -> bool:
    if re.fullmatch(NUMBER, term):
        return term.casefold() in {m.group().casefold() for m in re.finditer(NUMBER, text)}
    return re.search(r"(?<!\w)" + re.escape(_normalize(term)) + r"(?!\w)",
                     _normalize(text)) is not None


class HeuristicReasoner:
    """Literal requirement anchors only. No general semantic entailment or NER."""

    def missing_requirements(self, instruction: str, rubric: str) -> dict | None:
        # Ignore explanations/examples and rubric prose with no explicit requirement.
        if not re.match(r"^\s*(?:must\b|requires?\b|include\b|use\b|exactly\b)", rubric, re.I):
            return None
        if re.search(r"\b(?:not|never|without|avoid\w*|omit\w*|exclud\w*|optional|examples?|such as|for instance|either|or)\b|\be\.g\.", rubric, re.I):
            return None
        terms: list[str] = []
        quoted = r'"([^"\n]+)"|“([^”\n]+)”|(?<!\w)\x27([^\x27\n]+)\x27'
        for match in re.finditer(quoted, rubric):
            terms.append(next(g for g in match.groups() if g is not None))
        rest = re.sub(quoted, " ", rubric)
        terms.extend(m.group() for m in re.finditer(NUMBER, rest))
        # Small explicit unit vocabulary. Boundaries distinguish m from model, ms from mass.
        terms.extend(m.group() for m in re.finditer(
            r"(?<!\w)(?:kg|mg|km|cm|mm|ms|mL|kWh|Hz|MB|GB|°C|°F|seconds?|minutes?|hours?|kilograms?|meters?|liters?)(?!\w)", rest))
        # Conservative entity proxy: multiword Title Case names or all-caps tokens.
        # Discard the initial requirement verb before extracting names.
        rest = re.sub(r"^\s*(?:must|requires?|include|use|exactly)\b\s*", "", rest, flags=re.I)
        terms.extend(m.group() for m in re.finditer(
            r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|[A-Z]{2,}(?:-\d+)?)\b", rest))
        unique = list(dict.fromkeys(term for term in terms if term.strip()))
        missing = [term for term in unique if not _contains(instruction, term)]
        if not missing:
            return None
        sentences = re.split(r"(?<=[.!?])\s+|\n+", instruction.strip())
        rubric_words = set(re.findall(r"\w+", rubric.casefold()))
        closest = max(sentences, key=lambda s: len(set(re.findall(r"\w+", s.casefold())) & rubric_words))
        return {"missing_terms": missing, "closest_instruction_sentence": closest,
                "rubric_quote": rubric, "method": "literal anchors; absence is not proof of unfairness"}


def unstated_requirement(record: Record, reasoner: Reasoner) -> Finding | None:
    if record.score == 1 or record.instruction is None or record.rubric_item_text is None:
        return None
    evidence = reasoner.missing_requirements(record.instruction, record.rubric_item_text)
    return Finding("unstated_requirement", 0.65, evidence) if evidence else None


def _usable(record: Record) -> bool:
    """Whether a result counts in comparisons across attempts."""
    return record.score is not None and record.error_kind not in EXCLUDED_KINDS and infra(record) is None


@dataclass(frozen=True)
class Index:
    """Record groups, built once for a triage run."""

    items: dict       # item_key -> every candidate record
    attempts: dict    # item_key -> usable candidate records
    references: dict  # item_key -> usable reference records
    judges: dict      # judge_key -> disagreement summary or None


def build_index(records: Sequence[Record]) -> Index:
    items: dict[tuple, list[Record]] = defaultdict(list)
    attempts: dict[tuple, list[Record]] = defaultdict(list)
    references: dict[tuple, list[Record]] = defaultdict(list)
    by_judge: dict[tuple, list[Record]] = defaultdict(list)
    for record in records:
        if record.role != "candidate":
            if _usable(record):
                references[record.item_key].append(record)
            continue
        items[record.item_key].append(record)
        by_judge[record.judge_key].append(record)
        if _usable(record):
            attempts[record.item_key].append(record)
    return Index(items, attempts, references,
                 {key: _judge_disagreement(group) for key, group in by_judge.items()})


def _error_finding(record: Record, kind: str, label: str, strength: float, observed: str) -> Finding | None:
    if record.error_kind != kind or record.score == 1:
        return None
    return Finding(label, strength, {"observed": observed, "error": record.error})


def setup_error(record: Record) -> Finding | None:
    return _error_finding(record, "setup", "setup_error", 0.85,
                          "The harness recorded a setup or configuration error for this attempt.")


def grader_error(record: Record) -> Finding | None:
    return _error_finding(record, "grader", "grader_error", 0.85,
                          "The harness recorded that the verifier did not produce a result for this attempt.")


def unclassified_error(record: Record) -> Finding | None:
    if record.score is None and record.error_kind == "agent":
        # Never graded, so the default label (a graded loss no rule explains) would be false.
        return Finding("unclassified_error", 0.40, {
            "observed": "The harness recorded an agent-side error and no score, so the results do not say "
                        "whether this attempt would have passed.", "error": record.error})
    return _error_finding(record, "unknown", "unclassified_error", 0.40,
                          "The harness recorded an error that the format does not classify.")


def _references(record: Record, index: Index) -> list[Record]:
    """Usable reference results for this check, leaving out other task versions."""
    return [p for p in index.references.get(record.item_key, ())
            if None in (p.task_version, record.task_version) or p.task_version == record.task_version]


def reference_attempts(task_records: Sequence[Record], index: Index) -> tuple[int, int, int]:
    """Reference attempts of one task: passed, used and supplied.

    Used means the reference detectors read the attempt for at least one failed candidate
    result of the task, so this count and their findings cannot disagree.
    """
    failed = [r for r in task_records if r.role == "candidate" and r.score != 1]
    used: dict[tuple, bool] = {}
    for record in failed:
        for p in _references(record, index):   # an attempt passes when every result of it that was used passes
            used[p.attempt_key] = used.get(p.attempt_key, True) and p.score == 1
    supplied = {r.attempt_key for r in task_records if r.role != "candidate"}
    return sum(used.values()), len(used), len(supplied)


def _reference_runs(references: Sequence[Record]) -> list[dict]:
    return [{"system": p.system, "run_id": p.run_id, "score": p.score} for p in references]


def reference_flaky(record: Record, index: Index) -> Finding | None:
    references = _references(record, index)
    passes = sum(p.score == 1 for p in references)
    if record.score == 1 or not passes or passes == len(references):
        return None
    return Finding("reference_flaky", 0.85, {
        "observed": f"The reference solution passed {passes} of {len(references)} attempts.",
        "reference_runs": _reference_runs(references),
    })


def reference_fails(record: Record, index: Index) -> Finding | None:
    references = _references(record, index)
    if record.score == 1 or not references or any(p.score == 1 for p in references):
        return None
    versioned = record.task_version is not None and all(p.task_version is not None for p in references)
    strength = 0.90 if len(references) >= 2 else 0.75
    return Finding("reference_fails", strength if versioned else min(strength, 0.60), {
        "observed": f"The reference solution did not pass in {len(references)} of {len(references)} attempts.",
        "reference_runs": _reference_runs(references),
        "task_version": "same as this attempt" if versioned else "task version not available",
    })


def attempts_flip(record: Record, index: Index) -> Finding | None:
    if record.score == 1 or not _usable(record):
        return None
    runs: dict[str, bool] = {}
    for peer in index.attempts.get(record.item_key, ()):
        if peer.system == record.system:
            runs[peer.run_id] = runs.get(peer.run_id, False) or peer.score == 1
    passed = sorted(run for run, ok in runs.items() if ok and run != record.run_id)
    if not passed:
        return None
    return Finding("attempts_flip", 0.40, {
        "observed": f"This system passed {len(passed)} of {len(runs)} attempts.",
        "passes": len(passed), "attempts": len(runs), "passed_run_ids": passed,
        "other_run_ids": sorted(run for run in runs if run not in passed),
        "scope": "The results do not say whether the system, the task or the grader differs between attempts.",
    })


_RULES: dict[str, Callable[[Record, Index, Reasoner], Finding | None]] = {
    "infra": lambda record, index, reasoner: infra(record),
    "setup_error": lambda record, index, reasoner: setup_error(record),
    "grader_error": lambda record, index, reasoner: grader_error(record),
    "judge_unstable": lambda record, index, reasoner: _judge_finding(record, index.judges[record.judge_key]),
    "reference_flaky": lambda record, index, reasoner: reference_flaky(record, index),
    "reference_fails": lambda record, index, reasoner: reference_fails(record, index),
    "item_everyone_loses": lambda record, index, reasoner: item_everyone_loses(record, index.items[record.item_key]),
    "unstated_requirement": lambda record, index, reasoner: unstated_requirement(record, reasoner),
    "attempts_flip": lambda record, index, reasoner: attempts_flip(record, index),
    "unclassified_error": lambda record, index, reasoner: unclassified_error(record),
}
# One detector per label except the default, in LABELS order. A label without a rule fails at import.
DETECTORS = tuple((name, _RULES[name]) for name in CLASSES[:-1])


def triage(records: Sequence[Record], reasoner: Reasoner | None = None) -> list[dict]:
    """Every finding for each failed or ungraded candidate record; the first is the verdict."""
    reasoner = reasoner if reasoner is not None else HeuristicReasoner()
    index = build_index(records)
    verdicts = []
    for record in records:
        if record.role != "candidate" or record.score == 1:
            continue
        findings = [f for f in (rule(record, index, reasoner) for _, rule in DETECTORS) if f is not None]
        default = {
            "score": record.score, "rubric_quote": record.rubric_item_text,
            "output_quote": record.output, "judge_reasoning_quote": record.judge_reasoning,
            "note": "No precision-first detector fired. Default, not a proven model failure.",
        }
        if record.error:
            default["error"] = record.error
        selected = findings[0] if findings else Finding(CLASSES[-1], 0.50, default)
        verdicts.append({"record_id": record.record_id, "record": record_dict(record),
                         **asdict(selected), "matches": [asdict(f) for f in findings]})
    return verdicts
