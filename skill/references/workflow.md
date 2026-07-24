# Rewrite / recheck workflow

Unofficial tool. Not affiliated with ASD. EU TM No. 017966390.

This document expands the skill workflow. The engine is deterministic; you
(the agent) rewrite with your own LLM, then recheck via MCP.

## 0. Multi-file first pass

When the user asks about changed docs, a PR, or “what I edited locally”:

1. Call **`ste_check_changed_files`** (or CLI `ste100 check-changed`).
2. It compares the working tree to **`HEAD`** (staged + unstaged + untracked).
3. Default globs: `*.md`, `*.txt`, `*.rst`, `*.adoc` (override with `globs` / `--glob`).
4. Aggregate `compliant` is true only when every matched file has no ERROR findings.
5. Then drill into individual files with `ste_check_file` / `ste_suggest_rewrite` as needed.

Requires a git repository. If not in a repo, the tool returns a clear error.

## 1. Classify: procedure vs description

| Signal | Prefer `procedure` | Prefer `description` |
|--------|--------------------|----------------------|
| Mood | Imperative verbs, numbered steps | Declarative statements |
| Purpose | Tell the reader what to do | Explain what something is/does |
| Typical headings | Procedure, Removal, Installation, Warning | Description, Overview, Function |

If mixed, set `text_type` to the dominant type for the span you are checking, or use `auto` and accept the analyzer’s choice.

Pass the classification into `ste_check_text` / `ste_check_file` / `ste_suggest_rewrite` as `text_type`.

## 2. Sentence length limits (Tier-1)

| Text type | Max words per sentence |
|-----------|------------------------|
| Procedure | **20** |
| Description | **25** |

Count words in the English sentence the engine segments. Split long sentences; do not pack multiple instructions into one procedural sentence.

### Procedure — too long / multi-instruction

```text
Remove the cover and disconnect the cable and inspect the connector for damage.
```

Rewrite (one instruction per sentence, ≤ 20 words):

```text
Remove the cover.
Disconnect the cable.
Inspect the connector for damage.
```

### Description — too long

```text
The hydraulic pump supplies pressure to the landing gear system and also provides backup pressure to the brake system during emergency operation.
```

Rewrite (≤ 25 words each):

```text
The hydraulic pump supplies pressure to the landing gear system.
It also supplies backup pressure to the brake system during emergency operation.
```

## 2b. Tier-2 syntax (deterministic)

| Rule ID | Fix approach |
|---------|--------------|
| `STE-PASSIVE` | Rewrite procedures in active voice / imperative. Past participles used as adjectives (Rule 3.3) are not errors. |
| `STE-IMPERATIVE` | Numbered steps must be commands (`Close the valve.`). |
| `STE-VERB-FORM` | Drop progressive/perfect/modal+passive; use approved simple forms. |
| `STE-NOUN-CLUSTER` | Keep multi-word nouns to ≤ 3 words. |

Call `ste_explain_finding(rule_id)` when a finding’s meaning is unclear. ERRORs are authoritative; WARNINGs are advisory unless the user asks to clear them.

Evidence on Tier-2 findings includes `confidence`, `parse_cue`, `text_type`, and `rule_ref`.

## 2c. Tier-3 semantic (hybrid heuristics)

| Rule ID | Scope | Fix approach |
|---------|-------|--------------|
| `STE-PRONOUN-AMBIG` | both | Name the noun instead of `it` / `this` / `these` / `those` / `they` when the prior sentence has no clear antecedent or multiple candidates. |
| `STE-TOPIC-SENTENCE` | description only | Put the topic noun in the first sentence; avoid pronoun/demonstrative starts, fragments, pure coordination, and meta-comments. |
| `STE-POS-MISMATCH` | both | Use the approved dictionary part of speech (`verb↔noun` / `adj↔noun`). High-confidence clashes are ERRORs; TN/TV and unapproved words are skipped (vocab owns them). |

Default severity is WARNING. Only high-confidence approved POS clashes escalate to ERROR.

After check, if Tier-3 WARNINGs remain → call **`ste_suggest_semantic_review`** → host judgment → recheck.
POS ERRORs still go through the rewrite path and must clear before claiming done.

## 3. Check → explain → suggest_rewrite → (semantic_review) → host rewrite → recheck

```text
(optional) ste_check_changed_files   # multi-file / local changes
   ↓
classify
   ↓
ste_check_text / ste_check_file
   ↓
ERROR findings?
   ├─ no  → if Tier-3 WARNINGs → ste_suggest_semantic_review → host edit → recheck
   │         else report “no ERROR findings on recheck” (still unofficial; not certified)
   └─ yes → optional ste_explain_finding
              ↓
            optional ste_apply_safe_fixes (1:1 only) + recheck
              ↓
            ste_suggest_rewrite  → use returned prompt (host LLM; no API in MCP)
              ↓
            host produces minimal rewrite
              ↓
            (optional) ste_suggest_semantic_review for remaining Tier-3 WARNINGs
              ↓
            ste_check_text again
              ↓
            remaining ERRORs?
              ├─ no  → done
              └─ yes → repeat suggest_rewrite / rewrite / recheck
                         OR report unresolved findings
```

### Rules for each rewrite pass

1. Treat every `severity: "error"` finding as must-fix unless you cannot without changing safety meaning—then report it unresolved.
2. Prefer the finding’s `suggestions` when present and high-confidence.
3. Change the smallest span that clears the finding.
4. Do not “improve” style beyond what findings require.
5. Prefer **`ste_suggest_rewrite`** over ad-hoc prompting; follow its `constraints`.
6. Prefer **`ste_suggest_semantic_review`** for Tier-3 WARNINGs; follow its `constraints`.
7. After every rewrite (including safe-fixes), call `ste_check_text` again.
8. Never claim compliance from an unchecked rewrite.
9. Treat `warning` as advisory unless the user asks to clear warnings.

## 4. Vocabulary and glossary

- Unapproved / forbidden words → replace with approved alternatives from the finding or `ste_lookup_word`.
- Project glossary terms override or extend the dictionary when a glossary path is passed.
- Prefer glossary `preferred_terms` mappings when both forms appear.

## 5. Preserve always

Do not alter unless a finding explicitly requires a synonym that keeps the same referent:

- Part numbers, serial numbers, document IDs, software identifiers
- Numeric values and units (e.g. `5 mm`, `120 °C`)
- Warning / Caution / Note labels and safety-critical conditions
- Proper names required by the product or regulation

## 6. Stopping criteria

**Done:** recheck returns `compliant: true` or zero ERROR findings.

**Stop with report:** remaining ERRORs that you cannot clear without inventing data or changing safety meaning. List each unresolved finding (`rule_id`, span/evidence, reason).

**Forbidden:** claiming certified ASD-STE100 compliance; claiming the text is compliant because you rewrote it without a successful MCP recheck.

## 7. Example end-to-end

**Input (procedure):**

```text
Utilize a torque wrench to carefully tighten the bolts and then check them.
```

1. Classify → `procedure`
2. `ste_check_text(..., text_type="procedure")` → errors for `utilize`, sentence length / multi-instruction
3. Optional: `ste_explain_finding` / `ste_apply_safe_fixes` may yield `Use a torque wrench...` still multi-instruction
4. `ste_suggest_rewrite` → use `prompt` + `constraints`
5. Minimal rewrite:

```text
Use a torque wrench to tighten the bolts.
Then check the bolts.
```

6. `ste_check_text` on the rewrite → no ERROR findings → report rewrite + note that results are unofficial / not certified.

**Input (Tier-2 passive step):**

```text
1. The valve is closed by the operator.
```

1. Classify → `procedure`
2. Check → `STE-PASSIVE` / `STE-IMPERATIVE` ERRORs (call `ste_explain_finding` if needed)
3. `ste_suggest_rewrite` → host rewrite → `1. Close the valve.`
4. Recheck → no ERROR findings for those rules

**Input (Tier-3 ambiguous pronoun):**

```text
Remove the panel from the unit. It is damaged.
```

1. Classify → `description`
2. Check → `STE-PRONOUN-AMBIG` WARNING (`compliant` may still be true)
3. `ste_suggest_semantic_review` → host names the noun → `The panel is damaged.`
4. Recheck → no Tier-3 findings for that span
