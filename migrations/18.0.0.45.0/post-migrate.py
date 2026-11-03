def migrate(cr, version):
    _follow_ups_in_the_centre_language(cr)


def _follow_ups_in_the_centre_language(cr):
    """Issue #743: the follow-up EMS writes on its own when a minute reviews an agreement with
    nothing written about it was stored in the language of whoever reviewed it. Rewritten in
    Catalan, the centre's language, only where the text is exactly the automatic one. A clean
    install has no follow-up, so it needs no post_init_hook counterpart."""
    cr.execute(r"""
        UPDATE ems_quality_followup
           SET description = regexp_replace(description,
                   '^(?:Revisado en la reunión|Reviewed in the meeting) (\S+)\.$', 'Revisat a la reunió \1.')
         WHERE description ~ '^(?:Revisado en la reunión|Reviewed in the meeting) \S+\.$'
    """)
