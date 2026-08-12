# -*- coding: utf-8 -*-

from unittest.mock import MagicMock, patch

from odoo.exceptions import RedirectWarning, UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, make_synchronous_run_in_thread


class TestLimesurveyHeaderCore(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TLM4', level={'name': 'Test LimeSurvey Header Level'}, study={
            'name': 'Test LimeSurvey Header Study',
        })
        cls.other_group = cls.env['ems.group'].create({'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.subject = cls.env['ems.subject'].create({'code': 'TLM4SUB', 'acronym': 'TLM4S', 'name': 'Test Subject'})

        cls.student = cls.env['res.partner'].create({
            'name': 'Header Test Student', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'level_id': cls.level.id, 'study_id': cls.study.id, 'student_email': 'porrino.fernando+student@example.com',
            'wpi_enrolled': False,
        })
        cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})

        cls.no_group_student = cls.env['res.partner'].create({
            'name': 'No Group Student', 'contact_type': 'student', 'level_id': cls.level.id,
        })

    def _header(self, **overrides):
        vals = {
            'name': 'test_header', 'title': 'Test Header', 'description': 'A test header',
            'target': 'students', 'tsv_raw_text': "col1\tcol2\n{'TITLE'}\t{'DESCRIPTION'}",
        }
        vals.update(overrides)
        return self.env['ems.limesurvey_header'].create(vals)

    # -- required fields -----------------------------------------------------

    def test_required_fields(self):
        with self.assertRaises(Exception):
            self.env['ems.limesurvey_header'].create({'title': 'T', 'description': 'D', 'target': 'students', 'tsv_raw_text': 'x'})

    def test_default_state_is_draft(self):
        header = self._header()
        self.assertEqual(header.state, 'draft')

    # -- onchange cascades ----------------------------------------------------

    def test_onchange_level_ids_narrows_study_ids(self):
        header = self._header(level_ids=[(6, 0, [self.level.id])], study_ids=[(6, 0, [self.study.id])])
        header._onchange_level_ids()
        self.assertIn(self.study, header.study_ids)

    def test_onchange_study_ids_narrows_group_ids(self):
        header = self._header(study_ids=[(6, 0, [self.study.id])], group_ids=[(6, 0, [self.group.id, self.other_group.id])])
        header._onchange_study_ids()
        self.assertIn(self.group, header.group_ids)
        self.assertIn(self.other_group, header.group_ids)

    # -- _compute_recipients_students / action_compute -------------------------

    def test_action_compute_builds_recipients_from_students(self):
        header = self._header(group_ids=[(6, 0, [self.group.id])])
        header.action_compute()

        self.assertEqual(header.state, 'computed')
        self.assertIn(self.student, header.limesurvey_recipient_ids.mapped('student_id'))
        recipient = header.limesurvey_recipient_ids.filtered(lambda r: r.student_id == self.student)
        self.assertEqual(recipient.email, 'porrino.fernando+student@example.com')
        self.assertEqual(len(recipient.limesurvey_enrollment_ids), 1)
        self.assertEqual(recipient.limesurvey_enrollment_ids.subject_id, self.subject)

    def test_action_compute_excludes_students_without_main_group(self):
        header = self._header(group_ids=[(6, 0, [self.group.id])])
        header.action_compute()
        self.assertNotIn(self.no_group_student, header.limesurvey_recipient_ids.mapped('student_id'))

    def test_action_compute_falls_back_to_generic_email(self):
        student = self.env['res.partner'].create({
            'name': 'Fallback Email Student', 'contact_type': 'student', 'main_group_id': self.group.id,
            'level_id': self.level.id, 'email': 'porrino.fernando+fallback@example.com',
        })
        header = self._header(group_ids=[(6, 0, [self.group.id])])
        header.action_compute()
        recipient = header.limesurvey_recipient_ids.filtered(lambda r: r.student_id == student)
        self.assertEqual(recipient.email, 'porrino.fernando+fallback@example.com')

    def test_action_reload_recomputes(self):
        header = self._header(group_ids=[(6, 0, [self.group.id])])
        header.action_compute()
        first_count = len(header.limesurvey_recipient_ids)
        header.action_reload()
        self.assertEqual(len(header.limesurvey_recipient_ids), first_count)

    def test_action_draft_removes_recipients(self):
        header = self._header(group_ids=[(6, 0, [self.group.id])])
        header.action_compute()
        self.assertTrue(header.limesurvey_recipient_ids)
        header.action_draft()
        self.assertEqual(header.state, 'draft')
        self.assertFalse(header.limesurvey_recipient_ids)

    def test_compute_recipients_teachers_not_implemented(self):
        # Regression: `raise NotImplemented(...)` used to crash with TypeError
        # ('NotImplementedType' object is not callable) instead of a clean
        # NotImplementedError - action_compute's own try/except still caught it
        # either way, but the notify message read as a confusing TypeError.
        header = self._header(target='teachers')
        header.action_compute()  # caught internally, notifies failure, doesn't re-raise
        self.assertNotEqual(header.state, 'computed')
        with self.assertRaises(NotImplementedError):
            header._compute_recipients_teachers()

    def test_compute_recipients_asp_not_implemented(self):
        header = self._header(target='asp')
        with self.assertRaises(NotImplementedError):
            header._compute_recipients_asp()

    # -- unlink -----------------------------------------------------------------

    def test_unlink_blocked_in_uploading_state(self):
        header = self._header(state='uploading')
        with self.assertRaises(UserError):
            header.unlink()

    def test_unlink_allowed_in_draft(self):
        header = self._header()
        header.unlink()
        self.assertFalse(header.exists())

    def test_unlink_closed_without_flag_redirects(self):
        header = self._header(state='closed')
        with self.assertRaises(RedirectWarning):
            header.unlink()

    def test_unlink_closed_with_flag_deletes(self):
        header = self._header(state='closed')
        header_id = header.id
        header.with_context(force_delete_closed=True).unlink()
        self.assertFalse(self.env['ems.limesurvey_header'].browse(header_id).exists())

    def test_unlink_with_uploaded_recipients_never_touches_real_api(self):
        # Recipients with an external_id make unlink() call LimesurveyApi.delete_survey()
        # synchronously (no threading here) - must be mocked, this must never reach the
        # real, production-connected LimeSurvey service.
        header = self._header(state='uploaded')
        self.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': header.id, 'name': 'R', 'email': 'porrino.fernando+r@example.com',
            'external_id': '999', 'state': 'uploaded',
        })

        with patch('odoo.addons.ems.models.communications.limesurvey.LimesurveyApi') as mock_api_cls:
            mock_instance = MagicMock()
            mock_api_cls.return_value = mock_instance
            header.unlink()

        mock_instance.delete_survey.assert_called_once_with('999')

    # -- misc ---------------------------------------------------------------

    def test_action_get_csv(self):
        header = self._header()
        header.csv_filename = 'test.csv'
        action = header.action_get_csv()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('test.csv', action['url'])

    def test_action_none_returns_true(self):
        header = self._header()
        self.assertTrue(header.action_none())

    def test_action_upload_never_touches_real_api(self):
        # Wires action_upload()'s compute() closure through run_action() -> run_in_thread();
        # both LimesurveyApi and run_in_thread are mocked, so nothing here can ever reach
        # the real, production-connected LimeSurvey service.
        header = self._header(group_ids=[(6, 0, [self.group.id])])
        header.action_compute()
        self.env.company.limesurvey_gid = 1

        with patch('odoo.addons.ems.models.communications.limesurvey.LimesurveyApi') as mock_api_cls, \
                patch.object(type(header), 'run_in_thread', side_effect=make_synchronous_run_in_thread(header), autospec=True):
            mock_instance = MagicMock()
            mock_instance.create_survey.return_value = '111'
            mock_instance.add_participants.return_value = [
                {'tid': 1, 'token': 'TOK', 'email': r.email} for r in header.limesurvey_recipient_ids
            ]
            mock_api_cls.return_value = mock_instance
            header.action_upload()

        self.assertEqual(header.state, 'uploaded')
        mock_instance.create_survey.assert_called()


class TestComputeSurveyData(TransactionCase):
    """Regression coverage for the teacher_name/teachers_names mix-up fixed in this pass:
    a special_subject_enrolled block used to reference an unrelated (or undefined) local
    variable instead of the teachers actually computed for the current subject enrollment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TLM5', level={'name': 'Test Compute Survey Data Level'}, study={
            'name': 'Test Compute Survey Data Study',
        })
        cls.subject = cls.env['ems.subject'].create({'code': 'TLM5SUB', 'acronym': 'TLM5S', 'name': 'Test Subject'})
        cls.teacher = cls.env['hr.employee'].create({'name': 'Jane Doe (Test Teacher)', 'employee_type': 'teacher'})
        cls.env['ems.teaching'].create({'teacher_id': cls.teacher.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})

        cls.student = cls.env['res.partner'].create({
            'name': 'Compute Survey Data Student', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'level_id': cls.level.id, 'study_id': cls.study.id,
        })

        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'compute_survey_data_test', 'title': 'Title', 'description': 'Description',
            'target': 'students', 'tsv_raw_text': "col\n{'TITLE'}",
        })
        cls.block = cls.env['ems.limesurvey_block'].create({
            'name': 'Subject block', 'limesurvey_header_id': cls.header.id,
            'tsv_raw_text': "col\n{'X'}\t{'TITLE'}",
            'special': True, 'special_type': 'subject', 'special_course_filter': 0,
        })
        cls.recipient = cls.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': cls.header.id, 'name': cls.student.name, 'email': 'porrino.fernando+compute@example.com',
            'level_id': cls.level.id, 'student_id': cls.student.id, 'state': 'pending',
        })
        cls.env['ems.limesurvey_enrollment'].create({
            'limesurvey_recipient_id': cls.recipient.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
        })

    def test_teacher_names_are_appended_to_subject_block_title(self):
        # A special_subject_enrolled block is the ONLY block on this header, so if
        # `teacher_name` (undefined at this point) were still referenced instead of the
        # freshly-computed `teachers_names`, this would raise UnboundLocalError.
        result = self.header.compute_survey_data(self.recipient, only_key=False)
        self.assertIn('Jane Doe (Test Teacher)', result['raw_tsv'])

    def test_only_key_mode_does_not_touch_content(self):
        result = self.header.compute_survey_data(self.recipient, only_key=True)
        self.assertIsNone(result['raw_tsv'])
        self.assertTrue(result['internal_id'])

    def test_special_type_wpi_appends_block_for_enrolled_student(self):
        # No prior coverage of the special_type='wpi' branch existed before the
        # special_wpi_enrolled/special_subject_enrolled -> special_type Selection fix
        # (2026-07-30, see docs/en/developers/communications/limesurvey.md).
        wpi_student = self.env['res.partner'].create({
            'name': 'WPI Student', 'contact_type': 'student', 'main_group_id': self.group.id,
            'level_id': self.level.id, 'study_id': self.study.id, 'wpi_enrolled': True,
        })
        wpi_block = self.env['ems.limesurvey_block'].create({
            'name': 'WPI block', 'limesurvey_header_id': self.header.id,
            'tsv_raw_text': "col\n{'TITLE'}",
            'special': True, 'special_type': 'wpi', 'special_course_filter': 0,
        })
        wpi_recipient = self.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': self.header.id, 'name': wpi_student.name,
            'email': 'porrino.fernando+wpi@example.com',
            'level_id': self.level.id, 'student_id': wpi_student.id, 'state': 'pending',
            # ems.limesurvey_recipient.wpi_enrolled is its own field, only populated from
            # the student at real recipient-creation time (fill_recipients_data) - must be
            # set explicitly here since this test creates the recipient directly.
            'wpi_enrolled': True,
        })
        result = self.header.compute_survey_data(wpi_recipient, only_key=False)
        self.assertIn(wpi_block.name, result['raw_tsv'])
