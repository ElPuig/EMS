# -*- coding: utf-8 -*-

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

from .common import create_level_study_group, make_synchronous_run_in_thread


class TestLimesurveyBlock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'block_test_header', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\n{'TITLE'}",
        })

    def _block(self, **overrides):
        vals = {'name': 'Block', 'tsv_raw_text': 'col\nval', 'limesurvey_header_id': self.header.id}
        vals.update(overrides)
        return self.env['ems.limesurvey_block'].create(vals)

    def test_special_type_selection_is_exclusive_by_construction(self):
        # Fixed 2026-07-30 (see docs/en/developers/communications/limesurvey.md): the old
        # special_wpi_enrolled/special_subject_enrolled Boolean pair relied on an asymmetric
        # onchange to stay mutually exclusive (only worked in one direction). Replaced with a
        # single Selection field, which can only ever hold one value - no onchange needed, and
        # there is no asymmetry left to test.
        block = self._block(special=True, special_type='wpi')
        self.assertEqual(block.special_type, 'wpi')
        block.special_type = 'subject'
        self.assertEqual(block.special_type, 'subject')


class TestLimesurveyRecipient(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TLM6', level={'name': 'Test LimeSurvey Recipient Level'}, study={
            'name': 'Test LimeSurvey Recipient Study',
        })
        cls.subject = cls.env['ems.subject'].create({'code': 'TLM6SUB', 'acronym': 'TLM6S', 'name': 'Test Subject'})
        cls.student = cls.env['res.partner'].create({
            'name': 'Recipient Test Student', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'level_id': cls.level.id, 'study_id': cls.study.id, 'student_email': 'porrino.fernando+recipient@example.com',
        })
        cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})

        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'recipient_test_header', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\n{'TITLE'}",
        })

    def _recipient(self, **overrides):
        vals = {
            'limesurvey_header_id': self.header.id, 'name': 'Manual recipient',
            'email': 'porrino.fernando+manual@example.com', 'state': 'pending',
        }
        vals.update(overrides)
        return self.env['ems.limesurvey_recipient'].create(vals)

    # -- action_restore ---------------------------------------------------------

    def test_action_restore_copies_student_data_and_enrollments(self):
        recipient = self._recipient(student_id=self.student.id, name='stale', email='stale@example.com')
        recipient.action_restore()
        self.assertEqual(recipient.name, self.student.name)
        self.assertEqual(recipient.email, self.student.student_email)
        self.assertEqual(recipient.level_id, self.level)
        self.assertEqual(len(recipient.limesurvey_enrollment_ids), 1)
        self.assertEqual(recipient.limesurvey_enrollment_ids.subject_id, self.subject)

    def test_action_restore_returns_false_without_student(self):
        recipient = self._recipient()
        self.assertFalse(recipient.action_restore())

    # -- create() manual-state autofill -----------------------------------------

    def test_create_manual_autofills_name_and_email_from_student(self):
        recipient = self.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': self.header.id, 'state': 'manual', 'student_id': self.student.id,
        })
        self.assertEqual(recipient.name, self.student.name)
        self.assertEqual(recipient.email, self.student.student_email)
        self.assertEqual(recipient.state, 'pending')  # action_restore resets 'manual' back to 'pending'

    def test_create_manual_action_restore_overrides_explicit_name_and_email(self):
        # create()'s own autofill only fills name/email when absent from vals - but the
        # unconditional action_restore() call right after super().create() always re-derives
        # both from the student regardless, so an explicit name/email at create time doesn't
        # actually stick for a 'manual' record.
        recipient = self.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': self.header.id, 'state': 'manual', 'student_id': self.student.id,
            'name': 'Custom Name', 'email': 'porrino.fernando+custom@example.com',
        })
        self.assertEqual(recipient.name, self.student.name)
        self.assertEqual(recipient.email, self.student.student_email)

    def test_create_manual_without_student_id_does_not_crash(self):
        # Regression: browse(v["student_id"]) used to KeyError when 'manual' state was
        # created without a student_id at all, instead of degrading gracefully like
        # action_restore() does for a recipient with no student.
        recipient = self.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': self.header.id, 'state': 'manual', 'name': 'No Student',
        })
        self.assertEqual(recipient.name, 'No Student')

    def test_create_manual_on_uploaded_header_triggers_upload_without_real_api(self):
        # Manually adding a recipient to an already-uploaded/open survey immediately
        # re-triggers action_upload() -> run_action() -> run_in_thread() -> LimesurveyApi;
        # both must be mocked here, this must never reach the real API. create()'s manual
        # flow also does a real self.env.cr.commit(), forbidden inside a TransactionCase -
        # stubbed out here the same way, since production code legitimately needs it.
        header = self.env['ems.limesurvey_header'].create({
            'name': 'uploaded_header', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\n{'TITLE'}", 'state': 'uploaded',
        })

        # Can't use make_synchronous_run_in_thread() here: the recipient doesn't exist yet at
        # patch-setup time (it's created by the mocked create() call below) - this closure
        # uses the actual `self_recipient` autospec passes at call time instead of a
        # pre-existing record.
        def fake_run_in_thread(self_recipient, setup, compute_fn, store, callback, *a, **kw):
            setup(self_recipient)
            compute_fn()
            store(self_recipient)
            callback(self_recipient)

        with patch('odoo.addons.ems.models.communications.limesurvey.LimesurveyApi') as mock_api_cls, \
                patch.object(self.env.registry['ems.limesurvey_recipient'], 'run_in_thread', side_effect=fake_run_in_thread, autospec=True), \
                patch.object(self.env.cr, 'commit'):
            mock_instance = MagicMock()
            mock_instance.create_survey.return_value = '123'
            mock_instance.add_participants.return_value = []
            mock_api_cls.return_value = mock_instance
            recipient = self.env['ems.limesurvey_recipient'].create({
                'limesurvey_header_id': header.id, 'state': 'manual', 'student_id': self.student.id,
            })

        self.assertEqual(recipient.state, 'uploaded')
        mock_api_cls.assert_called()
        mock_instance.create_survey.assert_called_once()

    # -- _compute_inuse_student_ids ----------------------------------------------

    def test_inuse_student_ids_populated_only_for_manual_state(self):
        # create()'s own logic always flips a freshly-created 'manual' record to 'pending'
        # right away (state='manual' only exists transiently, e.g. in the add-student popup's
        # onchange, never as a value create() actually persists) - so state is set via write()
        # here to observe the compute in isolation, bypassing create()'s override entirely.
        other_student = self.env['res.partner'].create({
            'name': 'Other Recipient Student', 'contact_type': 'student', 'main_group_id': self.group.id,
        })
        self._recipient(student_id=other_student.id)
        manual_recipient = self._recipient()
        manual_recipient.write({'state': 'manual'})
        self.assertIn(other_student, manual_recipient.inuse_student_ids)

    def test_inuse_student_ids_empty_for_non_manual_state(self):
        recipient = self._recipient(state='pending')
        self.assertFalse(recipient.inuse_student_ids)

    # -- popups -------------------------------------------------------------

    def test_open_error_popup(self):
        recipient = self._recipient(error='Something went wrong')
        action = recipient.open_error_popup()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_id'], recipient.id)

    # -- action_remind / action_delete: happy path -------------------------------

    def test_action_remind_calls_do_send_reminders(self):
        recipient = self._recipient(internal_id='RSURVEY', external_id='999')

        with patch('odoo.addons.ems.models.communications.limesurvey.LimesurveyApi') as mock_api_cls, \
                patch.object(self.env.registry['ems.limesurvey_recipient'], 'run_in_thread', side_effect=make_synchronous_run_in_thread(recipient), autospec=True):
            mock_instance = MagicMock()
            mock_api_cls.return_value = mock_instance
            recipient.action_remind()

        mock_instance.remind_participants.assert_called_once_with('999')
        self.assertFalse(recipient.is_running)

    def test_action_delete_calls_do_remove_recipients(self):
        recipient = self._recipient(internal_id='RSURVEY2', external_id='888', tid=5)

        with patch('odoo.addons.ems.models.communications.limesurvey.LimesurveyApi') as mock_api_cls, \
                patch.object(self.env.registry['ems.limesurvey_recipient'], 'run_in_thread', side_effect=make_synchronous_run_in_thread(recipient), autospec=True):
            mock_instance = MagicMock()
            mock_instance.count_participants.return_value = 0
            mock_api_cls.return_value = mock_instance
            recipient.action_delete()

        mock_instance.delete_participants.assert_called_once()

    # -- action_remind / action_delete: robust to a failed setup -----------------

    def test_action_remind_survives_failed_setup(self):
        # Regression: action_remind()'s compute() closure used to skip the
        # `if success:` guard present on every sibling action, so `persistent_data["surveys"]`
        # (never populated when setup() fails) was accessed unconditionally - reachable
        # any time load_persistent_data()/compute_survey_data() raises for this recipient.
        recipient = self._recipient()

        with patch('odoo.addons.ems.models.communications.limesurvey.load_persistent_data', side_effect=Exception("boom")), \
                patch.object(self.env.registry['ems.limesurvey_recipient'], 'run_in_thread', side_effect=make_synchronous_run_in_thread(recipient), autospec=True):
            recipient.action_remind()  # must not raise

        self.assertFalse(recipient.is_running)

    def test_action_delete_survives_failed_setup(self):
        recipient = self._recipient()

        with patch('odoo.addons.ems.models.communications.limesurvey.load_persistent_data', side_effect=Exception("boom")), \
                patch.object(self.env.registry['ems.limesurvey_recipient'], 'run_in_thread', side_effect=make_synchronous_run_in_thread(recipient), autospec=True):
            recipient.action_delete()  # must not raise

        self.assertFalse(recipient.is_running)
        self.assertTrue(recipient.exists())  # post_store's unlink() never ran, success stayed False


class TestLimesurveyEnrollment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TLM7', level={'name': 'Test LimeSurvey Enrollment Level'}, study={
            'name': 'Test LimeSurvey Enrollment Study',
        })
        cls.subject = cls.env['ems.subject'].create({'code': 'TLM7SUB', 'acronym': 'TLM7S', 'name': 'Test Subject'})
        cls.student = cls.env['res.partner'].create({'name': 'Enrollment Test Student', 'contact_type': 'student'})
        cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})

        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'enrollment_test_header', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\n{'TITLE'}",
        })
        cls.recipient = cls.env['ems.limesurvey_recipient'].create({
            'limesurvey_header_id': cls.header.id, 'name': 'R', 'email': 'porrino.fernando+enr@example.com',
            'student_id': cls.student.id, 'state': 'pending',
        })

    def test_inuse_subject_ids_reflects_student_enrollments(self):
        enrollment = self.env['ems.limesurvey_enrollment'].create({
            'limesurvey_recipient_id': self.recipient.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })
        self.assertIn(self.subject, enrollment.inuse_subject_ids)

    def test_related_student_and_study_fields(self):
        enrollment = self.env['ems.limesurvey_enrollment'].create({
            'limesurvey_recipient_id': self.recipient.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })
        self.assertEqual(enrollment.student_id, self.student)
