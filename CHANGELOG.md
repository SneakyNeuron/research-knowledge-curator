# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- The `rkc` command (also available as `research-knowledge-curator`) can be installed. For now it only reports its version: `rkc --version`, or `rkc version --json` for scripts and agents.
- Every command accepts `--json` for machine-readable output. Running `rkc` with no command shows the help.
- Automated checks (linting, formatting, type checks and offline tests) run on Python 3.12 and 3.14 for every push and pull request.
- MIT license, contributor guide for coding agents (`CLAUDE.md`), and an `.env.example` showing how API keys are supplied without ever writing them into configuration.
