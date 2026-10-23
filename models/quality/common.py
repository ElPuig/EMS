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


# The language a department's or workgroup's name is read in to build the codes of its minutes
# and agreements. The centre works in Catalan; reading it in whatever language each user has
# would number the same department under several codes. To become a setting of the installation
# (issue #620), along with an acronym of its own for each department.
SCOPE_CODE_LANG = 'ca_ES'
_SCOPE_CODE_STOPWORDS = {'i', 'de', 'del', 'dels', 'la', 'el', 'les', 'els', 'a', 'y', 'and', 'of', 'the'}


def scope_code(record):
    """The short code a department or a workgroup gives to what is numbered under it.

    Its own `code` when the model has one; otherwise built from its name, without accents: the
    first five letters of a one-word name (Informàtica -> INFOR), and the first three of the first
    and of the last word of a longer one (Llengua Catalana -> LLECAT), which keeps two
    departments that start alike apart."""
    record = record.with_context(lang=SCOPE_CODE_LANG)
    code = getattr(record, 'code', False)
    if code:
        return code.upper()
    name = unicodedata.normalize('NFKD', record.name or '').encode('ascii', 'ignore').decode()
    words = [re.sub(r"^[dlDL]'", '', word) for word in re.split(r"[^A-Za-z0-9']+", name) if word]
    words = [word for word in words if word.lower() not in _SCOPE_CODE_STOPWORDS] or words
    if not words:
        return ""
    return (words[0][:5] if len(words) == 1 else words[0][:3] + words[-1][:3]).upper()
