import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged
from odoo.tools import misc

from .common import create_role_user
from .test_erasmus_records import ErasmusRecordsCase


class ErasmusSignatureCase(ErasmusRecordsCase):
    """Documents signed electronically with sign_oca: the grant agreement's template has a box for
    the participant, the Director and the legal guardian (the student is an adult)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with misc.file_open('sign_oca/tests/empty.pdf', 'rb') as pdf:
            cls.pdf = pdf.read()
        cls.director_user = create_role_user(cls, 'director', 'test_erasmus_sign_director',
                                             email='director@example.com')
        cls.env.ref('ems.group_director').users = cls.director_user
        cls.technician_user.email = 'erasmus.technician@example.com'  # sign_oca's sender
        cls.template = cls.env['sign.oca.template'].create(
            {'name': 'Grant agreement (Annex 6)', 'data': base64.b64encode(cls.pdf), 'filename': 'annex6.pdf'})
        for index, signer in enumerate(('participant', 'director', 'guardian'), 1):
            cls.template.add_item({'field_id': cls.env.ref('sign_oca.sign_field_name').id,
                                   'role_id': cls.env.ref(f'ems.sign_role_erasmus_{signer}').id, 'page': 1,
                                   'position_x': 10.0 * index, 'position_y': 80.0, 'width': 20.0, 'height': 5.0,
                                   'required': True})

    def _agreement(self):
        first, _second = self._on_project()
        agreement = self._line(first, 'Grant agreement')
        agreement.call_document_id.sign_template_id = self.template
        agreement.prepared_attachment_ids = self.env['ir.attachment'].create(
            {'name': 'agreement_filled.pdf', 'raw': self.pdf, 'mimetype': 'application/pdf'})
        return first, agreement


@tagged('post_install', '-at_install')
class TestErasmusSignature(ErasmusSignatureCase):

    def _sign(self, signer):
        """What the signer's page sends: every box of their role, filled in."""
        items = signer.sudo().get_info()['items']
        values = {key: {**item, 'value': 'Signed'} for key, item in items.items()}
        signer.sudo().action_sign(values)

    def test_the_team_prepares_the_request_with_whoever_still_signs(self):
        first, agreement = self._agreement()
        self.assertTrue(agreement.can_send_to_sign)
        with self.assertRaises(AccessError):
            agreement.with_user(self.hos_user).action_send_to_sign()
        action = agreement.with_user(self.technician_user).action_send_to_sign()
        request = agreement.sudo().sign_request_id
        self.assertEqual((action['res_model'], action['res_id']), ('sign.oca.request', request.id))
        self.assertEqual(request.state, '1_draft', "The team checks it before sending it.")
        self.assertEqual(request.record_ref, agreement)
        self.assertEqual(base64.b64decode(request.data), self.pdf, "The filled-in copy, not the template's.")
        signers = {signer.role_id.ems_signer: signer.partner_id for signer in request.signer_ids}
        self.assertEqual(signers, {'participant': first.partner_id, 'director': self.director_user.partner_id})
        roles = {item['role_id'] for item in request.signatory_data.values()}
        self.assertNotIn(self.env.ref('ems.sign_role_erasmus_guardian').id, roles, "No guardian for an adult.")
        again = agreement.with_user(self.technician_user).action_send_to_sign()
        self.assertEqual(again['res_id'], request.id, "The open request, not a new one.")

    def test_what_is_missing_to_send_it_is_listed(self):
        _first, agreement = self._agreement()
        self.director_user.partner_id.email = False
        with self.assertRaisesRegex(UserError, 'Director'):
            agreement.with_user(self.technician_user).action_send_to_sign()
        self.director_user.partner_id.email = 'director@example.com'
        self.template.item_ids.filtered(
            lambda item: item.role_id.ems_signer == 'director').role_id = self.env.ref('sign_oca.sign_role_customer')
        with self.assertRaises(UserError, msg="A box of a role that is not an Erasmus+ signer."):
            agreement.with_user(self.technician_user).action_send_to_sign()

    def test_signing_ticks_each_signature_and_keeps_the_signed_copy(self):
        first, agreement = self._agreement()
        agreement.with_user(self.technician_user).action_send_to_sign()
        request = agreement.sudo().sign_request_id
        request.with_user(self.technician_user).action_send()
        participant = request.signer_ids.filtered(lambda signer: signer.role_id.ems_signer == 'participant')
        self.assertEqual(agreement._ems_portal_sign_url(first.partner_id), participant.access_url)
        self._sign(participant)
        self.assertFalse(agreement._ems_portal_sign_url(first.partner_id), "Already signed.")
        signature = agreement.sudo().signature_ids.filtered(lambda line: line.signer == 'participant')
        self.assertTrue(signature.signed)
        self.assertEqual(signature.sign_signer_id, participant)
        self.assertEqual(agreement.signatures_missing, 'Director')
        self.assertFalse(agreement.attachment_ids, "Not signed by everybody yet.")
        with self.assertRaises(UserError):
            signature.with_user(self.technician_user).write({'signed': False})
        self._sign(request.signer_ids - participant)
        self.assertEqual(request.state, '2_signed')
        self.assertFalse(agreement.signatures_missing)
        self.assertEqual(agreement.attachment_ids.mapped('name'), ['agreement_filled - signed.pdf'])
        self.assertEqual(agreement.file_state, 'to_review', "The team still reviews it.")
        self.assertIn('signed electronically', ' '.join(first.message_ids.mapped('body')))
        agreement.with_user(self.technician_user).action_mark_valid()
        self.assertEqual(agreement.file_state, 'complete')
        self.assertFalse(agreement.can_send_to_sign)

    def test_a_document_without_template_is_signed_outside(self):
        first, _second = self._on_project()
        agreement = self._line(first, 'Grant agreement')
        self.assertFalse(agreement.can_send_to_sign)
        with self.assertRaises(UserError):
            agreement.with_user(self.technician_user).action_send_to_sign()
