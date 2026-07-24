# Skill-subagent gate prompt (W01–W10)

Use this prompt with a Task/subagent that can call STE MCP tools (stdio or HTTP).
Automated contract checks also live in `scripts/run_skill_gate.py` and write
`tests/edge_cases/gate_report.md` without requiring an LLM.

## Setup

1. Load `skill/SKILL.md` and follow its workflow.
2. Prefer real MCP tools (`ste_check_text`, `ste_apply_safe_fixes`,
   `ste_suggest_rewrite`, `ste_suggest_semantic_review`, `ste_lookup_word`,
   `ste_explain_finding`, `ste_check_changed_files`).
3. Do **not** claim ASD-STE100 compliance or certification.
4. Do **not** call any provider LLM API from inside the MCP server (the host
   agent may rewrite using a brief).

## Cases

Read `tests/edge_cases/cases.json` workflow cases `W01`–`W10`.

For each workflow case:

1. Call tools in an order that matches `expect_tools` as an ordered subsequence
   (alternatives separated by `|` mean either tool is acceptable at that step).
2. Satisfy `expect` outcomes (final recheck, explain known rule, constraints, etc.).
3. Record: tools called (ordered), pass/fail, brief notes.

## Scoring

- Pass if tool subsequence matches and outcome checks succeed.
- `W09` requires HTTP transport (`STE100_MCP_TOKEN` + `ste100 serve --transport http`).
- `W10` requires LSP Finding→diagnostic mapping (offsets/severity) for the E04 sample.

## Report

Write or refresh `tests/edge_cases/gate_report.md` with one section per workflow
case and an overall pass/fail summary.

## Re-run without an LLM subagent

```bash
source .venv/bin/activate
python scripts/run_skill_gate.py
```

That script executes W01–W08 (and W10) via direct MCP tool function calls, and
attempts W09 when `STE100_MCP_TOKEN` is set and HTTP is reachable; otherwise it
documents the HTTP smoke as skipped/manual.
