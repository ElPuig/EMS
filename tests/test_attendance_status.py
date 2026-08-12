# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestAttendanceStatus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Attendance Status)', 'login': 'test_admin_astatus',
            'email': 'test_admin_astatus@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Attendance Status)', 'login': 'test_teacher_astatus',
            'email': 'test_teacher_astatus@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.status_attended = cls.env.ref('ems.attendance_status_attended')
        cls.status_delayed = cls.env.ref('ems.attendance_status_delayed')
        cls.status_miss = cls.env.ref('ems.attendance_status_miss')
        cls.status_justified = cls.env.ref('ems.attendance_status_justified')
        cls.status_issue = cls.env.ref('ems.attendance_status_issue')

    # --- seed data -----------------------------------------------------

    def test_seed_statuses_exist_with_expected_shape(self):
        self.assertEqual(self.status_attended.category, 'assistance')
        self.assertEqual(self.status_delayed.category, 'assistance')
        self.assertEqual(self.status_miss.category, 'absence')
        self.assertEqual(self.status_justified.category, 'absence')
        # 'Issue' kept the historical 'a_'-prefix categorisation (counted as
        # assistance) even though it now lives on ems.strike conceptually - only its
        # active flag changed, not its reporting behaviour, to avoid silently
        # changing historical report numbers.
        self.assertEqual(self.status_issue.category, 'assistance')

        self.assertTrue(self.status_miss.notifiable)
        self.assertTrue(self.status_issue.notifiable)
        self.assertFalse(self.status_attended.notifiable)
        self.assertFalse(self.status_delayed.notifiable)
        self.assertFalse(self.status_justified.notifiable)

    def test_issue_status_is_archived(self):
        self.assertFalse(self.status_issue.active)

    def test_archived_issue_not_in_default_search(self):
        found = self.env['ems.attendance_status'].search([('id', '=', self.status_issue.id)])
        self.assertFalse(found)
        found_all = self.env['ems.attendance_status'].with_context(active_test=False).search(
            [('id', '=', self.status_issue.id)]
        )
        self.assertIn(self.status_issue, found_all)

    def test_session_line_referencing_archived_issue_still_reads_correctly(self):
        # This is the scenario a production upgrade actually produces: an existing
        # ems.attendance_session_line row whose old 'status' string was 'a_issue' gets
        # migrated to point at this now-archived record (see the post-migrate backfill
        # in migrations/18.0.0.22.0/). A Many2one pointing at an archived record is a
        # perfectly valid, permanent reference in Odoo - active=False only removes it
        # from default searches and new-selection dropdowns, it does not affect reads
        # of an already-set field. Confirms that directly, rather than just asserting it.
        student = self.env['res.partner'].create({
            'name': 'Test Student (Archived Issue Reference)', 'contact_type': 'student',
        })
        line = self.env['ems.attendance_session_line'].create({
            'student_id': student.id, 'status_id': self.status_issue.id,
        })
        self.assertEqual(line.status_id, self.status_issue)
        self.assertEqual(line.status_id.name, 'Issue')
        self.assertFalse(line.status_id.active)
        # Reports deliberately search with active_test=False (attendance_reports.py's
        # _report_data) specifically so historical 'Issue' entries still get a legend
        # label instead of showing blank - confirm that lookup still resolves this row.
        statuses = self.env['ems.attendance_status'].with_context(active_test=False).search([])
        self.assertIn(self.status_issue, statuses)

    # --- model behaviour -------------------------------------------------

    def test_create_valid_status(self):
        status = self.env['ems.attendance_status'].with_user(self.admin_user).create({
            'name': 'Test Custom Status', 'category': 'absence',
        })
        self.assertEqual(status.name, 'Test Custom Status')
        self.assertTrue(status.active)

    def test_category_required(self):
        with self.assertRaises(Exception):
            self.env['ems.attendance_status'].with_user(self.admin_user).create({'name': 'No category'})

    def test_color_must_be_hex(self):
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_status'].with_user(self.admin_user).create({
                'name': 'Bad color', 'category': 'absence', 'color': 'not-a-hex-color',
            })

    def test_teacher_can_read_but_not_write(self):
        status = self.env['ems.attendance_status'].with_user(self.teacher_user).browse(self.status_attended.id)
        self.assertEqual(status.name, 'Attended')
        with self.assertRaises(AccessError):
            status.write({'name': 'Should not be allowed'})

    # --- integration with ems.attendance_session_line ---------------------

    def test_session_line_defaults_to_attended(self):
        student = self.env['res.partner'].create({'name': 'Test Student (Attendance Status)', 'contact_type': 'student'})
        line = self.env['ems.attendance_session_line'].create({'student_id': student.id})
        self.assertEqual(line.status_id, self.status_attended)

    def test_status_is_notificable_reads_from_model(self):
        student = self.env['res.partner'].create({'name': 'Test Student 2 (Attendance Status)', 'contact_type': 'student'})
        attended_line = self.env['ems.attendance_session_line'].create({
            'student_id': student.id, 'status_id': self.status_attended.id,
        })
        miss_line = self.env['ems.attendance_session_line'].create({
            'student_id': student.id, 'status_id': self.status_miss.id,
        })
        self.assertFalse(attended_line.status_is_notificable())
        self.assertTrue(miss_line.status_is_notificable())
