---
name: asd-ste100
description: Check, rewrite, or review technical procedures and descriptions for ASD-STE100-style compliance. Use for manuals, instructions, warnings, maintenance text, technical requirements, and controlled-language reviews.
---

# ASD-STE100 Checker Skill

> **Unofficial — not affiliated with, endorsed by, or sponsored by ASD.**
> ASD-STE100 is a registered European Union Trade Mark (No. 017966390).
> This skill and the companion MCP/engine are an independent tool. They make
> **no claim of official compliance or certification**.

## When to use

Use this skill when the user asks to:

- Check or rewrite manuals, procedures, warnings, maintenance text, or technical descriptions for STE-style clarity
- Review controlled language / Simplified Technical English wording
- Look up whether a word is approved and what alternatives exist
- Apply safe synonym fixes before a full rewrite
- Explain what a checker `rule_id` means and how to fix it
- Check only locally changed documentation files in a git working tree
- Judge Tier-3 semantic WARNINGs (pronouns, topic sentence, POS) via a review brief

Do **not** use this skill for creative writing, marketing copy, or general English editing unrelated to technical procedures/descriptions.

## Core principles

- Prefer short sentences (procedures ≤ 20 words; descriptions ≤ 25 words).
- Use approved dictionary words; prefer project glossary terms when provided.
- Write procedures in active, imperative mood (one instruction per sentence).
- Avoid progressive/perfect/complex verb stacks; keep multi-word nouns ≤ 3 words.
- Name nouns instead of ambiguous pronouns; put the topic in the first descriptive sentence.
- Use each approved word in its approved part of speech only.
- One meaning per word; do not invent alternate senses.
- Preserve identifiers, measurements, part numbers, and safety information.

## Strict workflow

1. **Multi-file / PR-local docs:** call **`ste_check_changed_files`** first (working tree vs `HEAD`, or pass `base=` for merge-base vs a branch; default globs `*.md` / `*.txt` / `*.rst` / `*.adoc`).
2. **Classify** the text as `procedure` or `description` (or leave as `auto` if unsure).
3. **Check** with MCP: `ste_check_text` (paste) or `ste_check_file` (path). Pass a glossary path when available.
4. **Treat deterministic ERROR findings as authoritative.** Do not dismiss ERROR results based on your own judgment (includes high-confidence `STE-POS-MISMATCH`).
5. **WARNINGs are advisory** (Tier-2 parse confidence or Tier-3 semantic heuristics). Prefer fixing them; leave with rationale only if unclear, unless the user asks to clear warnings too.
6. If unsure what a `rule_id` means, call **`ste_explain_finding(rule_id)`**.
7. **Optionally** call `ste_apply_safe_fixes` first for unambiguous 1:1 synonyms (e.g. `utilize` → `use`), then recheck.
8. Call **`ste_suggest_rewrite`** to get a structured rewrite brief (`prompt` + capped findings + `constraints` + optional `safe_fix_preview`). It does **not** call an LLM — **you** (the host agent) rewrite from that brief.
9. If Tier-3 WARNINGs remain (`STE-PRONOUN-AMBIG`, `STE-TOPIC-SENTENCE`, or advisory `STE-POS-MISMATCH`), call **`ste_suggest_semantic_review`**, judge the brief, edit, then recheck.
10. **Propose a minimal rewrite** using the brief(s). Change only what ERROR findings require (and WARNINGs when requested).
11. **Recheck** the rewrite with `ste_check_text`.
12. **Stop** only when no ERROR findings remain, **or** explicitly list unresolved findings and why they remain.
13. **Never** claim certified compliance. **Never** claim compliance from your rewrite alone without a successful recheck.
14. **Preserve** part numbers, measurements, identifiers, warnings, cautions, and safety-critical wording unless a finding requires a synonym that does not change meaning.

Canonical loop: **check → explain → suggest_rewrite → (optional semantic_review) → host rewrite → recheck**.

Details: [references/workflow.md](references/workflow.md)

## MCP tools

| Tool | Use when |
|------|----------|
| `ste_check_text(text, text_type="auto", glossary=None, output="json")` | Check pasted/generated text; primary loop tool |
| `ste_check_file(path, text_type="auto", output="json")` | Check a file on disk |
| `ste_check_changed_files(globs=None, text_type="auto", glossary=None, output="json", base=None)` | Check working-tree doc changes vs `HEAD`, or vs `git merge-base HEAD <base>` |
| `ste_lookup_word(word)` | Inspect status, meaning, alternatives, inflections, rule_ref |
| `ste_explain_finding(rule_id)` | Explain a finding’s rule (title, severity, STE ref, fix hints) |
| `ste_apply_safe_fixes(text, glossary=None)` | Apply only unambiguous 1:1 synonym replacements; returns text + diff |
| `ste_suggest_rewrite(text, text_type="auto", glossary=None, max_findings=20)` | Build a host-agent rewrite brief (prompt-return; no LLM API) |
| `ste_suggest_semantic_review(text, text_type="auto", glossary=None, max_findings=20)` | Tier-3-only semantic brief (prompt-return; no LLM API) |

### spaCy model (MCP)

Check tools do **not** take a spaCy model parameter. Set `STE100_SPACY_MODEL`
in the MCP server environment before start (default `en_core_web_sm`).

### When to use `ste_suggest_rewrite`

Call it after you have ERROR (or requested WARNING) findings and before you
rewrite with your own LLM. Use `prompt` as the rewrite instructions; respect
`constraints`. Optionally inspect `safe_fix_preview` — call
`ste_apply_safe_fixes` only if you want those 1:1 synonyms applied.

### When to use `ste_suggest_semantic_review`

Call it when the check returns Tier-3 findings (especially WARNINGs for pronouns
or topic sentence). Use `prompt` for host judgment; clear POS ERRORs before
claiming done. Semantic WARNINGs alone do not make `compliant: false`.

### When to use `ste_apply_safe_fixes`

Call it **before** a manual rewrite when findings are mostly vocabulary synonyms with a single clear approved alternative. Do **not** use it for sentence splits, voice/mood changes, or ambiguous terms—rewrite those yourself, then recheck.

### Tier-2 rule IDs

| Rule ID | Meaning |
|---------|---------|
| `STE-PASSIVE` | Verbal passive in procedures (Rule 3.6) |
| `STE-IMPERATIVE` | Non-imperative procedural step (Rule 5.3) |
| `STE-VERB-FORM` | Progressive / perfect / complex verb stack (Rules 3.2 / 3.4) |
| `STE-NOUN-CLUSTER` | Multi-word noun longer than 3 words (Rule 2.1) |

### Tier-3 rule IDs

| Rule ID | Meaning |
|---------|---------|
| `STE-PRONOUN-AMBIG` | Ambiguous pronoun (`it` / `this` / `these` / `those` / `they`) |
| `STE-TOPIC-SENTENCE` | Weak description opener (topic not clear) |
| `STE-POS-MISMATCH` | Approved POS clash (`verb↔noun` / `adj↔noun`); ERROR if high-confidence |

Result shapes: [references/result-format.md](references/result-format.md)  
Project glossaries: [references/terminology-profiles.md](references/terminology-profiles.md)
