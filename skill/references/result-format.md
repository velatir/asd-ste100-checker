# Result format

Unofficial tool. Not affiliated with ASD. EU TM No. 017966390.

Primary MCP/CLI output is JSON mirroring `ste100/core/schema.py`. Optional
SARIF is available via `output="sarif"` on check tools.

## Severity meanings

| Severity | Meaning | Agent action |
|----------|---------|--------------|
| `error` | Determinative Tier-1/Tier-2/Tier-3 violation (high-confidence) | **Authoritative.** Must fix or explicitly report unresolved. |
| `warning` | Likely issue; may be heuristic / lower-confidence Tier-2 or Tier-3 | Prefer fixing; may leave with rationale if unclear unless user asks to clear warnings. |
| `info` | Advisory / context | Optional; do not treat as compliance failure. |

`AnalysisResult.compliant` is `true` only when there are no ERROR-level findings (engine definition). Warnings/info alone do not make a text non-compliant in the engine’s boolean.

Tier-2 / Tier-3 findings include evidence keys: `confidence`, `parse_cue`, `text_type`, `rule_ref`. Call MCP `ste_explain_finding(rule_id)` for titles, fix hints, and STE mapping.

### Tier-2 rule IDs

| `rule_id` | STE ref | Typical scope |
|-----------|---------|---------------|
| `STE-PASSIVE` | Rule 3.6 | procedure |
| `STE-IMPERATIVE` | Rule 5.3 | procedure |
| `STE-VERB-FORM` | Rule 3.2 / 3.4 | both |
| `STE-NOUN-CLUSTER` | Rule 2.1 | both |

### Tier-3 rule IDs

| `rule_id` | STE ref | Typical scope |
|-----------|---------|---------------|
| `STE-PRONOUN-AMBIG` | STE pronoun clarity | both |
| `STE-TOPIC-SENTENCE` | STE topic sentence | description |
| `STE-POS-MISMATCH` | Rule 1.2 / 1.3 | both (ERROR if high-conf) |

`ste_suggest_semantic_review` returns Tier-3 findings only, plus a host-agent `prompt`. Semantic WARNINGs alone do not make `compliant` false.

## Finding

A single located rule violation.

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | `string` | Stable rule identifier (e.g. vocabulary or sentence rule). |
| `severity` | `"error"` \| `"warning"` \| `"info"` | See table above. |
| `message` | `string` | Human-readable explanation. |
| `start` | `int` | Inclusive UTF-8/codepoint offset into the analyzed text. |
| `end` | `int` | Exclusive offset of the flagged span. |
| `sentence` | `int` \| `null` | 0-based sentence index when known. |
| `evidence` | `object` | Rule-specific context (word, count, etc.). Default `{}`. |
| `suggestions` | `Suggestion[]` | Proposed replacements. Default `[]`. |

### Suggestion

| Field | Type | Description |
|-------|------|-------------|
| `replacement` | `string` | Proposed text for the span. |
| `confidence` | `float` | 0.0–1.0; default `0.0`. |
| `automatic` | `bool` | `true` if suitable for `ste_apply_safe_fixes`-style auto apply. Default `false`. |

### Example Finding (JSON)

```json
{
  "rule_id": "vocabulary.unapproved",
  "severity": "error",
  "message": "Word 'utilize' is not approved; prefer 'use'.",
  "start": 0,
  "end": 7,
  "sentence": 0,
  "evidence": {
    "word": "utilize",
    "status": "unapproved"
  },
  "suggestions": [
    {
      "replacement": "use",
      "confidence": 1.0,
      "automatic": true
    }
  ]
}
```

## AnalysisResult

Full check response for `ste_check_text` / `ste_check_file` when `output="json"`.

| Field | Type | Description |
|-------|------|-------------|
| `text_type` | `"auto"` \| `"procedure"` \| `"description"` | Effective classification used for the run (`auto` may be resolved by the analyzer before rules run; the returned value reflects the type applied). |
| `compliant` | `bool` | `true` if no ERROR findings. |
| `findings` | `Finding[]` | All findings; may be empty. |
| `summary` | `object` | Aggregates (counts by severity/rule). Default `{}`. |

### Example AnalysisResult (JSON)

```json
{
  "text_type": "procedure",
  "compliant": false,
  "findings": [
    {
      "rule_id": "sentence.length",
      "severity": "error",
      "message": "Procedural sentence has 24 words; maximum is 20.",
      "start": 0,
      "end": 118,
      "sentence": 0,
      "evidence": { "word_count": 24, "limit": 20 },
      "suggestions": []
    }
  ],
  "summary": {
    "error": 1,
    "warning": 0,
    "info": 0
  }
}
```

## Related schema types (not always in check output)

These models live in the same schema module; agents may see them via
`ste_lookup_word` or glossary loading, not always in `AnalysisResult`.

### DictionaryRecord (lookup)

| Field | Type |
|-------|------|
| `word` | `string` |
| `part_of_speech` | `string` |
| `status` | `WordStatus` enum string |
| `approved_meaning` | `string` \| `null` |
| `inflections` | `string[]` |
| `alternatives` | `string[]` |
| `category` | `string` \| `null` |
| `rule_ref` | `string` \| `null` |
| `examples_ste` / `examples_non_ste` | `string[]` |
| `notes` | `string` \| `null` |

`WordStatus` values: `approved`, `unapproved`, `forbidden`, `technical_noun`,
`technical_verbs`, `not_approved_technical_verb`.

### Glossary (YAML profile → engine)

| Field | Type |
|-------|------|
| `name` | `string` |
| `technical_nouns` | `GlossaryEntry[]` |
| `technical_verbs` | `GlossaryEntry[]` |
| `preferred_terms` | `map[string, string]` |

See [terminology-profiles.md](terminology-profiles.md).

## SARIF note

When `output="sarif"`, the same findings are serialized as a SARIF 2.1.0
log suitable for CI upload / code-scanning UIs.

- Each Finding maps to a SARIF `result` (`ruleId` ← `rule_id`, level from severity).
- Offsets map to a physical location on the analyzed artifact.
- Prefer JSON for the agent rewrite loop; use SARIF for tooling pipelines.

Severity → SARIF level (typical mapping):

| Severity | SARIF level |
|----------|-------------|
| `error` | `error` |
| `warning` | `warning` |
| `info` | `note` |

Exact SARIF field layout is owned by `ste100/core/serialize.py`; treat this
section as contract intent, not a second schema.
