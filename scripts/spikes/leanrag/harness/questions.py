"""``questions.yaml``: the synthetic benchmark's questions (spec R5).

Each question has an ID, a kind, its text, the planted item IDs a correct
retrieval should reach (``expected``) and the strings a correct answer contains
(``expect_strings``). The owner sets ``status: approved`` with the date before
the first baseline build.
"""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from harness.generate import ArticleSpec

QUESTION_KINDS = ("fact", "disagreement", "multi-hop", "seed", "negative")
STATUSES = ("draft", "approved")
COUNT_RANGE = (15, 20)


class QuestionsError(ValueError):
    """``questions.yaml`` is malformed; the message names the entry."""


@dataclass(frozen=True)
class Question:
    id: str
    kind: str
    text: str
    expected: tuple[str, ...]
    expect_strings: tuple[str, ...]


@dataclass(frozen=True)
class QuestionsDocument:
    status: str
    approved: str | None
    questions: tuple[Question, ...]


def _strings(entry: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = entry.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise QuestionsError(f"{where}: '{key}' must be a list of strings")
    return tuple(value)


def _question(entry: Any, index: int) -> Question:
    where = f"question #{index + 1}"
    if not isinstance(entry, dict):
        raise QuestionsError(f"{where}: must be a mapping")
    for key in ("id", "kind", "text"):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise QuestionsError(f"{where}: '{key}' must be a non-empty string")
    if entry["kind"] not in QUESTION_KINDS:
        raise QuestionsError(f"{where}: kind {entry['kind']!r} is not one of {QUESTION_KINDS}")
    return Question(
        id=entry["id"],
        kind=entry["kind"],
        text=entry["text"],
        expected=_strings(entry, "expected", where),
        expect_strings=_strings(entry, "expect_strings", where),
    )


def load_questions(path: Path) -> QuestionsDocument:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise QuestionsError(f"{path}: expected a mapping with a 'questions' list")
    status = data.get("status")
    if status not in STATUSES:
        raise QuestionsError(f"{path}: status must be one of {STATUSES}")
    approved = data.get("approved")
    if isinstance(approved, datetime.date):
        approved = approved.isoformat()
    if status == "approved" and not isinstance(approved, str):
        raise QuestionsError(f"{path}: an approved question set needs its approval date")
    questions = tuple(_question(entry, i) for i, entry in enumerate(data["questions"]))
    return QuestionsDocument(status=status, approved=approved, questions=questions)


def question_problems(
    document: QuestionsDocument,
    articles: Sequence[ArticleSpec],
    seed_texts: Sequence[str],
) -> list[str]:
    """R5's checks against the corpus spec; an empty list means they hold."""
    problems = []
    questions = document.questions
    low, high = COUNT_RANGE
    if not low <= len(questions) <= high:
        problems.append(f"{len(questions)} questions (expected {low}-{high} questions)")
    seen: set[str] = set()
    for question in questions:
        if question.id in seen:
            problems.append(f"duplicate question id {question.id}")
        seen.add(question.id)
    items = {item.id: item for a in articles for item in a.planted}
    for question in questions:
        problems += [
            f"{question.id}: unknown planted id {item_id}"
            for item_id in question.expected
            if item_id not in items
        ]
        if question.kind == "negative":
            if question.expected or question.expect_strings:
                problems.append(f"negative question {question.id} expects planted items")
        elif not question.expected or not question.expect_strings:
            problems.append(f"{question.id} needs expected items and expect_strings")
        else:
            texts = " ".join(items[i].text for i in question.expected if i in items)
            problems += [
                f"{question.id}: expect_string {s!r} is in none of its expected items"
                for s in question.expect_strings
                if s not in texts
            ]
    seeds = [q.text for q in questions if q.kind == "seed"]
    if sorted(seeds) != sorted(seed_texts):
        problems.append("the seed questions must be exactly the docs/topics.md questions")
    negatives = sum(q.kind == "negative" for q in questions)
    if negatives < 2:
        problems.append(f"{negatives} negative questions (expected at least 2)")
    pairs: dict[str, set[str]] = {}
    for item in items.values():
        if item.kind == "disagreement":
            pairs.setdefault(str(item.extra["pair"]), set()).add(item.id)
    for pair, sides in sorted(pairs.items()):
        if not any(sides <= set(q.expected) for q in questions):
            problems.append(f"disagreement pair {pair} is not asked with both sides expected")
    return problems
