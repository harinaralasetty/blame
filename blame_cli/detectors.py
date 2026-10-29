"""Pure, precision-first detectors. None perform I/O or call an LLM."""

from collections import defaultdict
from dataclasses import asdict
from itertools import combinations
import re
from typing import Protocol, Sequence

from .model import Finding, Record


# The single source of truth for infrastructure rules, including non-regex rules.
# Regex rules require the whole stripped output to look like an error message.
INFRA_RULES = (
    ("error_field", None, 0.99),
    ("empty_output", None, 0.98),
    ("timeout", r"(?:error:\s*)?(?:(?:request|connection|operation)\s+)?(?:timed?\s*out|timeout(?:error)?)(?:[.: ].*)?", 0.95),
    ("rate_limit", r"(?:error:\s*)?(?:rate[ -]limit(?:ed| exceeded)?|too many requests|(?:http(?: error)?\s*:?\s*)?429)(?:[.: ].*)?", 0.96),
    ("server_error", r"(?:error:\s*)?(?:(?:http(?: error)?|status(?: code)?)\s*[:=]?\s*5\d\d\b.*|5\d\d(?:\s+(?:internal server error|bad gateway|service unavailable|gateway timeout).*)?|bad gateway[.!]?|gateway timeout[.!]?|internal server error[.!]?|service unavailable[.!]?)", 0.96),
    ("missing_artifact", r"(?:error:\s*)?(?:missing (?:required )?artifact|(?:required )?artifact (?:is )?(?:missing|not found))(?:[.: ].*)?", 0.94),
)


def infra(record: Record) -> Finding | None:
    if record.score == 1:
        return None
    for name, pattern, confidence in INFRA_RULES:
        if name == "error_field":
            matched = bool(record.error and record.error.strip())
            quote = record.error
        elif name == "empty_output":
            matched = not record.output.strip()
            quote = record.output
        else:
            matched = re.fullmatch(pattern, record.output.strip(), re.I | re.S) is not None
            quote = record.output
        if matched:
            return Finding("infra", confidence, {"rule": name, "quote": quote})
    return None


def judge_unstable(record: Record, peers: Sequence[Record]) -> Finding | None:
    if record.score == 1 or record.judge_run is None:
        return None
    runs: dict[int, set[float]] = defaultdict(set)
    for peer in peers:
        if peer.judge_key == record.judge_key and peer.judge_run is not None:
            runs[peer.judge_run].add(peer.score)
    # Conflicting scores within a judge run do not establish independent judging.
    if any(len(scores) != 1 for scores in runs.values()):
        return None
    values = sorted((run, next(iter(scores))) for run, scores in runs.items())
    pairs = list(combinations(values, 2))
    flips = sum(left[1] != right[1] for left, right in pairs)
    if not flips:
        return None
    return Finding("judge_unstable", 0.99, {
        "output_quote": record.output,
        "judge_scores": [{"judge_run": run, "score": score} for run, score in values],
        "different_score_pairs": flips, "judge_pairs": len(pairs),
        "flip_rate": flips / len(pairs),
    })


def item_everyone_loses(record: Record, peers: Sequence[Record]) -> Finding | None:
    group = [p for p in peers if p.item_key == record.item_key]
    models = sorted({p.model for p in group})
    if record.score != 0 or len(models) < 2 or any(p.score != 0 for p in group):
        return None
    if any((p.instruction, p.rubric_item_text) !=
           (record.instruction, record.rubric_item_text) for p in group):
        return None
    return Finding("item_everyone_loses", 0.90, {
        "rubric_quote": record.rubric_item_text,
        "models": models, "model_count": len(models), "observation_count": len(group),
        "run_count": len({(p.model, p.run_id) for p in group}),
        "zero_count": len(group),
        "scores_by_model": {m: [p.score for p in group if p.model == m] for m in models},
        "scope": "All supplied observations only; this does not prove a bad item.",
    })


class Reasoner(Protocol):
    """An LLM can implement this method later; callers inject it into triage()."""

    def missing_requirements(self, instruction: str, rubric: str) -> dict | None:
        """Return missing_terms and closest_instruction_sentence, or abstain."""
        ...


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _contains(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normalize(term)) + r"(?!\w)",
                     _normalize(text)) is not None


class HeuristicReasoner:
    """Literal requirement anchors only. No general semantic entailment or NER."""

    def missing_requirements(self, instruction: str, rubric: str) -> dict | None:
        # Ignore explanations/examples and rubric prose with no explicit requirement.
        if not re.match(r"^\s*(?:must\b|requires?\b|include\b|use\b|exactly\b)", rubric, re.I):
            return None
        if re.search(r"\b(?:not|never|without|optional|example|such as|either|or)\b|\be\.g\.", rubric, re.I):
            return None
        terms: list[str] = []
        quoted = r'"([^"\n]+)"|“([^”\n]+)”|(?<!\w)\x27([^\x27\n]+)\x27'
        for match in re.finditer(quoted, rubric):
            terms.append(next(g for g in match.groups() if g is not None))
        rest = re.sub(quoted, " ", rubric)
        terms.extend(m.group() for m in re.finditer(r"(?<![\w.])[+-]?\d+(?:\.\d+)?(?:%|\b)", rest))
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
    if record.score == 1:
        return None
    evidence = reasoner.missing_requirements(record.instruction, record.rubric_item_text)
    return Finding("unstated_requirement", 0.65, evidence) if evidence else None


def triage(records: Sequence[Record], reasoner: Reasoner | None = None) -> list[dict]:
    reasoner = reasoner if reasoner is not None else HeuristicReasoner()
    by_item: dict[tuple, list[Record]] = defaultdict(list)
    by_judge: dict[tuple, list[Record]] = defaultdict(list)
    for record in records:
        by_item[record.item_key].append(record)
        by_judge[record.judge_key].append(record)
    verdicts = []
    for record in records:
        if record.score == 1:
            continue
        findings = [f for f in (
            infra(record), judge_unstable(record, by_judge[record.judge_key]),
            item_everyone_loses(record, by_item[record.item_key]),
            unstated_requirement(record, reasoner),
        ) if f is not None]
        selected = findings[0] if findings else Finding("genuine_failure", 0.50, {
            "score": record.score, "rubric_quote": record.rubric_item_text,
            "output_quote": record.output, "judge_reasoning_quote": record.judge_reasoning,
            "note": "No precision-first detector fired. Default, not a proven model failure.",
        })
        verdicts.append({"record_id": record.record_id, "record": asdict(record),
                         **asdict(selected), "matches": [asdict(f) for f in findings]})
    return verdicts
