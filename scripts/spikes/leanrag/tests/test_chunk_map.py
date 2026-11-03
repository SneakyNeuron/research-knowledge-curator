"""Chunk export and offset map (spec R6): upstream's chunker, mapped back to article spans.

Most tests use small windows so that boundaries land where the test needs them;
the mapping is the same code at upstream's 1024/128.

In ``cl100k_base``, ``é``, ``—`` and ``β`` are single tokens in every context, so a
window boundary never splits them. Flagged windows therefore use characters that
the encoding splits into byte tokens: ``ŝ`` (2 bytes, 2 tokens) and ``ꞵ`` (LATIN
SMALL LETTER BETA, 3 bytes, 3 tokens).
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import tiktoken
from harness.chunk import (
    ChunkMapError,
    chunk_articles,
    load_articles,
    map_chunks,
    upstream_chunks,
    write_outputs,
)

ENC = tiktoken.get_encoding("cl100k_base")
FFFD = "�"

ASCII = (
    "Calibration error measures how far stated confidence drifts from accuracy.\n\n"
    "  Benchmarks for financial question answering report it per model and per task.\n"
    "A model can be accurate yet badly calibrated, which matters for risk decisions.\n"
)


def post(text: str) -> str:
    """Upstream's post-processing of a decoded window."""
    return text.strip().replace("\n", "")


def assert_exact_spans(articles: list[tuple[str, str]], max_size: int, overlap: int) -> None:
    """Unflagged spans: the post-processed span is the chunk text, and md5 the hash."""
    chunks, chunk_map = chunk_articles(
        articles, max_token_size=max_size, overlap_token_size=overlap
    )
    texts = dict(articles)
    assert len(chunk_map.spans) == len(chunks)
    for span in chunk_map.spans:
        chunk = chunks[span.chunk_index]
        assert span.hash_code == chunk["hash_code"]
        piece = texts[span.article_id][span.char_start : span.char_end]
        if not span.split_char:
            assert post(piece) == chunk["text"]
            assert hashlib.md5(piece.encode()).hexdigest() == chunk["hash_code"]  # noqa: S324


def test_ascii_windows_map_to_exact_spans_with_token_and_char_offsets() -> None:
    max_size, overlap = 8, 2
    chunks, chunk_map = chunk_articles(
        [("synthetic:01", ASCII)], max_token_size=max_size, overlap_token_size=overlap
    )
    tokens = ENC.encode(ASCII)
    starts = list(range(0, len(tokens), max_size - overlap))
    assert [s.window for s in chunk_map.spans] == list(range(len(starts)))
    assert [s.chunk_index for s in chunk_map.spans] == list(range(len(chunks)))
    for span, start in zip(chunk_map.spans, starts, strict=True):
        end = min(start + max_size, len(tokens))
        assert (span.token_start, span.token_end) == (start, end)
        assert span.char_start == len(ENC.decode(tokens[:start]))
        assert span.char_end == len(ENC.decode(tokens[:end]))
        assert not span.split_char
        assert post(ASCII[span.char_start : span.char_end]) == chunks[span.chunk_index]["text"]
    assert chunk_map.flagged == 0
    assert chunk_map.spans[-1].char_end == len(ASCII)


def test_overlapping_windows_share_the_overlap_tokens_and_characters() -> None:
    _, chunk_map = chunk_articles(
        [("synthetic:01", ASCII)], max_token_size=10, overlap_token_size=4
    )
    for prev, cur in zip(chunk_map.spans, chunk_map.spans[1:], strict=False):
        assert cur.token_start == prev.token_start + 6
        if prev.token_end - prev.token_start == 10:
            assert prev.token_end - cur.token_start == 4
            assert cur.char_start < prev.char_end


def test_final_short_window_and_upstream_parameters_on_a_long_article() -> None:
    text = " ".join(f"metric{i} drifts." for i in range(1200))
    tokens = ENC.encode(text)
    assert len(tokens) > 2 * 1024
    chunks, chunk_map = chunk_articles([("synthetic:01", text)])  # 1024/128 by default
    starts = list(range(0, len(tokens), 1024 - 128))
    assert len(chunks) == len(chunk_map.spans) == len(starts)
    last = chunk_map.spans[-1]
    assert last.token_start == starts[-1]
    assert last.token_end == len(tokens)
    assert last.token_end - last.token_start < 1024
    assert last.char_end == len(text)
    assert_exact_spans([("synthetic:01", text)], 1024, 128)


def test_article_shorter_than_one_window_is_one_span_over_the_whole_text() -> None:
    text = "\n  A short note on calibration.\nIt has two lines.  \n"
    chunks, chunk_map = chunk_articles([("synthetic:01", text)])
    assert len(chunks) == 1
    (span,) = chunk_map.spans
    assert (span.char_start, span.char_end) == (0, len(text))
    assert (span.token_start, span.token_end) == (0, len(ENC.encode(text)))
    assert chunks[0]["text"] == "A short note on calibration.It has two lines."
    assert chunks[0]["hash_code"] == hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def test_multibyte_characters_at_and_across_boundaries_are_never_split() -> None:
    text = "Café returns — β of 1.2 — résumé of βeta, café—β.\nNaïve é—β again. " * 3
    for max_size in range(2, 9):
        for overlap in (0, 1):
            assert_exact_spans([("synthetic:01", text)], max_size, overlap)
            _, chunk_map = chunk_articles(
                [("synthetic:01", text)], max_token_size=max_size, overlap_token_size=overlap
            )
            assert chunk_map.flagged == 0
    # Boundaries land right before and right after each character (at), and with
    # an overlap every character sits in two windows somewhere (across).
    _, chunk_map = chunk_articles([("synthetic:01", text)], max_token_size=3, overlap_token_size=1)
    edges = {s.char_start for s in chunk_map.spans} | {s.char_end for s in chunk_map.spans}
    for char in "é—β":
        positions = [i for i, c in enumerate(text) if c == char]
        assert any(p in edges for p in positions), char
        assert any(p + 1 in edges for p in positions), char
        assert any(
            sum(s.char_start <= p < s.char_end for s in chunk_map.spans) >= 2 for p in positions
        ), char


def split_windows(text: str, char: str) -> tuple[int, list[bytes]]:
    """The window size that puts a token boundary inside the first ``char``."""
    tokens = ENC.encode(text)
    pieces = [ENC.decode_single_token_bytes(t) for t in tokens]
    start = len(text[: text.index(char)].encode())
    end = start + len(char.encode())
    offset = 0
    for count, piece in enumerate(pieces, start=1):
        offset += len(piece)
        if start < offset < end:
            return count, pieces
    raise AssertionError(f"{char!r} is not split into several tokens")


@pytest.mark.parametrize("char", ["ŝ", "ꞵ"])
def test_window_splitting_a_character_is_widened_and_flagged(char: str) -> None:
    text = f"Coefficient {char}  is reported.\n\n The {char} again and done."
    max_size, pieces = split_windows(text, char)
    chunks, chunk_map = chunk_articles(
        [("synthetic:01", text)], max_token_size=max_size, overlap_token_size=0
    )
    first, second = chunk_map.spans[0], chunk_map.spans[1]
    position = text.index(char)

    # The first window ends inside the character: widened to include it whole.
    assert first.split_char
    assert first.char_end == position + 1
    assert text[first.char_end - 1] == char
    assert chunks[0]["text"].endswith(FFFD)
    # The second window starts inside it: widened back to its start.
    assert second.split_char
    assert second.char_start == position
    assert chunks[1]["text"].startswith(FFFD)
    assert chunk_map.flagged >= 2
    # md5 of the decoded window is the hash, U+FFFD included.
    window = b"".join(pieces[: first.token_end]).decode("utf-8", errors="replace")
    assert chunks[0]["hash_code"] == hashlib.md5(window.encode()).hexdigest()  # noqa: S324
    # Edge comparison: drop the partial character and the U+FFFD run. Upstream's
    # strip() cannot reach past the U+FFFD, so the whitespace after it stays.
    chunks, chunk_map = chunk_articles(
        [("synthetic:01", text)], max_token_size=max_size + 4, overlap_token_size=4
    )
    second = chunk_map.spans[1]
    assert second.split_char
    assert second.char_start == position
    core = text[second.char_start + 1 : second.char_end]
    assert core.startswith("  is")
    assert chunks[1]["text"].lstrip(FFFD) == core.rstrip().replace("\n", "")
    assert chunks[1]["text"].lstrip(FFFD).startswith("  is")


def test_one_token_windows_inside_one_character_each_map_to_that_character() -> None:
    text = "ꞵ"
    chunks, chunk_map = chunk_articles(
        [("synthetic:01", text)], max_token_size=1, overlap_token_size=0
    )
    assert len(chunks) == 3
    assert all(c["text"] == FFFD for c in chunks)
    assert [(s.char_start, s.char_end, s.split_char) for s in chunk_map.spans] == [(0, 1, True)] * 3
    assert chunk_map.flagged == 3


def test_flagged_window_with_a_wrong_edge_fails_loudly() -> None:
    text = "Coefficient ꞵ is reported here."
    max_size, _ = split_windows(text, "ꞵ")
    articles = [("synthetic:01", text)]
    chunks = upstream_chunks([text], max_token_size=max_size, overlap_token_size=0)
    tampered = [dict(c) for c in chunks]
    tampered[1]["text"] = "x" + tampered[1]["text"][1:]
    with pytest.raises(ChunkMapError, match=r"synthetic:01.*window 1"):
        map_chunks(articles, tampered, max_token_size=max_size, overlap_token_size=0)


def test_duplicate_chunk_text_in_two_articles_gives_one_hash_with_two_spans() -> None:
    shared = "Identical paragraph about tail risk in credit models."
    articles = [("synthetic:01", shared), ("synthetic:02", shared)]
    chunks, chunk_map = chunk_articles(articles)
    assert chunks[0]["hash_code"] == chunks[1]["hash_code"]
    # Upstream keys chunks by hash, so its dict holds one; the map keeps both spans.
    assert len({c["hash_code"]: c for c in chunks}) == 1
    (hash_code, spans), *_ = chunk_map.duplicates.items()
    assert hash_code == chunks[0]["hash_code"]
    assert [(s.article_id, s.char_start, s.char_end) for s in spans] == [
        ("synthetic:01", 0, len(shared)),
        ("synthetic:02", 0, len(shared)),
    ]


def test_span_whose_text_does_not_match_fails_loudly() -> None:
    articles = [("synthetic:01", ASCII)]
    chunks = upstream_chunks([ASCII], max_token_size=8, overlap_token_size=2)
    tampered = [dict(c) for c in chunks]
    tampered[2]["text"] = tampered[2]["text"].replace("e", "a", 1)
    with pytest.raises(ChunkMapError, match=r"synthetic:01.*window 2.*text"):
        map_chunks(articles, tampered, max_token_size=8, overlap_token_size=2)


def test_hash_mismatch_and_wrong_chunk_count_fail_loudly() -> None:
    articles = [("synthetic:01", ASCII)]
    chunks = upstream_chunks([ASCII], max_token_size=8, overlap_token_size=2)
    tampered = [dict(c) for c in chunks]
    tampered[0]["hash_code"] = "0" * 32
    with pytest.raises(ChunkMapError, match=r"window 0.*hash"):
        map_chunks(articles, tampered, max_token_size=8, overlap_token_size=2)
    with pytest.raises(ChunkMapError, match="chunks"):
        map_chunks(articles, chunks[:-1], max_token_size=8, overlap_token_size=2)
    with pytest.raises(ChunkMapError, match="chunks"):
        map_chunks(articles, [*chunks, chunks[0]], max_token_size=8, overlap_token_size=2)


def write_fixture(root: Path, texts: dict[str, str]) -> None:
    (root / "articles").mkdir(parents=True)
    records = []
    for article_id, text in texts.items():
        (root / "articles" / (article_id.replace(":", "-") + ".txt")).write_bytes(text.encode())
        records.append(json.dumps({"id": article_id, "synthetic": True}))
    (root / "articles.jsonl").write_text("\n".join(records) + "\n", encoding="utf-8")


def test_load_articles_reads_in_id_order_without_newline_translation(tmp_path: Path) -> None:
    write_fixture(tmp_path, {"synthetic:02": "second\r\nline", "synthetic:01": "first"})
    assert load_articles(tmp_path) == [
        ("synthetic:01", "first"),
        ("synthetic:02", "second\r\nline"),
    ]


@pytest.mark.parametrize("bad_id", ["../evil", "synthetic:1", "synthetic:01/../x", "other:01"])
def test_load_articles_rejects_ids_that_are_not_synthetic_nn(tmp_path: Path, bad_id: str) -> None:
    write_fixture(tmp_path, {"synthetic:01": "first"})
    with (tmp_path / "articles.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"id": bad_id}) + "\n")
    with pytest.raises(ChunkMapError, match="article id"):
        load_articles(tmp_path)


def test_write_outputs_writes_upstream_chunks_unchanged_and_the_map(tmp_path: Path) -> None:
    articles = [("synthetic:01", "Café — β.\n" * 4), ("synthetic:02", "Coefficient ꞵ here.")]
    chunks, chunk_map = chunk_articles(articles, max_token_size=4, overlap_token_size=1)
    chunks_path, map_path = write_outputs(tmp_path, chunks, chunk_map)

    raw = chunks_path.read_text(encoding="utf-8")
    assert raw == json.dumps(chunks, ensure_ascii=False, indent=2)
    records: list[dict[str, Any]] = [
        json.loads(line) for line in map_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == len(chunks)
    assert set(records[0]) == {
        "chunk_index",
        "hash_code",
        "article_id",
        "window",
        "token_start",
        "token_end",
        "char_start",
        "char_end",
        "split_char",
    }
    assert [r["chunk_index"] for r in records] == list(range(len(chunks)))
    assert any(r["split_char"] for r in records)


def test_chunk_command_writes_both_files_and_reports_flagged_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness.__main__ import main

    fixture = tmp_path / "fixture"
    write_fixture(fixture, {"synthetic:01": "Café — β.", "synthetic:02": "Café — β."})
    # main() moves into the work directory; chdir here first so it is undone.
    monkeypatch.chdir(tmp_path)

    assert main(["chunk", "--fixture", str(fixture), "--out", str(tmp_path / "out")]) == 0
    captured = capsys.readouterr()
    assert captured.out.split() == [
        str(tmp_path / "out" / "chunks.json"),
        str(tmp_path / "out" / "chunk_map.jsonl"),
    ]
    assert "2 chunks from 2 articles" in captured.err
    assert "0 flagged windows" in captured.err
    assert "1 hash_codes with several spans" in captured.err

    assert main(["chunk", "--fixture", str(tmp_path / "missing")]) == 1
    assert "chunk:" in capsys.readouterr().err
