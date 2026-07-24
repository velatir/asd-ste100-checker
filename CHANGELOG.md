# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-07-23

### Added

- Branch-vs-base mode for `ste_check_changed_files` / `ste100 check-changed`
  via `base=` / `--base` (`git merge-base HEAD <base>`).
- Packaging readiness: classifiers, typed marker, documented install path.
- Continuous edge-case gate report refresh for acceptance.

### Changed

- Declared **agent-complete, not ASD-certified**.
- Architecture / MCP / LSP documentation polish in README.
- Development status classifier → Beta.

## [0.6.0] — 2026-07-23

### Added

- HTTP/SSE (streamable) MCP transport: `ste100 serve --transport http|sse|streamable-http`
  with required `STE100_MCP_TOKEN` Bearer auth (stdio unchanged).
- Thin diagnostics LSP: `ste100 lsp` (pygls); Finding → severity/range; filetypes
  md/txt/rst/adoc; no code actions.
- Edge-case corpus `tests/edge_cases/cases.json` (E01–E20, W01–W10).
- Pytest engine harness `tests/test_edge_cases.py`.
- Skill-subagent gate prompt + `scripts/run_skill_gate.py` →
  `tests/edge_cases/gate_report.md`.

## [0.5.0] — 2026-07-23

### Added

- Tier-1–3 rules, stdio MCP (check/lookup/fixes/rewrite/semantic/changed-files/explain),
  skill, CLI, CI.

[1.0.0]: https://github.com/search?q=asd-ste100-checker
[0.6.0]: https://github.com/search?q=asd-ste100-checker
[0.5.0]: https://github.com/search?q=asd-ste100-checker
