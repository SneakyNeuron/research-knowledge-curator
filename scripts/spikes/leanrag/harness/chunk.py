"""Chunk export and offset map (spec R6).

Runs upstream's ``file_chunk.chunk_documents`` unchanged over the articles in ID
order and keeps its output unchanged (``chunks.json``). Upstream keeps only
``{hash_code, text}``: the text has been ``strip()``-ped and had every ``\\n``
removed, windows overlap, identical windows share one ``hash_code``, and a
window can start or end inside a multi-byte character. So its text cannot be
found again by searching the article. This module rebuilds each window instead:

1. Re-encode the article with the same tiktoken encoding and recompute the
   windows exactly as upstream does (starts ``0, step, 2*step, ...`` with
   ``step = max - overlap``), taking upstream's chunks in order.
2. Map each token window to byte offsets (the tokens' bytes concatenate to the
   article's UTF-8), then to character offsets. An edge inside a multi-byte
   character is widened to the whole character and the span gets ``split_char``.
3. Verify each span: ``md5`` of the decoded window is ``hash_code``, and the
   span after upstream's post-processing is the chunk's ``text``. At a split
   edge the partial character is dropped from the span and the U+FFFD it
   decodes to from the chunk text; upstream's ``strip()`` cannot reach past
   that U+FFFD, so the span is not stripped on that side.

Any mismatch raises ``ChunkMapError`` naming the article and window.
"""

import bisect
import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import tiktoken

from harness.generate import ARTICLE_ID
from harness.paths import make_upstream_importable

ENCODING = "cl100k_base"
MAX_TOKEN_SIZE = 1024
OVERLAP_TOKEN_SIZE = 128
FFFD = "�"

Chunk = dict[str, Any]


class ChunkMapError(RuntimeError):
    """A chunk could not be mapped back to its article; the message says where."""


@dataclass(frozen=True)
class ChunkSpan:
    chunk_index: int  # position in chunks.json
    hash_code: str
    article_id: str
    window: int  # window index within the article
    token_start: int
    token_end: int
    char_start: int  # into the article text, widened to whole characters
    char_end: int
    split_char: bool

    def record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChunkMap:
    spans: list[ChunkSpan]

    @property
    def flagged(self) -> int:
        """Number of windows that split a multi-byte character."""
        return sum(span.split_char for span in self.spans)

    @property
    def duplicates(self) -> dict[str, list[ChunkSpan]]:
        """``hash_code``s with several spans (upstream keeps one chunk per hash)."""
        by_hash: dict[str, list[ChunkSpan]] = defaultdict(list)
        for span in self.spans:
            by_hash[span.hash_code].append(span)
        return {h: spans for h, spans in by_hash.items() if len(spans) > 1}


def _post(text: str, strip_start: bool = True, strip_end: bool = True) -> str:
    """Upstream's post-processing (``strip()``, then drop ``\\n``), per edge."""
    if strip_start:
        text = text.lstrip()
    if strip_end:
        text = text.rstrip()
    return text.replace("\n", "")


def upstream_chunks(
    texts: Sequence[str],
    max_token_size: int = MAX_TOKEN_SIZE,
    overlap_token_size: int = OVERLAP_TOKEN_SIZE,
) -> list[Chunk]:
    """Upstream's ``file_chunk.chunk_documents``, called unchanged."""
    make_upstream_importable()
    import file_chunk  # type: ignore[import-not-found]  # upstream, on sys.path

    chunks: list[Chunk] = file_chunk.chunk_documents(
        list(texts),
        model_name=ENCODING,
        max_token_size=max_token_size,
        overlap_token_size=overlap_token_size,
    )
    return chunks


def _map_window(
    article_id: str,
    text: str,
    window: int,
    pieces: Sequence[bytes],
    byte_offsets: Sequence[int],
    char_bytes: Sequence[int],
    token_start: int,
    token_end: int,
    chunk: Chunk,
    chunk_index: int,
) -> ChunkSpan:
    where = f"{article_id} window {window} (chunk {chunk_index})"
    b_start, b_end = byte_offsets[token_start], byte_offsets[token_end]
    decoded = b"".join(pieces[token_start:token_end]).decode("utf-8", errors="replace")
    digest = hashlib.md5(decoded.encode()).hexdigest()  # noqa: S324 - upstream's chunk key
    if digest != chunk.get("hash_code"):
        raise ChunkMapError(f"{where}: md5 of the decoded window is not the chunk's hash_code")

    # char_bytes[i] is the byte offset of character i (plus the total at the end).
    first = bisect.bisect_left(char_bytes, b_start)  # first boundary >= b_start
    last = bisect.bisect_right(char_bytes, b_end) - 1  # last boundary <= b_end
    split_start = char_bytes[first] != b_start
    split_end = char_bytes[last] != b_end
    char_start = first - 1 if split_start else first
    char_end = last + 1 if split_end else last
    if first <= last:
        head = b"".join(pieces[token_start:token_end])[: char_bytes[first] - b_start]
        tail = b"".join(pieces[token_start:token_end])[char_bytes[last] - b_start :]
        core_span = text[first:last]
    else:  # the whole window lies inside one character
        head, tail, core_span = b"".join(pieces[token_start:token_end]), b"", ""
    n_head = len(head.decode("utf-8", errors="replace"))
    n_tail = len(tail.decode("utf-8", errors="replace"))

    chunk_text = chunk.get("text")
    if not isinstance(chunk_text, str):
        raise ChunkMapError(f"{where}: chunk has no text")
    edges = chunk_text[:n_head] + chunk_text[len(chunk_text) - n_tail :]
    core_text = chunk_text[n_head : len(chunk_text) - n_tail]
    expected = _post(core_span, strip_start=not split_start, strip_end=not split_end)
    if len(chunk_text) < n_head + n_tail or set(edges) - {FFFD} or core_text != expected:
        raise ChunkMapError(
            f"{where}: the post-processed span [{char_start}:{char_end}] does not match "
            f"the chunk text (split_char={split_start or split_end})"
        )
    return ChunkSpan(
        chunk_index=chunk_index,
        hash_code=digest,
        article_id=article_id,
        window=window,
        token_start=token_start,
        token_end=token_end,
        char_start=char_start,
        char_end=char_end,
        split_char=split_start or split_end,
    )


def map_chunks(
    articles: Sequence[tuple[str, str]],
    chunks: Sequence[Chunk],
    max_token_size: int = MAX_TOKEN_SIZE,
    overlap_token_size: int = OVERLAP_TOKEN_SIZE,
) -> ChunkMap:
    """Map upstream's chunks (in its output order) to spans of ``articles``."""
    encoder = tiktoken.get_encoding(ENCODING)
    step = max_token_size - overlap_token_size
    spans: list[ChunkSpan] = []
    for article_id, text in articles:
        tokens = encoder.encode(text)
        pieces = [encoder.decode_single_token_bytes(t) for t in tokens]
        byte_offsets = [0]
        for piece in pieces:
            byte_offsets.append(byte_offsets[-1] + len(piece))
        if b"".join(pieces) != text.encode("utf-8"):
            raise ChunkMapError(f"{article_id}: tokens do not re-encode to the article bytes")
        char_bytes = [0]
        for char in text:
            char_bytes.append(char_bytes[-1] + len(char.encode("utf-8")))
        for window, token_start in enumerate(range(0, len(tokens), step)):
            index = len(spans)
            if index >= len(chunks):
                raise ChunkMapError(
                    f"{article_id} window {window}: ran out of chunks ({len(chunks)} chunks)"
                )
            token_end = min(token_start + max_token_size, len(tokens))
            spans.append(
                _map_window(
                    article_id,
                    text,
                    window,
                    pieces,
                    byte_offsets,
                    char_bytes,
                    token_start,
                    token_end,
                    chunks[index],
                    index,
                )
            )
    if len(spans) != len(chunks):
        raise ChunkMapError(
            f"{len(chunks)} chunks but the articles give {len(spans)} windows; "
            "every chunk must be mapped"
        )
    return ChunkMap(spans)


def chunk_articles(
    articles: Sequence[tuple[str, str]],
    max_token_size: int = MAX_TOKEN_SIZE,
    overlap_token_size: int = OVERLAP_TOKEN_SIZE,
) -> tuple[list[Chunk], ChunkMap]:
    """Run upstream's chunker over the articles, then map and verify every chunk."""
    chunks = upstream_chunks([text for _, text in articles], max_token_size, overlap_token_size)
    return chunks, map_chunks(articles, chunks, max_token_size, overlap_token_size)


def load_articles(fixture_dir: Path) -> list[tuple[str, str]]:
    """``(id, text)`` in ID order, from ``articles.jsonl`` and ``articles/``.

    IDs must be ``synthetic:NN`` before they name a file. Text is decoded from
    the exact bytes (no newline translation), since offsets index into it.
    """
    ids: list[str] = []
    lines = (fixture_dir / "articles.jsonl").read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.strip():
            continue
        article_id = json.loads(line).get("id")
        if not isinstance(article_id, str) or not ARTICLE_ID.fullmatch(article_id):
            raise ChunkMapError(f"bad article id in articles.jsonl: {article_id!r}")
        ids.append(article_id)
    articles = []
    for article_id in sorted(set(ids)):
        path = fixture_dir / "articles" / (article_id.replace(":", "-") + ".txt")
        articles.append((article_id, path.read_bytes().decode("utf-8")))
    return articles


def write_outputs(out_dir: Path, chunks: Sequence[Chunk], chunk_map: ChunkMap) -> tuple[Path, Path]:
    """Write ``chunks.json`` as upstream's ``file_chunk.py`` does, and ``chunk_map.jsonl``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = out_dir / "chunks.json"
    with chunks_path.open("w", encoding="utf-8") as f:
        json.dump(list(chunks), f, ensure_ascii=False, indent=2)
    map_path = out_dir / "chunk_map.jsonl"
    lines = [json.dumps(span.record(), ensure_ascii=False) for span in chunk_map.spans]
    map_path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return chunks_path, map_path


def run_chunk(fixture_dir: Path, out_dir: Path) -> tuple[Path, Path]:
    """The ``chunk`` command: chunk, map, verify, write and report."""
    articles = load_articles(fixture_dir)
    if not articles:
        raise ChunkMapError(f"no articles listed in {fixture_dir / 'articles.jsonl'}")
    chunks, chunk_map = chunk_articles(articles)
    paths = write_outputs(out_dir, chunks, chunk_map)
    duplicates = chunk_map.duplicates
    print(
        f"chunk: {len(chunks)} chunks from {len(articles)} articles "
        f"({MAX_TOKEN_SIZE}/{OVERLAP_TOKEN_SIZE} {ENCODING}); "
        f"{chunk_map.flagged} flagged windows (split_char); "
        f"{len(duplicates)} hash_codes with several spans",
        file=sys.stderr,
    )
    return paths
