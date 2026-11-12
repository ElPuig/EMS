
from lxml import etree

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

from ..models.erasmus.application import (LANGUAGE_SCORES, LAST_MOBILITY_SCORES, SENIORITY_SCORES,
                                          STAFF_LANGUAGE_SCORES)

# Field labels as the review of 46.0 named them, as (model, field): Catalan, Spanish.
LABELS = {
    ('ems.erasmus.application', 'scoring_frozen_date'): ("Puntuació fixada el", "Puntuación fijada el"),
    ('ems.erasmus.application', 'ranking_result'): ("Resultat", "Resultado"),
    ('ems.erasmus.application', 'strike_count'): ("Amonestacions", "Amonestaciones"),
    ('ems.erasmus.application', 'strike_ids'): ("Amonestacions", "Amonestaciones"),
    ('ems.erasmus.call', 'staff_level_ids'): ("Poden sol·licitar", "Pueden solicitar"),
    ('ems.erasmus.call', 'panel_ids'): ("Comissió", "Comisión"),
    ('ems.erasmus.call.document', 'panel_visible'): ("La veu la comissió", "La ve la comisión"),
    ('ems.erasmus.group.draw', 'tied_count'): ("Empatats", "Empatados"),
    ('ems.erasmus.application.document', 'signature_progress'): ("Signatures", "Firmas"),
    ('ems.erasmus.mobility', 'commitment_signed_date'): ("Signada el", "Firmada el"),
    ('ems.erasmus.mobility', 'commitment_signed_by_id'): ("Per", "Por"),
    ('ems.erasmus.mobility', 'commitment_guardian_signed_date'): ("Signada el", "Firmada el"),
    ('ems.erasmus.mobility', 'commitment_guardian_signed_by_id'): ("Per", "Por"),
    ('ems.erasmus.group.mobility', 'teacher_places'): ("Places de docents", "Plazas de docentes"),
    ('ems.erasmus.group.mobility', 'registration_count'): ("Inscrits", "Inscritos"),
    ('ems.erasmus.offer', 'from_reserve'): ("A reserva", "A reserva"),
}
# The state of an application, feminine, and whose call it is: only these change, not the same
# English word elsewhere in EMS.
SELECTIONS = {
    ('ems.erasmus.application', 'state', 'submitted'): ("Enviada", "Enviada"),
    ('ems.erasmus.call', 'audience', 'student'): ("Alumnat", "Alumnado"),
}
# (view xmlid, field name, Catalan header) of the short list headers.
HEADERS = [
    ('view_erasmus_call_list', 'date_open', "Obertura"),
    ('view_erasmus_call_list', 'date_close', "Tancament"),
    ('view_erasmus_call_list', 'application_count', "Sol·licituds"),
    ('view_erasmus_call_list', 'course_id', "Curs de la convocatòria"),
    ('view_erasmus_mobility_list', 'preparation_complete', "A punt"),
    ('view_erasmus_mobility_list', 'return_complete', "Tornada"),
    ('view_erasmus_application_list', 'documents_to_review', "Per revisar"),
    ('view_erasmus_ranking_list', 'state', "Situació actual"),
    ('view_erasmus_staff_ranking_list', 'state', "Situació actual"),
    ('view_erasmus_group_mobility_list', 'group_ids', "Grups"),
    ('view_erasmus_group_mobility_list', 'selected_count', "Seleccionats"),
    ('view_erasmus_group_mobility_list', 'documents_missing', "Docs. pendents"),
    ('view_erasmus_group_mobility_list', 'documents_to_review', "Per revisar"),
    ('view_erasmus_economy_panel_list', 'call_year', "Any"),
    ('view_erasmus_economy_panel_list', 'grant_current', "Subvenció"),
    ('view_erasmus_payment_list', 'kind', "Tipus"),
    ('view_erasmus_payment_list', 'receipt_ids', "Justificant"),
    ('view_erasmus_diffusion_list', 'recipient_count', "Abast"),
    ('view_erasmus_diffusion_list', 'is_automatic', "Automàtica"),
    ('view_erasmus_quality_history_list', 'student_applicants', "Sol·l."),
    ('view_erasmus_quality_history_list', 'student_target', "Dest."),
    ('view_erasmus_quality_history_list', 'staff_applicants', "Prof. sol·l."),
    ('view_erasmus_quality_history_list', 'staff_target', "Prof. dest."),
    ('view_erasmus_quality_history_list', 'satisfaction', "Satisfacció"),
    ('view_erasmus_quality_history_list', 'satisfaction_count', "Respostes"),
    ('view_erasmus_support_rate_list', 'call_year', "Any"),
    ('view_erasmus_support_rate_list', 'band_from', "Des de"),
    ('view_erasmus_support_rate_list', 'band_to', "Fins a"),
    ('view_erasmus_support_rate_list', 'min_days', "Mín. dies"),
    ('view_erasmus_support_rate_list', 'amount', "Import"),
]


@tagged('post_install', '-at_install')
class TestErasmusLabels(TransactionCase):
    """Issue #779 - texts and names of the Erasmus+ screens. Only the words change: every key and
    every stored value stays."""

    def _arch(self, xmlid, lang='ca_ES'):
        view = self.env.ref(f'ems.{xmlid}').with_context(lang=lang)
        return etree.fromstring(view.arch_db)

    def test_field_labels(self):
        for (model, name), (catalan, spanish) in LABELS.items():
            for lang, label in (('ca_ES', catalan), ('es_ES', spanish)):
                string = self.env[model].with_context(lang=lang).fields_get([name])[name]['string']
                self.assertEqual(string, label, f"{model}.{name} in {lang}")

    def test_selection_labels(self):
        for (model, name, key), (catalan, spanish) in SELECTIONS.items():
            for lang, label in (('ca_ES', catalan), ('es_ES', spanish)):
                selection = dict(self.env[model].with_context(lang=lang).fields_get([name])[name]['selection'])
                self.assertEqual(selection[key], label, f"{model}.{name}.{key} in {lang}")

    def test_short_list_headers(self):
        for xmlid, name, header in HEADERS:
            nodes = self._arch(xmlid).xpath(f".//field[@name='{name}']")
            self.assertTrue(nodes, f"{xmlid}: {name}")
            string = nodes[0].get('string') or self.env[self.env.ref(f'ems.{xmlid}').model].with_context(
                lang='ca_ES').fields_get([name])[name]['string']
            self.assertEqual(string, header, f"{xmlid}: {name}")

    def test_no_tribunal_left(self):
        """The call's rules (art. 10) say Comissió: nothing in the screens says Tribunal any more."""
        for lang in ('ca_ES', 'es_ES'):
            records = self.env['ir.model.fields'].with_context(lang=lang).search([('model', '=like', 'ems.erasmus%')])
            for field in records:
                self.assertNotRegex(f"{field.field_description} {field.help or ''}", r'(?i)tribunal', field.name)
            views = self.env['ir.ui.view'].with_context(lang=lang).search([('model', '=like', 'ems.erasmus%')])
            for view in views:
                self.assertNotRegex(view.arch_db, r'(?i)tribunal', view.name)
            self.assertNotRegex(self.env.ref('ems.group_erasmus_panel').with_context(lang=lang).name, r'(?i)tribunal')

    def _maximums(self, xmlid):
        return {node.get('name'): safe_eval(node.get('options'))['max']
                for node in self._arch(xmlid, 'en_US').iter('field')
                if node.get('widget') == 'ems_score_out_of' and node.get('options')}

    def test_points_show_their_maximum(self):
        """The criteria of the student call add up to 100 and those of the staff call to 10, and a
        criterion's maximum is what the code can give."""
        maximums = self._maximums('view_erasmus_application_form')
        self.assertEqual(maximums['score_c'], max(LANGUAGE_SCORES.values()))
        self.assertEqual(sum(maximums[name] for name in ('score_a', 'score_b', 'score_c', 'score_d', 'score_e')), 100)
        self.assertEqual((maximums['interview_general'], maximums['interview_english']), (20, 15))
        self.assertEqual(maximums['score_last_mobility'], max(LAST_MOBILITY_SCORES.values()))
        self.assertEqual(maximums['score_staff_language'], max(STAFF_LANGUAGE_SCORES.values()))
        self.assertEqual(maximums['score_seniority'], max(SENIORITY_SCORES.values()))
        self.assertEqual(sum(maximums[name] for name in (
            'score_plan', 'score_last_mobility', 'score_projects', 'score_staff_language', 'score_seniority',
            'score_internationalisation')), 10)
