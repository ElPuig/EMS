from datetime import timedelta

from odoo import fields
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus import create_erasmus_fixtures
from .test_erasmus_group_mobility import create_group_mobility_fixtures
from .test_erasmus_mobility import ErasmusMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusDefaultData(TransactionCase):
    """Issue #780 - what a new call or group mobility starts with is stored in Catalan, Spanish and
    English, whoever creates it; a text changed before saving stays as written; the staff call's
    names and its optional step."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_default_data_technician', lang='es_ES')
        cls.Call = cls.env['ems.erasmus.call'].with_user(cls.technician)
        now = fields.Datetime.now()
        cls.dates = {'date_open': now - timedelta(days=1), 'date_close': now + timedelta(days=10)}

    def _in(self, records, lang, field='name'):
        return records.with_context(lang=lang).mapped(field)

    def _new_call(self, audience='student', **values):
        return self.Call.create({'name': f'Test default data {audience}', 'audience': audience, **self.dates,
                                 **values})

    def test_a_students_call_starts_in_every_language(self):
        """Created by a Spanish-speaking technician: Catalan and English readers see theirs too."""
        call = self._new_call()
        documents = call.preparation_document_ids
        self.assertIn("Certificat de l'OLS", self._in(documents, 'ca_ES'))
        self.assertIn("Certificado del OLS", self._in(documents, 'es_ES'))
        self.assertIn("OLS certificate", self._in(documents, 'en_US'))
        ols = documents.filtered(lambda line: line.with_context(lang='en_US').name == "OLS certificate")
        self.assertNotEqual(ols.with_context(lang='ca_ES').description, ols.with_context(lang='en_US').description)
        self.assertIn("Sessions de preparació", self._in(call.task_ids, 'ca_ES'))
        self.assertIn("Què has fet aquesta setmana?", self._in(call.self_assessment_question_ids, 'ca_ES'))
        self.assertIn("CV Europass en anglès", self._in(call.document_ids, 'ca_ES'))
        self.assertIn("Lliurar la documentació de viatge", call.with_context(lang='ca_ES').commitment_text)
        self.assertIn("Entregar la documentación de viaje", call.with_context(lang='es_ES').commitment_text)
        self.assertIn("Hand in the travel documents", call.with_context(lang='en_US').commitment_text)

    def test_the_form_defaults_are_translated_too_and_a_changed_text_is_kept(self):
        """The form shows the defaults before saving: a line renamed there keeps its new name in
        every language (Odoo's own fallback), the others get their translations."""
        form = Form(self.Call)
        form.name = 'Test default data form'
        form.date_open, form.date_close = self.dates['date_open'], self.dates['date_close']
        with form.document_ids.edit(0) as document:
            document.name = "CV propi"
        call = form.save()
        documents = call.document_ids.sorted('sequence')
        self.assertEqual({*self._in(documents[:1], 'ca_ES'), *self._in(documents[:1], 'en_US')}, {"CV propi"})
        for lang in ('ca_ES', 'es_ES', 'en_US'):
            expected = [vals['name'] for _c, _i, vals in call.with_context(lang=lang)._ems_student_documents()]
            self.assertEqual(self._in(documents[1:], lang), expected[1:])

    def test_a_staff_call_starts_translated_and_sharing_is_optional(self):
        call = self._new_call('staff')
        self.assertEqual(self._in(call.modality_ids, 'ca_ES'), ["Personal d'FP (KA121-VET)", "Personal d'educació superior (KA131-HED)"])
        self.assertEqual(call.modality_ids.mapped('project'), ['ka121_vet', 'ka131_hed'])
        tasks = call.task_ids.with_context(lang='en_US')
        self.assertEqual(tasks[:1].name, "Preparation sessions")
        share = tasks.filtered(lambda task: task.name.startswith("Share it"))
        self.assertEqual(share.requirement, 'optional')
        self.assertEqual((tasks - share).mapped('requirement'), ['required'] * 3)
        self.assertIn("Certificats de llengües", self._in(call.document_ids, 'ca_ES'))

    def test_a_copied_call_keeps_the_translations(self):
        copy = self._new_call().copy()
        self.assertIn("Certificat de l'OLS", self._in(copy.preparation_document_ids, 'ca_ES'))
        self.assertIn("Certificado del OLS", self._in(copy.preparation_document_ids, 'es_ES'))


@tagged('post_install', '-at_install')
class TestErasmusGroupDefaultData(TransactionCase):
    """Issue #780 (9.6) - a group mobility's selection criteria and documents in every language."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_group_mobility_fixtures(cls)

    def test_the_selection_criteria_and_documents_are_in_every_language(self):
        mobility = self.mobility
        self.assertTrue(mobility.with_context(lang='ca_ES').tie_break.startswith("Inscrit dins del termini"))
        self.assertTrue(mobility.with_context(lang='es_ES').tie_break.startswith("Inscrito dentro del plazo"))
        self.assertTrue(mobility.with_context(lang='en_US').tie_break.startswith("Enrolled within the period"))
        self.assertIn("Pòlissa d'assegurança col·lectiva",
                      mobility.requirement_ids.with_context(lang='ca_ES').mapped('name'))
        self.assertIn("Póliza de seguro colectiva", mobility.requirement_ids.with_context(lang='es_ES').mapped('name'))


@tagged('post_install', '-at_install')
class TestErasmusOptionalStep(ErasmusMobilityCase):
    """Issue #780 (6.6) - an optional step is listed but never holds a mobility back."""

    def test_an_optional_step_is_not_required(self):
        optional, required = self.env['ems.erasmus.call.task'].create([
            {'call_id': self.call.id, 'name': 'Test optional step', 'stage': 'return', 'requirement': 'optional'},
            {'call_id': self.call.id, 'name': 'Test required step', 'stage': 'return'}])
        mobility, _second = self._accepted()
        steps = mobility.task_ids
        self.assertEqual(steps.filtered(lambda task: task.call_task_id == optional).is_required, False)
        self.assertEqual(steps.filtered(lambda task: task.call_task_id == required).is_required, True)
        # Everything of the return done except the optional step: the return is complete.
        self._complete_stage(mobility, 'return')
        steps.filtered(lambda task: task.call_task_id == optional).done = False
        self.assertTrue(mobility.return_complete)
