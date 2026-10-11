# Changes:

## Convalidations: the list opens on what waits for each role:
- Academic management > Convalidations now opens with a single "Pending for me" filter instead of every state waiting for the centre: the Head of Studies and their Deputy see the requests pending their review and those in process at the Ministry, the Director those pending their resolution, and the secretariat those pending registration (developer's decision, 2026-10-11). The administrator, and anybody holding several of those roles, sees the sum. Requests waiting for the applicant's documentation are nobody's and keep their own filter, like every other state; removing "Pending for me" shows them all.
- New non-stored, searchable `ems.convalidation.is_pending_for_me` (`@api.depends_context('uid')`), resolved by `_ems_states_pending_for_user()`. The Director's group implies the Head of Studies' one, but the Director only gets their own step.
- Backend tests in TestConvalidation (each role, the administrator and several roles, negation), new tour `ems_convalidation_default_filter` as the secretariat, ca/es translations, Head of Studies and secretariat manuals (3 languages) and developer doc updated.
