# -*- coding: utf-8 -*-

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
