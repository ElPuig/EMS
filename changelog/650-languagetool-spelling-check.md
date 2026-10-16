# Internal changes

## Spelling and grammar check for Catalan and Spanish texts (LanguageTool):

- New `scripts/i18n/lt_check.py`: checks the Catalan and Spanish user manuals (`docs/{ca,es}/`, markdown-aware) and translations (`i18n/{ca,es}_ES.po`, `msgstr` only) with the LanguageTool Premium API. `--since <ref>` reports only what changed since a git ref, `--text` checks loose text (newsletter, slides). Project ignore list for acronyms in `scripts/i18n/lt_ignore.txt`.
- Personal credentials outside the repo (`~/.claude/languagetool.json`); without them the script exits cleanly, so nobody without a key is blocked.
- CLAUDE.md: Catalan/Spanish text is checked before being handed over, job titles go in lowercase (IEC norm), and the release close review checks every ca/es text changed since the last release. Developer doc: `docs/en/developers/tooling/languagetool.md`.
- Triggered by "Vaig a faltar" (should be "Faltaré") in the guard-duty videos; fixing the existing texts is issue #651.
