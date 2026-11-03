"""Harness command line. Run from ``scripts/spikes/leanrag`` with the harness venv:

work/venv/bin/python -m harness check
work/venv/bin/python -m harness write-config
"""

import argparse
import logging
import os
import sys

from harness.paths import WORK_DIR, enter_work_dir, make_upstream_importable
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="verify upstream, MySQL, both vLLM instances and metrics")
    commands.add_parser("write-config", help="write upstream's config.yaml into the work dir")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    make_upstream_importable()
    enter_work_dir()
    if args.command == "check":
        return cmd_check()
    return cmd_write_config()


if __name__ == "__main__":
    sys.exit(main())
