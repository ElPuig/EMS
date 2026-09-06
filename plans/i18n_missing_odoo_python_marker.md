# i18n: missing `#. odoo-python` marker on Python-raised strings

**Status: current as of 2026-09-06.** Not started - this is a newly-found gap, discovered as a
side effect of the MP 3003/3004 duplicate-code work (see the `ems.subject`/`ems.study` code
reuse feature), not something anyone has started fixing yet.

## What's wrong

A `_("...")` string raised from Python (a `ValidationError`, an onchange warning, etc.) only
actually translates at runtime in this Odoo version if its `i18n/<lang>.po` entry carries a
`#. odoo-python` comment line, in addition to the usual `#. module: ems` one and the
`#: code:addons/ems/models/<path>.py:0` occurrence line. Odoo's `CodeTranslations.
_load_python_translations` (`odoo/tools/translate.py`) filters entries by
`PYTHON_TRANSLATION_COMMENT in row['comments']` (`PYTHON_TRANSLATION_COMMENT = 'odoo-python'`) -
an entry missing that marker is silently skipped, and the string renders in English for every
user regardless of their language, with **no error anywhere** (`./upgrade.sh` loads the `.po`
file cleanly; the string just never resolves).

**Not visible via psql** - this Odoo version no longer has an `ir_translation` table at all
(confirmed empirically 2026-09-06: `SELECT * FROM ir_translation` errors with "relation ...
does not exist"). Python-code translations live purely in an in-memory cache
(`CodeTranslations.python_translations`, keyed by `(module, lang)`) populated by re-reading the
module's own `i18n/<lang>.po` file the first time a translation for that `(module, lang)` pair
is requested in a given server process. The only way to actually prove one of these strings
translates is a functional test: create/call the record under `with_context(lang='ca_ES')` (or
`es_ES`) and assert on the translated text - see `tests/test_subject.py::
test_code_conflict_message_translates_to_catalan` and `tests/test_working_schedules_import_
wizard.py::test_continue_from_intro_unknown_subject_code_raises_translated_message_in_catalan`
for the pattern (both added this session, both initially failed with the raw English message
until the marker was added, which is how this gap was found in the first place).

## Scope

Measured on `i18n/ca_ES.po` (2026-09-06): of 559 `msgid` blocks that carry at least one
`#: code:...` occurrence, **115 are missing the `#. odoo-python` marker** - roughly a fifth of
every Python-raised translatable string in this module has silently never translated. One
confirmed concrete instance found by hand: `models/curriculum/outcome.py`'s
`_("The code must start as the subject's code.")` (`i18n/ca_ES.po` around line 7191) - the
block has `#. module: ems` and the right `#: code:...` occurrence, but no `#. odoo-python` line.
`es_ES.po` almost certainly has the same 115 (both files are generated/maintained together in
this project and were not spot-checked individually for this count).

## How to fix

For each of the 115 blocks (`ca_ES.po` and the matching one in `es_ES.po`): add a
`#. odoo-python` comment line right after the existing `#. module: ems` line, e.g.:

```diff
 #. module: ems
+#. odoo-python
 #: code:addons/ems/models/curriculum/outcome.py:0
 msgid "The code must start as the subject's code."
 msgstr "El codi ha de començar com el codi de l'assignatura."
```

A block whose occurrences mix a `code:` reference with `model:`/`model_terms:` ones (like
`ems.subject`'s own `"duplicated code!"`, fixed this session) still only needs the marker added
once - `PoFileReader` builds one shared `comments` string per PO entry, so the marker is picked
up regardless of which occurrence line it sits next to.

**Verify per-fix, don't trust the diff alone** - same reasoning as the field/`arch_db` i18n gap
this mirrors (see `feedback_i18n_export_cli_broken_for_field_translations` in memory): add (or
reuse) a functional test asserting the translated text under `with_context(lang='ca_ES')` (or
`es_ES`), and confirm it actually fails before the marker is added and passes after - a `.po`
diff that "looks right" is not proof the string resolves at runtime, exactly as happened twice
in this same session before the tests caught it.

## Suggested approach for whoever picks this up

A small Python script (not checked in - a scratchpad one-off) can enumerate the 115 msgid blocks
missing the marker in both `.po` files and insert it mechanically (same logic as the counting
snippet used to produce the "115" figure above: split each file on blank lines, find blocks
containing `#: code:` without `#. odoo-python`, insert the line). Mechanical insertion is safe
here since the fix is always the same one-line addition with no judgment call involved - unlike
the field/`arch_db` gap, there's no risk of misreading which reference a fix belongs to. Spot
functional-test a handful of the fixed strings afterwards (not all 115) to confirm the mechanism
itself works, the same way this session did for the two strings it actually needed.
