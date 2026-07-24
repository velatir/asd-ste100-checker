# ASD-STE100 dictionary data

Unofficial curated extracts from **ASD-STE100 Issue 9**. This project is not
affiliated with, endorsed by, or sponsored by ASD. ASD-STE100 is a registered
European Union Trade Mark (No. 017966390).

## Committed files

| File | Purpose |
|------|---------|
| `dictionary.json` | Curated headwords (`DictionaryRecord` schema) |
| `rules.json` | Writing-rule metadata (`RuleMeta` schema) |
| `ambiguous.md` | Unresolved parser edge cases for human review |
| `seed_technical_nouns.json` | Rule 1.5 TN gap-fill for procedure examples |
| `seed_technical_verbs.json` | Rule 1.12 TV gap-fill for common tech verbs |

## Quality notes (v0.4 audit)

Official Issue 9 advertises roughly **~875 approved** and **~1274 unapproved**
headwords. The heuristic curator currently yields about **851 approved** and
**1301 unapproved** (**2152** total). Drivers of the remaining delta:

- **Empty / section-break pages** in the alpha range (no extractable entries).
- **Phrase / multi-line heads** occasionally skipped when POS cannot be resolved.
- **Technical nouns/verbs** live in category lists rather than the alpha dictionary;
  those are supplied via seed files at load time (not double-counted in
  `dictionary.json` totals).
- **Alternatives**: unapproved entries without an ALTERNATIVES column now fall
  back to STE vs Non-STE example diffs; a small residue still has empty
  `alternatives` when examples do not align.

Spelled cardinals (`four`, `twenty`, …) are treated as non-vocabulary tokens so
STE examples that mix words and digits do not flood false positives.

## Regenerate from the PDF

Requires the local PDF at the repo root (`ASD-STE100-ISSUE-9.pdf`) and the
project venv (with `pymupdf`).

```bash
source .venv/bin/activate

# 1) Dump raw section text under data/raw/ (gitignored)
python -m ste100.dictionary.extract \
  --pdf ASD-STE100-ISSUE-9.pdf \
  --out-dir ste100/dictionary/data/raw

# 2) Heuristic curation -> dictionary.json + rules.json + ambiguous.md
python -m ste100.dictionary.curate \
  --pdf ASD-STE100-ISSUE-9.pdf
```

Optional: if `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set, the curator notes
API availability; the committed data is produced by the deterministic parser.

Raw dumps under `data/raw/` are gitignored because they are large. Re-run the
commands above after updating the PDF issue.
