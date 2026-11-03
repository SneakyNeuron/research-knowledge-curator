"""The committed corpus spec and questions meet R4 and R5."""

import re
from pathlib import Path

import pytest
from harness.generate import corpus_problems, load_corpus_spec, section_prompt
from harness.paths import CORPUS_SPEC, QUESTIONS, REPO_DIR
from harness.questions import QuestionsError, load_questions, question_problems

ARTICLES = load_corpus_spec(CORPUS_SPEC)


def topic_questions() -> list[str]:
    """The numbered questions under docs/topics.md's fin-model-evaluation heading."""
    text = (REPO_DIR / "docs" / "topics.md").read_text(encoding="utf-8")
    section = text.split("(cluster: `fin-model-evaluation`)", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\d+\. (.+)$", section, flags=re.MULTILINE)


def test_corpus_spec_meets_r4() -> None:
    assert len(ARTICLES) == 40
    assert [a.id for a in ARTICLES] == [f"synthetic:{n:02d}" for n in range(1, 41)]
    assert corpus_problems(ARTICLES) == []
    assert all(a.target_words == 3000 for a in ARTICLES)


def test_planted_texts_are_unique_across_the_corpus() -> None:
    texts = [item.text for a in ARTICLES for item in a.planted]
    assert len(set(texts)) == len(texts)
    for text in texts:
        others = [t for t in texts if t != text]
        assert not any(text in other for other in others)


def test_no_prompt_for_the_committed_spec_leaks_a_canary() -> None:
    for article in ARTICLES:
        for section in article.sections:
            system, prompt = section_prompt(article, section)
            assert "RKC-CANARY" not in system + prompt
            assert ".invalid" not in system + prompt


def test_committed_questions_meet_r5() -> None:
    document = load_questions(QUESTIONS)

    assert question_problems(document, ARTICLES, topic_questions()) == []
    assert document.status == "draft"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "questions.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_question_problems_are_reported(tmp_path: Path) -> None:
    document = load_questions(
        write(
            tmp_path,
            """
status: draft
approved: null
questions:
  - {id: q01, kind: fact, text: "What?", expected: [s99-f1], expect_strings: ["x"]}
  - {id: q01, kind: negative, text: "Who?", expected: [s01-f1], expect_strings: []}
""",
        )
    )

    problems = question_problems(document, ARTICLES, topic_questions())

    joined = "\n".join(problems)
    assert "15-20 questions" in joined
    assert "duplicate question id q01" in joined
    assert "unknown planted id s99-f1" in joined
    assert "negative question q01 expects planted items" in joined
    assert "seed" in joined
    assert "disagreement pair D1" in joined


@pytest.mark.parametrize(
    "text",
    [
        "questions: []",
        "status: done\nquestions: []",
        "status: draft\nquestions:\n  - {id: q1, kind: rumour, text: x}",
        "status: approved\napproved: null\nquestions: []",
    ],
)
def test_malformed_questions_are_rejected(tmp_path: Path, text: str) -> None:
    with pytest.raises(QuestionsError):
        load_questions(write(tmp_path, text))
