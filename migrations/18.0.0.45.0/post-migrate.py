from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_centre_lang(env)
    _follow_ups_in_the_centre_language(cr)


def _seed_centre_lang(env):
    """Issue #746: Catalan as the centre language of an installation that had none, and as the
    default language of its new contacts and users. The same step post_init_hook runs on install."""
    env['res.company']._ems_seed_centre_lang()


def _follow_ups_in_the_centre_language(cr):
    """Issue #743: the follow-up EMS writes on its own when a minute reviews an agreement with
    nothing written about it was stored in the language of whoever reviewed it. Rewritten in
    Catalan, the centre language _seed_centre_lang() has just set, only where the text is exactly
    the automatic one. A clean install has no follow-up, so it needs no post_init_hook counterpart."""
    cr.execute(r"""
        UPDATE ems_quality_followup
           SET description = regexp_replace(description,
                   '^(?:Revisado en la reunión|Reviewed in the meeting) (\S+)\.$', 'Revisat a la reunió \1.')
         WHERE description ~ '^(?:Revisado en la reunión|Reviewed in the meeting) \S+\.$'
    """)
