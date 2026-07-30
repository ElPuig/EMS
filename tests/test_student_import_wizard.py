import base64

from odoo.tests.common import TransactionCase


class TestStudentImportWizard(TransactionCase):
    """Focused coverage for _get_or_create_student: the dedup/reactivation
    logic touched by the archive-on-withdrawal change, not a full xlsx
    column-mapping suite (see action_import / _process_row for that)."""

    def _wizard(self):
        return self.env['ems.student_import_wizard'].create({
            'file': base64.b64encode(b'placeholder'), 'file_name': 'esfera.xlsx',
        })

    def test_creates_new_student(self):
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        student = wizard._get_or_create_student('8000001', {
            'name': 'Brand New', 'contact_type': 'student',
            'student_id': '8000001', 'active': True,
        }, stats)
        self.assertEqual(student.name, 'Brand New')
        self.assertTrue(student.active)
        self.assertEqual(stats['created'], 1)

    def test_updates_existing_student(self):
        existing = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'student', 'student_id': '8000002'})
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        student = wizard._get_or_create_student('8000002', {
            'name': 'New Name', 'contact_type': 'student',
            'student_id': '8000002', 'active': True,
        }, stats)
        self.assertEqual(student, existing)
        self.assertEqual(student.name, 'New Name')
        self.assertEqual(stats['updated'], 1)

    def test_reactivates_archived_withdrawal_instead_of_duplicating(self):
        # A withdrawal is archived (active=False) as part of the exit, mirroring
        # hr.employee. Re-importing the same RALC must find and reactivate that
        # record, not silently create a duplicate partner.
        withdrawn = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'withdrawal', 'student_id': '8000003'})
        withdrawn.write({'active': False})
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        student = wizard._get_or_create_student('8000003', {
            'name': 'New Name', 'contact_type': 'student',
            'student_id': '8000003', 'active': True,
        }, stats)
        self.assertEqual(student, withdrawn)
        self.assertTrue(student.active)
        self.assertEqual(student.contact_type, 'student')
        self.assertEqual(stats['updated'], 1)
        matches = self.env['res.partner'].with_context(active_test=False).search(
            [('student_id', '=', '8000003')])
        self.assertEqual(len(matches), 1)
