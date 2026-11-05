# -*- coding: utf-8 -*-

import re
import unicodedata

from odoo import _

# The five stages the centre already uses in its own registries, in order. Shared by every
# model whose state is derived from its follow-up entries (actions now, records in phase 3),
# so the vocabulary cannot drift between them.
QUALITY_STATES = [
    ('new', "New (pending)"),
    ('analysed', "Analysed (planning)"),
    ('in_progress', "In progress (implementation)"),
    ('review', "Review (measuring efficacy)"),
    ('closed', "Closed"),
]

QUALITY_STATE_CLOSED = 'closed'


def quality_state_selection():
    """Translatable copy of QUALITY_STATES, for use as a Selection field's own list."""
    return [(key, _(label)) for key, label in QUALITY_STATES]


_SCOPE_CODE_STOPWORDS = {'i', 'de', 'del', 'dels', 'la', 'el', 'les', 'els', 'a', 'y', 'and', 'of', 'the'}


def scope_code(record):
    """The short code a department or a workgroup gives to what is numbered under it.

    Its own `code` when the model has one; otherwise built from its name, without accents: the
    first five letters of a one-word name (Informàtica -> INFOR), and the first three of the first
    and of the last word of a longer one (Llengua Catalana -> LLECAT), which keeps two
    departments that start alike apart. Read in the centre language (res.company.ems_lang): in
    whatever language each user has, the same department would be numbered under several codes."""
    record = record.with_env(record.env['res.company']._ems_centre_env())
    code = getattr(record, 'code', False)
    if code:
        return code.upper()
    name = unicodedata.normalize('NFKD', record.name or '').encode('ascii', 'ignore').decode()
    words = [re.sub(r"^[dlDL]'", '', word) for word in re.split(r"[^A-Za-z0-9']+", name) if word]
    words = [word for word in words if word.lower() not in _SCOPE_CODE_STOPWORDS] or words
    if not words:
        return ""
    return (words[0][:5] if len(words) == 1 else words[0][:3] + words[-1][:3]).upper()
