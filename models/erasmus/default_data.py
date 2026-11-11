# -*- coding: utf-8 -*-
"""Issue #780 - the texts a new call or group mobility starts with (documents, checklist, questions,
commitment letter, selection criteria) are stored in every installed language, so each reader
sees them in theirs (the centre's Catalan, Spanish...) and not in that of whoever created the
record. Odoo stores a new text in the creator's language only; once the record exists, the lines
still holding a default text get the default's translations. A text the creator changed before
saving is kept as written."""


def installed_langs(env):
    return [code for code, _name in env['res.lang'].get_installed()]


def translate_default_value(record, field_name, build):
    """`record[field_name]` still holds the default `build(record)` returns: store that default in
    every installed language."""
    current = build(record)
    if not current or str(record[field_name] or '') != str(current):
        return
    defaults = {lang: build(record.with_context(lang=lang)) for lang in installed_langs(record.env)}
    # The language the default was written in (Odoo's `_` may take the user's when the context
    # has none).
    source_lang = next((lang for lang, value in defaults.items() if str(value) == str(current)), None)
    if not source_lang:
        return
    field = record._fields[field_name]
    if callable(field.translate):
        # HTML is translated term by term (paragraph, list item...): each term of the creator's
        # default maps to the same term of each language's default (its own one too: it may be
        # stored only as the source, under en_US).
        source = field.get_trans_terms(current)
        defaults = {lang: dict(zip(source, field.get_trans_terms(value))) for lang, value in defaults.items()}
    record.sudo().update_field_translations(field_name, defaults, source_lang=source_lang)


def translate_default_lines(lines, build):
    """`lines` were created (in any order, some perhaps changed or added by hand) from the
    `(0, 0, vals)` commands `build(model)` returns: each line still matching a default (by name,
    then instructions) gets that default's translatable texts in every installed language."""
    if not lines:
        return
    langs = installed_langs(lines.env)
    per_lang = {lang: [command[2] for command in build(lines.browse().with_context(lang=lang))] for lang in langs}
    pending = list(enumerate(command[2] for command in build(lines.browse())))
    translatable = [name for name, field in lines._fields.items() if field.translate and field.store]
    for line in lines:
        candidates = [(index, vals) for index, vals in pending if vals.get('name') == line.name]
        if not candidates:
            continue
        # Two defaults may share a name (one per project): the instructions tell them apart.
        description = line['description'] or False if 'description' in line._fields else False
        match = next((candidate for candidate in candidates
                      if (candidate[1].get('description') or False) == description), candidates[0])
        pending.remove(match)
        index, vals = match
        for name in translatable:
            if name in vals and (line[name] or False) == (vals[name] or False):
                line.sudo().update_field_translations(name, {lang: per_lang[lang][index][name] for lang in langs})
