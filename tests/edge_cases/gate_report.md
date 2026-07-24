# STE skill/workflow gate report

- Generated: `2026-07-23T16:14:00.967724+00:00`
- Overall: **PASS**
- Harness: `scripts/run_skill_gate.py` (direct MCP tool contracts; no provider LLM)

## How to re-run with Task/subagent

1. Open `tests/edge_cases/SUBAGENT_PROMPT.md`.
2. Load `skill/SKILL.md` in a subagent that can call MCP tools.
3. Execute W01–W10; refresh this report with observed tool sequences.
4. For W09, start `STE100_MCP_TOKEN=… ste100 serve --transport http --host 127.0.0.1 --port 8765`.

## Results

| ID | Pass | Tools | Notes |
|----|------|-------|-------|
| W01 | PASS | `ste_check_text, ste_apply_safe_fixes, ste_check_text` | final_compliant=True fixed='Use the tool.' |
| W02 | PASS | `ste_check_text, ste_explain_finding` | explained STE-IMPERATIVE found=True |
| W03 | PASS | `ste_check_text, ste_suggest_semantic_review, ste_check_text` | tier3_findings=1 |
| W04 | PASS | `ste_check_text, ste_suggest_rewrite, ste_check_text` | errors=2 rewrite_brief=True |
| W05 | PASS | `ste_check_changed_files` | not_a_git_repository shape ok |
| W06 | PASS | `ste_lookup_word, ste_suggest_rewrite` | lookup_found=True alts=['use'] |
| W07 | PASS | `ste_suggest_rewrite` | constraints_ok=True |
| W08 | PASS | `ste_check_text, ste_apply_safe_fixes, ste_check_text` | final_compliant=True fixed='Use the tool.' final_step_is_check=True |
| W09 | PASS | `ste_check_text, ste_apply_safe_fixes, ste_check_text` | http ok url=http://127.0.0.1:48447/mcp final=True |
| W10 | PASS | `—` | mapped STE-IMPERATIVE → severity=DiagnosticSeverity.Error range=0:16-0:22 |

## Coverage notes

- W01–W08: automated MCP function contracts (tool subsequence + outcomes).
- W09: HTTP transport smoke when `STE100_MCP_TOKEN` is set; otherwise local
  contract still runs and HTTP is documented as skipped.
- W10: LSP Finding→diagnostic mapping (severity/range/code) for E04 sample.
