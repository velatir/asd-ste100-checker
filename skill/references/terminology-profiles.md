# Terminology profiles (project glossaries)

Unofficial tool. Not affiliated with ASD. EU TM No. 017966390.

Pass a glossary YAML path to `ste_check_text` / `ste_apply_safe_fixes` via the
`glossary` argument so project-specific nouns, verbs, and preferred terms are
recognized during checks and safe fixes.

The engine loads YAML into the `Glossary` model from `ste100/core/schema.py`.

## File shape

```yaml
name: <profile-name>          # required string

technical_nouns:              # optional list
  - word: <lemma>
    part_of_speech: noun      # default: noun
    status: technical_noun    # default: technical_noun
    approved_meaning: <str>   # optional
    inflections: []           # optional list of surface forms
    preferred_term: <str>     # optional canonical display form

technical_verbs:              # optional list
  - word: <lemma>
    part_of_speech: verb
    status: technical_verbs   # default for verbs when set explicitly
    approved_meaning: <str>
    inflections: []
    preferred_term: <str>

preferred_terms:              # optional map: dispreferred → preferred
  <unwanted-form>: <preferred-form>
```

### Field notes

| Key | Purpose |
|-----|---------|
| `technical_nouns` | Product/domain nouns not in (or extending) the STE dictionary. |
| `technical_verbs` | Approved technical verbs for this project. |
| `preferred_terms` | Unambiguous 1:1 renames; safe-fixes may apply these. |
| `inflections` | Plural/tense forms the engine should treat as the same entry. |
| `preferred_term` | Optional canonical spelling for that entry. |
| `approved_meaning` | Single allowed sense; agents must not invent other senses. |

Keep glossaries **minimal**. Only add terms the project truly needs. Prefer
STE approved words when they already cover the meaning.

`preferred_terms` must be **1:1 and unambiguous** (same referent, no context
branching). Ambiguous mappings belong in agent rewrite judgment, not safe-fixes.

## Worked example

File: `glossaries/landing-gear.yaml`

```yaml
# Project terminology for landing-gear maintenance manuals.
# Unofficial STE checker profile — not an ASD publication.

name: landing-gear-maintenance

technical_nouns:
  - word: torque-link
    part_of_speech: noun
    status: technical_noun
    approved_meaning: The link that connects the landing gear oleo to the axle.
    inflections:
      - torque-links
    preferred_term: torque-link

  - word: oleo
    part_of_speech: noun
    status: technical_noun
    approved_meaning: The shock absorber strut of the landing gear.
    inflections:
      - oleos

  - word: bogie
    part_of_speech: noun
    status: technical_noun
    approved_meaning: The multi-wheel truck assembly of the main landing gear.
    inflections:
      - bogies

technical_verbs:
  - word: safeties
    part_of_speech: verb
    status: technical_verbs
    approved_meaning: Installs a safety device or lock to prevent unwanted movement.
    inflections:
      - safety
      - safetied
      - safetying
    preferred_term: safety

preferred_terms:
  utilize: use
  ensure: make sure
  torque link: torque-link
  shock strut: oleo
```

### How to use with MCP

```text
ste_check_text(
  text=<manual excerpt>,
  text_type="procedure",
  glossary="glossaries/landing-gear.yaml",
  output="json",
)

ste_apply_safe_fixes(
  text=<manual excerpt>,
  glossary="glossaries/landing-gear.yaml",
)
```

### Expected effect

- `torque-link` / `oleo` / `bogie` are accepted as technical nouns (not flagged as unapproved vocabulary solely for being absent from the base dictionary).
- `utilize` → `use` and similar `preferred_terms` entries are candidates for `ste_apply_safe_fixes`.
- Agent rewrites must keep the **approved_meaning** of glossary terms and must not substitute unrelated synonyms for safety-critical nouns.

## Authoring checklist

1. One profile per product family or manual set (`name` unique and stable).
2. Lemmas lowercase unless the term is a required mixed-case identifier.
3. List needed inflections; do not rely on guessing irregular forms.
4. Put only clear synonyms in `preferred_terms`.
5. Re-run `ste_check_text` after glossary edits—do not assume compliance without a recheck.
