from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestErasmusJourneyReview(TransactionCase):
    """Issue #824 - fixes from the journey review of batches 5-9."""

    def test_portal_step_counter_is_translated(self):
        """A06m: "Step 6 of 8" read in English on the mobile portal (its "of" had no translation)."""
        view = self.env.ref('ems.portal_erasmus_progress')
        for lang, step, of in (('ca_ES', 'Pas', 'de'), ('es_ES', 'Paso', 'de')):
            if not self.env['res.lang']._lang_get(lang):
                continue
            arch = view.with_context(lang=lang).arch_db
            self.assertIn(f'>{step} <t', arch)
            self.assertIn(f'/> {of} <t', arch)

    def test_last_call_phase_says_places_assigned(self):
        """C23: the last phase only means no offer waits for an answer."""
        labels = dict(self.env['ems.erasmus.call'].with_context(lang='en_US')._fields['phase']._description_selection(
            self.env(context={'lang': 'en_US'})))
        self.assertEqual(labels['finished'], "Places assigned")
