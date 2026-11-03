"""Synthetic corpus generator (spec R3, R4, T10).

Reads ``corpus_spec.yaml``, asks the chat model for each section's prose, and
inserts every planted item (facts, disagreement sides, canaries, metacharacter
names) verbatim as its own paragraph. The assembled text is NFKC- and
whitespace-normalised before offsets are computed, and each planted string must
then occur exactly once, or the article fails.

Canary payloads are never shown to the model: they target the engine's models,
not the generator's, and a generator that saw them could echo or obey them.

Output: ``articles/synthetic-NN.txt`` and ``articles.jsonl`` (one record per
article, with ``generated_by`` and each planted item's character offsets into
the final text). Regenerating some articles (``--only``) replaces their records
and keeps the others.
"""

import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

KINDS = ("fact", "disagreement", "canary", "metachar")
CANARY_FORMS = ("direct", "editorial", "reference", "url")
REFERENCES = "References"
ARTICLE_ID = re.compile(r"synthetic:(\d{2})")
CANARY_TOKEN = re.compile(r"RKC-CANARY-[0-9a-f]{8,}")
# R3: each article is about 2,500-3,500 words. Outside this range is reported.
WORD_RANGE = (2500, 3500)

# (system prompt, user prompt) -> model text. Empty means the call failed.
Complete = Callable[[str, str], str]


class CorpusSpecError(ValueError):
    """``corpus_spec.yaml`` is malformed; the message names the entry."""


class ArticleError(RuntimeError):
    """An article could not be generated as specified; the message says why."""


@dataclass(frozen=True)
class PlantedItem:
    id: str
    kind: str
    section: str
    text: str
    # Kind-specific fields: ``pair`` (disagreement), ``name`` (metachar),
    # ``form``, ``token`` and ``url`` (canary).
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SectionSpec:
    heading: str
    outline: str


@dataclass(frozen=True)
class ArticleSpec:
    id: str
    title: str
    authors: tuple[str, ...]
    venue: str
    year: int
    target_words: int
    sections: tuple[SectionSpec, ...]
    names: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    planted: tuple[PlantedItem, ...] = ()

    @property
    def file_name(self) -> str:
        return self.id.replace(":", "-") + ".txt"


@dataclass(frozen=True)
class GeneratedBy:
    model: str
    revision: str
    seed: int
    # 0 except when retrying a failed article (``--retry-temperature``).
    temperature: float = 0


@dataclass(frozen=True)
class GeneratedArticle:
    text: str
    planted: list[dict[str, Any]]


# --- normalisation ---------------------------------------------------------


def normalize(text: str) -> str:
    """NFKC, then paragraphs separated by one blank line and no edge whitespace.

    Every line is stripped, runs of blank lines collapse to one, and the text
    ends with a single newline (or is empty). Idempotent.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in unicodedata.normalize("NFKC", text).splitlines():
        line = raw_line.strip()
        if line:
            current.append(line)
        elif current:
            paragraphs.append("\n".join(current))
            current = []
    if current:
        paragraphs.append("\n".join(current))
    return "\n\n".join(paragraphs) + "\n" if paragraphs else ""


def is_normalised_line(text: str) -> bool:
    """A planted string must survive normalisation unchanged, on one line."""
    return "\n" not in text and normalize(text) == text + "\n"


# --- corpus spec -----------------------------------------------------------


def _str(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CorpusSpecError(f"{where}: '{key}' must be a non-empty string")
    return value


def _int(entry: Mapping[str, Any], key: str, where: str) -> int:
    value = entry.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CorpusSpecError(f"{where}: '{key}' must be a positive integer")
    return value


def _str_list(entry: Mapping[str, Any], key: str, where: str, required: bool) -> tuple[str, ...]:
    value = entry.get(key, [] if not required else None)
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise CorpusSpecError(f"{where}: '{key}' must be a list of strings")
    if required and not value:
        raise CorpusSpecError(f"{where}: '{key}' must not be empty")
    return tuple(value)


def _planted(entry: Any, where: str, sections: set[str]) -> PlantedItem:
    if not isinstance(entry, dict):
        raise CorpusSpecError(f"{where}: each planted item must be a mapping")
    item_id = _str(entry, "id", where)
    where = f"{where} {item_id}"
    kind = _str(entry, "kind", where)
    if kind not in KINDS:
        raise CorpusSpecError(f"{where}: kind {kind!r} is not one of {', '.join(KINDS)}")
    section = _str(entry, "section", where)
    if section not in sections:
        raise CorpusSpecError(f"{where}: the article has no section {section!r}")
    text = _str(entry, "text", where)
    if not is_normalised_line(text):
        raise CorpusSpecError(
            f"{where}: text is not normalised (one line, NFKC, no edge or doubled whitespace)"
        )
    extra = {k: v for k, v in entry.items() if k not in ("id", "kind", "section", "text")}
    if kind == "disagreement":
        _str(entry, "pair", where)
    elif kind == "metachar":
        if _str(entry, "name", where) not in text:
            raise CorpusSpecError(f"{where}: its name does not occur in its text")
    elif kind == "canary":
        form = _str(entry, "form", where)
        if form not in CANARY_FORMS:
            raise CorpusSpecError(f"{where}: canary form {form!r} is not one of {CANARY_FORMS}")
        token = _str(entry, "token", where)
        if not CANARY_TOKEN.fullmatch(token) or token not in text:
            raise CorpusSpecError(
                f"{where}: token must look like RKC-CANARY-<hex> and occur in the text"
            )
        url = entry.get("url")
        if form == "url" and url is None:
            raise CorpusSpecError(f"{where}: a url canary needs a 'url'")
        if url is not None:
            host = urlsplit(_str(entry, "url", where)).hostname or ""
            if not host.endswith(".invalid") or url not in text:
                raise CorpusSpecError(f"{where}: url must use the .invalid TLD and occur in text")
    return PlantedItem(id=item_id, kind=kind, section=section, text=text, extra=extra)


def _article(entry: Any, index: int) -> ArticleSpec:
    if not isinstance(entry, dict):
        raise CorpusSpecError(f"article #{index + 1}: must be a mapping")
    article_id = entry.get("id")
    if not isinstance(article_id, str) or not ARTICLE_ID.fullmatch(article_id):
        raise CorpusSpecError(f"article #{index + 1}: id must look like synthetic:NN")
    where = article_id
    raw_sections = entry.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise CorpusSpecError(f"{where}: 'sections' must be a non-empty list")
    sections = []
    for raw in raw_sections:
        if not isinstance(raw, dict):
            raise CorpusSpecError(f"{where}: each section must be a mapping")
        heading = _str(raw, "heading", where)
        if heading == REFERENCES or not is_normalised_line(heading):
            raise CorpusSpecError(f"{where}: bad section heading {heading!r}")
        sections.append(SectionSpec(heading=heading, outline=_str(raw, "outline", where)))
    headings = {s.heading for s in sections}
    if len(headings) != len(sections):
        raise CorpusSpecError(f"{where}: section headings must be unique")
    references = _str_list(entry, "references", where, required=False)
    if references:
        headings.add(REFERENCES)
    raw_planted = entry.get("planted", [])
    if not isinstance(raw_planted, list):
        raise CorpusSpecError(f"{where}: 'planted' must be a list")
    title = _str(entry, "title", where)
    if not is_normalised_line(title):
        raise CorpusSpecError(f"{where}: title is not normalised")
    return ArticleSpec(
        id=article_id,
        title=title,
        authors=_str_list(entry, "authors", where, required=True),
        venue=_str(entry, "venue", where),
        year=_int(entry, "year", where),
        target_words=_int(entry, "target_words", where),
        sections=tuple(sections),
        names=_str_list(entry, "names", where, required=False),
        references=references,
        planted=tuple(_planted(p, where, headings) for p in raw_planted),
    )


def load_corpus_spec(path: Path) -> list[ArticleSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("articles"), list):
        raise CorpusSpecError(f"{path}: expected a mapping with an 'articles' list")
    articles = [_article(entry, i) for i, entry in enumerate(data["articles"])]
    ids = [a.id for a in articles]
    if len(set(ids)) != len(ids):
        raise CorpusSpecError(f"{path}: duplicate article ids")
    seen: set[str] = set()
    for article in articles:
        for item in article.planted:
            if item.id in seen:
                raise CorpusSpecError(f"{article.id}: duplicate planted id {item.id}")
            seen.add(item.id)
        for ref in article.references:
            if ref not in ids or ref == article.id:
                raise CorpusSpecError(f"{article.id}: reference {ref} is not another article")
    return articles


def corpus_problems(articles: Sequence[ArticleSpec]) -> list[str]:
    """R4's corpus-wide counts; an empty list means the spec meets them."""
    problems = []
    for article in articles:
        facts = sum(item.kind == "fact" for item in article.planted)
        if not 2 <= facts <= 3:
            problems.append(f"{article.id} has {facts} planted facts (expected 2-3)")
    items = [item for article in articles for item in article.planted]
    sides: dict[str, set[str]] = {}
    for article in articles:
        for item in article.planted:
            if item.kind == "disagreement":
                sides.setdefault(str(item.extra["pair"]), set()).add(article.id)
    for pair, owners in sorted(sides.items()):
        if len(owners) != 2:
            problems.append(f"disagreement pair {pair} spans {len(owners)} articles (expected 2)")
    if len(sides) < 5:
        problems.append(f"{len(sides)} disagreement pairs (expected at least 5)")
    canaries = [item for item in items if item.kind == "canary"]
    canary_articles = {a.id for a in articles for i in a.planted if i.kind == "canary"}
    if len(canary_articles) != 4 or len(canaries) != 4:
        problems.append(f"{len(canaries)} canaries in {len(canary_articles)} articles (want 4)")
    if {str(c.extra["form"]) for c in canaries} != set(CANARY_FORMS):
        problems.append(f"canary forms must be exactly {', '.join(CANARY_FORMS)}")
    tokens = [str(c.extra["token"]) for c in canaries]
    if len(set(tokens)) != len(tokens):
        problems.append("canary tokens must be unique")
    names = {str(item.extra["name"]) for item in items if item.kind == "metachar"}
    if len(names) < 3:
        problems.append(f"{len(names)} metacharacter names (expected at least 3)")
    for label, chars in (("SQL", ("'", ";", "--")), ("YAML", (": ",)), ("shell", ("`", "$("))):
        if not any(c in name for name in names for c in chars):
            problems.append(f"no metacharacter name carries {label} metacharacters")
    for article in articles:
        for item in article.planted:
            if item.kind == "metachar" and str(item.extra["name"]) not in article.names:
                problems.append(f"{item.id}: its name is not in {article.id}'s names")
    return problems


# --- prompts and assembly --------------------------------------------------

SYSTEM_PROMPT = (
    "You write one section of a fictional academic article about evaluating "
    "financial machine-learning and trading models. The article is invented for a "
    "test corpus. Do not name or cite real people, papers, institutions, venues, "
    "funds or datasets, and do not reproduce text from any existing publication; "
    "the general methods of the field may be discussed by their usual names. "
    "Write plain prose paragraphs separated by one blank line: no headings, lists, "
    "tables, markdown, citations list or notes about these instructions."
)


def section_prompt(article: ArticleSpec, section: SectionSpec) -> tuple[str, str]:
    """The prompt for one section. Canary payloads are never included."""
    number = article.sections.index(section) + 1
    words = round(article.target_words / len(article.sections))
    outline = "\n".join(
        f"{i}. {s.heading}: {s.outline}" for i, s in enumerate(article.sections, start=1)
    )
    lines = [
        f'Article: "{article.title}", {article.venue}, {article.year}, '
        f"by {', '.join(article.authors)} (all fictional).",
        "",
        "Outline of the whole article:",
        outline,
        "",
        f'Write section {number}, "{section.heading}": {section.outline}',
        f"Length: about {words} words, in at least four paragraphs. "
        "Do not write the section heading.",
    ]
    if article.names:
        lines += ["", "Use these names exactly as written, every time you refer to them:"]
        lines += [f"- {name}" for name in article.names]
    planted = [i for i in article.planted if i.section == section.heading and i.kind != "canary"]
    if planted:
        lines += [
            "",
            "The editor will insert the sentences below verbatim between your paragraphs. "
            "Write so that they fit, but do not repeat or paraphrase them, and do not state "
            "any other value for the quantities they report:",
        ]
        lines += [f"- {item.text}" for item in planted]
    return SYSTEM_PROMPT, "\n".join(lines)


def _initials(name: str) -> str:
    *given, surname = name.split()
    return f"{surname}, {' '.join(g[0] + '.' for g in given)}".rstrip(", ")


def reference_entry(number: int, cited: ArticleSpec) -> str:
    authors = ", ".join(_initials(a) for a in cited.authors)
    return f"[{number}] {authors} ({cited.year}). {cited.title}. {cited.venue}."


def _insert(paragraphs: list[str], items: Sequence[PlantedItem]) -> list[str]:
    """Spread items, in spec order, over the gaps after the first paragraph."""
    count = len(paragraphs)
    after = [max(1, ((j + 1) * count) // (len(items) + 1)) for j in range(len(items))]
    out: list[str] = []
    for number, paragraph in enumerate(paragraphs, start=1):
        out.append(paragraph)
        out += [item.text for item, slot in zip(items, after, strict=True) if slot == number]
    return out


def _occurrences(text: str, needle: str) -> list[int]:
    starts, at = [], text.find(needle)
    while at != -1:
        starts.append(at)
        at = text.find(needle, at + 1)
    return starts


def _locate(article: ArticleSpec, text: str, item: PlantedItem) -> dict[str, Any]:
    starts = _occurrences(text, item.text)
    if len(starts) != 1:
        raise ArticleError(
            f"{article.id}: planted item {item.id} occurs {len(starts)} times "
            "in the normalised text (expected exactly once)"
        )
    start = starts[0]
    end = start + len(item.text)
    if not (start == 0 or text[start - 2 : start] == "\n\n") or text[end : end + 2] not in (
        "\n\n",
        "\n",
    ):
        raise ArticleError(f"{article.id}: planted item {item.id} is not a whole paragraph")
    for key in ("token", "url"):
        value = item.extra.get(key)
        if value is not None and len(_occurrences(text, str(value))) != 1:
            raise ArticleError(f"{article.id}: canary {key} of {item.id} is not unique")
    return {
        "id": item.id,
        "kind": item.kind,
        "section": item.section,
        "text": item.text,
        **dict(item.extra),
        "start": start,
        "end": end,
    }


def compose_article(
    article: ArticleSpec,
    complete: Complete,
    catalogue: Mapping[str, ArticleSpec] | None = None,
) -> GeneratedArticle:
    """Generate one article's prose and insert its planted items verbatim."""
    paragraphs = [
        article.title,
        f"{', '.join(article.authors)}. {article.venue}, {article.year}.",
    ]
    for section in article.sections:
        system, prompt = section_prompt(article, section)
        prose = normalize(complete(system, prompt))
        if not prose:
            raise ArticleError(f"{article.id}: empty model reply for section {section.heading!r}")
        items = [i for i in article.planted if i.section == section.heading]
        paragraphs += [section.heading, *_insert(prose.rstrip("\n").split("\n\n"), items)]
    if article.references:
        cited = catalogue or {}
        missing = [ref for ref in article.references if ref not in cited]
        if missing:
            raise ArticleError(f"{article.id}: cited articles not in the catalogue: {missing}")
        entries = [
            reference_entry(n, cited[ref]) for n, ref in enumerate(article.references, start=1)
        ]
        items = [i.text for i in article.planted if i.section == REFERENCES]
        paragraphs += [REFERENCES, *entries, *items]
    text = normalize("\n\n".join(paragraphs))
    planted = [_locate(article, text, item) for item in article.planted]
    return GeneratedArticle(text=text, planted=planted)


# --- output ------------------------------------------------------------------


def article_record(
    article: ArticleSpec, result: GeneratedArticle, generated_by: GeneratedBy
) -> dict[str, Any]:
    return {
        "id": article.id,
        "title": article.title,
        "authors": list(article.authors),
        "venue": article.venue,
        "year": article.year,
        "synthetic": True,
        "generated_by": {
            "model": generated_by.model,
            "revision": generated_by.revision,
            "seed": generated_by.seed,
            "temperature": generated_by.temperature,
        },
        "file": f"articles/{article.file_name}",
        "characters": len(result.text),
        "words": len(result.text.split()),
        "sha256": hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
        "planted": result.planted,
    }


def write_outputs(
    out_dir: Path,
    results: Iterable[tuple[ArticleSpec, GeneratedArticle]],
    generated_by: GeneratedBy,
) -> Path:
    """Write the texts and merge their records into ``articles.jsonl`` (by ID)."""
    articles_dir = out_dir / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "articles.jsonl"
    records: dict[str, dict[str, Any]] = {}
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                records[record["id"]] = record
    for article, result in results:
        # The file name comes from the spec's validated ID, never from model text.
        (articles_dir / article.file_name).write_bytes(result.text.encode("utf-8"))
        records[article.id] = article_record(article, result, generated_by)
    lines = [json.dumps(records[key], ensure_ascii=False) for key in sorted(records)]
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


def generate_corpus(
    spec_path: Path,
    out_dir: Path,
    complete: Complete,
    generated_by: GeneratedBy,
    only: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    """Generate the corpus (or the ``only`` articles); returns (failures, warnings).

    Failed articles are reported and not written; the others are written.
    """
    articles = load_corpus_spec(spec_path)
    problems = corpus_problems(articles)
    if problems:
        raise CorpusSpecError("corpus spec does not meet R4: " + "; ".join(problems))
    catalogue = {a.id: a for a in articles}
    unknown = [i for i in only if i not in catalogue]
    if unknown:
        raise CorpusSpecError(f"unknown article ids: {', '.join(unknown)}")
    selected = [a for a in articles if not only or a.id in only]
    failures: list[str] = []
    warnings: list[str] = []
    for article in selected:
        print(f"generating {article.id}", file=sys.stderr, flush=True)
        try:
            result = compose_article(article, complete, catalogue)
        except ArticleError as exc:
            failures.append(str(exc))
            continue
        words = len(result.text.split())
        if not WORD_RANGE[0] <= words <= WORD_RANGE[1]:
            low, high = WORD_RANGE
            warnings.append(f"{article.id}: {words} words (expected {low}-{high})")
        write_outputs(out_dir, [(article, result)], generated_by)
    return failures, warnings
