"""Harness command line. Run from ``scripts/spikes/leanrag`` with the harness venv:

work/venv/bin/python -m harness check
work/venv/bin/python -m harness write-config
work/venv/bin/python -m harness generate --model-revision <HF commit> [--only synthetic:NN]
    [--retry-temperature T]
work/venv/bin/python -m harness chunk [--fixture DIR] [--out DIR]
"""

import argparse
import logging
import math
import os
import sys
from pathlib import Path

from harness.paths import (
    CORPUS_SPEC,
    FIXTURE_DIR,
    WORK_DIR,
    enter_work_dir,
    make_upstream_importable,
)
from harness.settings import Settings, SettingsError
from harness.upstream_config import write_config


def cmd_write_config() -> int:
    try:
        settings = Settings.from_env(dict(os.environ))
    except SettingsError as exc:
        print(f"write-config: {exc}", file=sys.stderr)
        return 1
    print(write_config(settings, WORK_DIR))
    return 0


def cmd_check() -> int:
    from harness.check import run_checks

    results = run_checks()
    for result in results:
        mark = "ok  " if result.ok else "FAIL"
        print(f"{mark} {result.name}: {result.detail}", file=sys.stderr)
    failed = [r.name for r in results if not r.ok]
    if failed:
        print(f"check failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("check passed", file=sys.stderr)
    return 0


def cmd_generate(
    spec: Path, out: Path, revision: str, only: list[str], temperature: float = 0
) -> int:
    from harness.adapter import ChatAdapter
    from harness.generate import CorpusSpecError, GeneratedBy, generate_corpus

    try:
        settings = Settings.from_env(dict(os.environ))
    except SettingsError as exc:
        print(f"generate: {exc}", file=sys.stderr)
        return 1
    adapter = ChatAdapter(settings, temperature=temperature)
    generated_by = GeneratedBy(
        model=settings.chat_model, revision=revision, seed=settings.seed, temperature=temperature
    )
    try:
        failures, warnings = generate_corpus(
            spec,
            out,
            lambda system, prompt: adapter.generate_text(prompt, system_prompt=system),
            generated_by,
            only,
        )
    except CorpusSpecError as exc:
        print(f"generate: {exc}", file=sys.stderr)
        return 1
    stats = adapter.stats()
    print(
        f"generate: {stats.calls} chat calls, {stats.empty_responses} empty responses, "
        f"longest prompt {stats.max_prompt_tokens} cl100k tokens",
        file=sys.stderr,
    )
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for failure in failures:
        print(f"FAILED: {failure}", file=sys.stderr)
    if failures:
        print(
            "generate: some articles failed and were not written; regenerate them with "
            "--only synthetic:NN --retry-temperature T (T > 0, e.g. 0.7) and another "
            "LEANRAG_SEED (at temperature 0 a new seed changes nothing; both are recorded "
            "per article)",
            file=sys.stderr,
        )
        return 1
    print(out / "articles.jsonl")
    return 0


def cmd_chunk(fixture: Path, out: Path) -> int:
    from harness.chunk import ChunkMapError, run_chunk

    try:
        chunks_path, map_path = run_chunk(fixture, out)
    except (ChunkMapError, OSError, ValueError) as exc:
        print(f"chunk: {exc}", file=sys.stderr)
        return 1
    print(chunks_path)
    print(map_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="verify upstream, MySQL, both vLLM instances and metrics")
    commands.add_parser("write-config", help="write upstream's config.yaml into the work dir")
    generate = commands.add_parser("generate", help="generate the synthetic corpus")
    generate.add_argument(
        "--model-revision",
        required=True,
        help="Hugging Face commit of the served chat model (recorded in generated_by)",
    )
    generate.add_argument("--spec", type=Path, default=CORPUS_SPEC, help="corpus_spec.yaml")
    generate.add_argument(
        "--out", type=Path, default=FIXTURE_DIR, help="output directory (default: the fixture)"
    )
    generate.add_argument(
        "--only", action="append", default=[], metavar="synthetic:NN", help="repeatable"
    )
    generate.add_argument(
        "--retry-temperature",
        type=float,
        metavar="T",
        help="retry failed articles at temperature T > 0 instead of 0 (only with --only)",
    )
    chunk = commands.add_parser(
        "chunk", help="chunk the articles with upstream's chunker and write the offset map"
    )
    chunk.add_argument(
        "--fixture",
        type=Path,
        default=FIXTURE_DIR,
        help="directory with articles.jsonl and articles/ (default: the fixture)",
    )
    chunk.add_argument(
        "--out",
        type=Path,
        help="where chunks.json and chunk_map.jsonl go (default: the --fixture directory)",
    )
    args = parser.parse_args(argv)
    if args.command == "generate":
        retry = args.retry_temperature
        if retry is not None and not args.only:
            generate.error("--retry-temperature is allowed only with --only")
        if retry is not None and not (math.isfinite(retry) and retry > 0):
            generate.error(f"--retry-temperature must be a finite number above 0, not {retry}")
        # Resolve before moving into the work directory.
        args.spec, args.out = args.spec.resolve(), args.out.resolve()
    if args.command == "chunk":
        args.fixture = args.fixture.resolve()
        args.out = args.out.resolve() if args.out is not None else args.fixture

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    make_upstream_importable()
    enter_work_dir()
    if args.command == "check":
        return cmd_check()
    if args.command == "generate":
        temperature = args.retry_temperature if args.retry_temperature is not None else 0
        return cmd_generate(args.spec, args.out, args.model_revision, args.only, temperature)
    if args.command == "chunk":
        return cmd_chunk(args.fixture, args.out)
    return cmd_write_config()


if __name__ == "__main__":
    sys.exit(main())
