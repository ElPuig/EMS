# -*- coding: utf-8 -*-

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

from odoo.addons.ems.models.communications.limesurvey import (
    _build_csv,
    _clean_trainer,
    _do,
    _email_not_empty,
    do_close_survey,
    do_download_survey,
    do_open_survey,
    do_remove_recipients,
    do_remove_survey,
    do_remove_survey_if_empty,
    do_reopen_survey,
    do_send_invitations,
    do_send_reminders,
    do_upload_recipient_changes,
    do_upload_recipients,
    do_upload_survey,
    load_persistent_data,
    run_action,
)


def _survey(**overrides):
    base = {
        "internal_id": "SURVEY_1",
        "external_id": "123",
        "raw_tsv": "col1\tcol2",
        "state": "closed",
        "recipients": [
            {"name": "Student One", "email": "porrino.fernando+1@example.com", "tid": 1, "external_id": "123", "internal_id": "SURVEY_1"},
        ],
    }
    base.update(overrides)
    return base


class TestDetachedHelpers(TransactionCase):
    """_do / _email_not_empty / _clean_trainer / _build_csv — no DB, no API."""

    def test_do_returns_true_when_code_returns_none(self):
        self.assertTrue(_do(_survey(), lambda: None))

    def test_do_returns_code_result(self):
        self.assertFalse(_do(_survey(), lambda: False))
        self.assertTrue(_do(_survey(), lambda: True))

    def test_do_catches_exception_and_flags_all_recipients(self):
        survey = _survey(recipients=[{"name": "A"}, {"name": "B"}])

        def code():
            raise ValueError("boom")

        result = _do(survey, code)
        self.assertFalse(result)
        for rec in survey["recipients"]:
            self.assertIn("boom", rec["error"])

    def test_email_not_empty(self):
        self.assertEqual(_email_not_empty(""), "Empty email address!")
        self.assertEqual(_email_not_empty(None), "Empty email address!")
        self.assertIsNone(_email_not_empty("porrino.fernando+x@example.com"))

    def test_clean_trainer_strips_prefix(self):
        self.assertEqual(_clean_trainer("Trainer: Jane Doe"), "Jane Doe")
        self.assertEqual(_clean_trainer("TRAINER:   Jane Doe  "), "Jane Doe")

    def test_clean_trainer_leaves_other_values(self):
        self.assertEqual(_clean_trainer("Jane Doe"), "Jane Doe")
        self.assertEqual(_clean_trainer(None), "")
        self.assertEqual(_clean_trainer(""), "")

    def test_build_csv_numeric_and_comment_rows(self):
        response = {
            "submitdate": "2026-07-29 10:00:00",
            "L1level": "ESO1", "L1topic": "Math", "L1subjectcode": "MAT1",
            "L1subjectname": "Mathematics", "L1degree": "ESO", "L1group": "1A",
            "L1trainer": "Trainer: Jane Doe",
            "L1questions[L11]": "5", "L1questions[L12]": "4",
            "L1comments": "Great course",
        }
        csv_text = _build_csv(self.env, [response])
        lines = csv_text.strip().split("\r\n")

        self.assertEqual(lines[0], "evaluation_id,timestamp,year,level,department,degree,group,subject_code,subject_name,trainer,topic,question_sort,question_type,value")
        self.assertEqual(len(lines), 4)  # header + 2 numeric rows + 1 comment row
        self.assertIn("Jane Doe", lines[1])
        self.assertIn("Numeric", lines[1])
        self.assertIn("Numeric", lines[2])
        self.assertIn("Text,Great course", lines[3])

    def test_build_csv_skips_comment_row_when_empty(self):
        response = {
            "L1level": "ESO1", "L1questions[L11]": "3",
        }
        csv_text = _build_csv(self.env, [response])
        lines = csv_text.strip().split("\r\n")
        self.assertEqual(len(lines), 2)  # header + 1 numeric row, no comment row


class TestDoFunctions(TransactionCase):
    """do_* orchestration helpers — every LimeSurvey call goes through a mocked
    ls_api (MagicMock), never a real request, per the block's testing rule."""

    def setUp(self):
        super().setUp()
        self.ls_api = MagicMock()

    def test_do_upload_survey_sets_external_id(self):
        self.ls_api.create_survey.return_value = "999"
        survey = _survey(external_id=None)
        self.assertTrue(do_upload_survey(self.ls_api, survey))
        self.assertEqual(survey["external_id"], "999")
        self.ls_api.create_survey.assert_called_once_with(survey["raw_tsv"])

    def test_do_remove_survey_resets_recipients(self):
        survey = _survey()
        self.assertTrue(do_remove_survey(self.ls_api, survey))
        self.ls_api.delete_survey.assert_called_once_with("123")
        rec = survey["recipients"][0]
        self.assertIsNone(rec["external_id"])
        self.assertIsNone(rec["internal_id"])
        self.assertEqual(rec["state"], "pending")

    def test_do_upload_recipients_success(self):
        self.ls_api.add_participants.return_value = [{"tid": 5, "token": "TOK", "email": "porrino.fernando+1@example.com"}]
        survey = _survey()
        self.assertTrue(do_upload_recipients(self.ls_api, survey))
        rec = survey["recipients"][0]
        self.assertEqual(rec["tid"], 5)
        self.assertEqual(rec["token"], "TOK")
        self.assertEqual(rec["state"], "uploaded")
        self.assertIsNone(rec["error"])

    def test_do_upload_recipients_flags_empty_email(self):
        self.ls_api.add_participants.return_value = [{"tid": 5, "token": "TOK", "email": ""}]
        survey = _survey()
        do_upload_recipients(self.ls_api, survey)
        self.assertEqual(survey["recipients"][0]["error"], "Empty email address!")

    def test_do_upload_recipients_propagates_row_error(self):
        self.ls_api.add_participants.return_value = [{"tid": 5, "token": "TOK", "email": "porrino.fernando+1@example.com", "error": "Invalid token ID"}]
        survey = _survey()
        do_upload_recipients(self.ls_api, survey)
        self.assertEqual(survey["recipients"][0]["error"], "Invalid token ID")

    def test_do_upload_recipients_api_failure(self):
        self.ls_api.add_participants.side_effect = Exception("API down")
        survey = _survey()
        self.assertFalse(do_upload_recipients(self.ls_api, survey))
        self.assertIn("API down", survey["error"])

    def test_do_open_survey_activates_and_invites(self):
        survey = _survey()
        self.assertTrue(do_open_survey(self.ls_api, survey))
        self.ls_api.activate_survey.assert_called_once_with("123")
        self.ls_api.invite_participants.assert_called_once_with("123")

    def test_do_close_survey_deactivates(self):
        survey = _survey()
        survey["recipients"][0]["error"] = "stale"
        self.assertTrue(do_close_survey(self.ls_api, survey))
        self.ls_api.deactivate_survey.assert_called_once_with("123")
        self.assertIsNone(survey["recipients"][0]["error"])

    def test_do_reopen_survey_reactivates(self):
        survey = _survey()
        self.assertTrue(do_reopen_survey(self.ls_api, survey))
        self.ls_api.reactivate_survey.assert_called_once_with("123")

    def test_do_download_survey_stores_responses(self):
        self.ls_api.export_survey_responses.return_value = [{"id": 1}]
        survey = _survey()
        self.assertTrue(do_download_survey(self.ls_api, survey))
        self.assertEqual(survey["responses"], [{"id": 1}])

    def test_do_send_invitations(self):
        survey = _survey()
        self.assertTrue(do_send_invitations(self.ls_api, survey))
        self.ls_api.invite_participants.assert_called_once_with("123")

    def test_do_send_reminders(self):
        survey = _survey()
        self.assertTrue(do_send_reminders(self.ls_api, survey))
        self.ls_api.remind_participants.assert_called_once_with("123")

    def test_do_remove_recipients_success(self):
        survey = _survey()
        self.assertTrue(do_remove_recipients(self.ls_api, survey))
        self.ls_api.delete_participants.assert_called_once_with("123", [1])

    def test_do_remove_recipients_skips_recipients_without_external_id(self):
        survey = _survey(recipients=[{"name": "No survey yet", "external_id": None, "tid": None}])
        self.assertTrue(do_remove_recipients(self.ls_api, survey))
        self.ls_api.delete_participants.assert_not_called()

    def test_do_remove_recipients_api_failure(self):
        self.ls_api.delete_participants.side_effect = Exception("boom")
        survey = _survey()
        self.assertFalse(do_remove_recipients(self.ls_api, survey))
        self.assertIn("boom", survey["recipients"][0]["error"])

    def test_do_remove_survey_if_empty_deletes_when_empty(self):
        self.ls_api.count_participants.return_value = 0
        survey = _survey()
        self.assertTrue(do_remove_survey_if_empty(self.ls_api, survey))
        self.ls_api.delete_survey.assert_called_once_with("123")

    def test_do_remove_survey_if_empty_keeps_when_not_empty(self):
        self.ls_api.count_participants.return_value = 3
        survey = _survey()
        self.assertTrue(do_remove_survey_if_empty(self.ls_api, survey))
        self.ls_api.delete_survey.assert_not_called()

    def test_do_upload_recipient_changes_updates_in_place(self):
        survey = _survey()
        survey["recipients"][0]["internal_id"] = "SURVEY_1"
        self.assertTrue(do_upload_recipient_changes(self.ls_api, survey))
        self.ls_api.update_participant_data.assert_called_once()

    def test_do_upload_recipient_changes_flags_empty_email_in_place(self):
        survey = _survey(recipients=[{"name": "A", "email": "", "tid": 1, "external_id": "123", "internal_id": "SURVEY_1"}])
        self.assertFalse(do_upload_recipient_changes(self.ls_api, survey))
        self.assertEqual(survey["recipients"][0]["error"], "Empty email address!")

    def test_do_upload_recipient_changes_moves_to_new_existing_survey(self):
        # Recipient currently belongs to a different survey (internal_id mismatch); target survey already exists.
        survey = _survey(external_id="456")
        survey["recipients"][0]["internal_id"] = "OTHER_SURVEY"
        survey["recipients"][0]["external_id"] = "123"
        self.ls_api.add_participants.return_value = [{"tid": 9, "token": "TOK9", "email": "porrino.fernando+1@example.com"}]

        self.assertTrue(do_upload_recipient_changes(self.ls_api, survey))
        self.ls_api.delete_participants.assert_called_once_with("123", [1])
        self.assertEqual(survey["recipients"][0]["internal_id"], "SURVEY_1")
        self.assertEqual(survey["recipients"][0]["external_id"], "456")
        self.ls_api.add_participants.assert_called_once()

    def test_do_upload_recipient_changes_creates_new_survey_when_none_exists(self):
        survey = _survey(external_id=None)
        survey["recipients"][0]["internal_id"] = "OTHER_SURVEY"
        survey["recipients"][0]["external_id"] = None  # never uploaded anywhere yet
        self.ls_api.create_survey.return_value = "789"
        self.ls_api.add_participants.return_value = [{"tid": 1, "token": "TOK", "email": "porrino.fernando+1@example.com"}]

        self.assertTrue(do_upload_recipient_changes(self.ls_api, survey))
        self.ls_api.create_survey.assert_called_once_with(survey["raw_tsv"])
        self.assertEqual(survey["external_id"], "789")

    def test_do_upload_recipient_changes_opens_survey_when_state_open(self):
        survey = _survey(external_id=None, state="open")
        survey["recipients"][0]["internal_id"] = "OTHER_SURVEY"
        survey["recipients"][0]["external_id"] = None
        self.ls_api.create_survey.return_value = "789"
        self.ls_api.add_participants.return_value = [{"tid": 1, "token": "TOK", "email": "porrino.fernando+1@example.com"}]

        self.assertTrue(do_upload_recipient_changes(self.ls_api, survey))
        self.ls_api.activate_survey.assert_called_once_with("789")
        self.ls_api.invite_participants.assert_called_once_with("789")


class TestLoadPersistentData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level = cls.env['ems.level'].create({'acronym': 'TLIM', 'name': 'Test LimeSurvey Level'})
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'test_survey', 'title': 'Test Survey', 'description': 'A test survey',
            'target': 'students', 'tsv_raw_text': "col1\tcol2\n{'TITLE'}\t{'DESCRIPTION'}",
        })

    def _recipient(self, **vals):
        base = {
            'limesurvey_header_id': self.header.id, 'name': 'Student', 'email': 'porrino.fernando+ls@example.com',
            'level_id': self.level.id, 'state': 'pending',
        }
        base.update(vals)
        return self.env['ems.limesurvey_recipient'].create(base)

    def test_header_groups_recipients_by_internal_id(self):
        self._recipient(internal_id='S1', external_id='E1')
        self._recipient(internal_id='S1', external_id='E1')
        self._recipient(internal_id='S2', external_id=False)

        surveys = load_persistent_data(self.header, compute_survey_data=False)
        self.assertEqual(set(surveys.keys()), {'S1', 'S2'})
        self.assertEqual(len(surveys['S1']['recipients']), 2)
        self.assertEqual(len(surveys['S2']['recipients']), 1)

    def test_recipient_loads_its_own_survey(self):
        rec = self._recipient(internal_id='S3', external_id='E3')
        surveys = load_persistent_data(rec, compute_survey_data=False)
        self.assertEqual(list(surveys.keys()), ['S3'])
        self.assertEqual(surveys['S3']['external_id'], 'E3')

    def test_unsupported_model_raises_not_implemented_error(self):
        with self.assertRaises(NotImplementedError):
            load_persistent_data(self.env['ems.level'].browse(self.level.id), compute_survey_data=False)

    def test_computes_survey_data_when_requested(self):
        # internal_id is a hash of a survey_name built from the header/blocks/recipient
        # (ems.limesurvey_header.compute_survey_data) - not reproducible by hand here, so
        # this only asserts the grouping + content-building actually ran end to end.
        self._recipient()
        surveys = load_persistent_data(self.header, compute_survey_data=True)
        self.assertEqual(len(surveys), 1)
        raw_tsv = next(iter(surveys.values()))["raw_tsv"]
        self.assertIn("Test Survey", raw_tsv)
        self.assertIn("A test survey", raw_tsv)


class TestRunAction(TransactionCase):
    """run_action() is shared infrastructure for both ems.limesurvey_header and
    ems.limesurvey_recipient's action_* methods - exercised here directly against
    a real header record, with run_in_thread mocked (no real threading/API)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'run_action_test', 'title': 'Run Action Test', 'description': 'desc',
            'target': 'students', 'tsv_raw_text': "col1\tcol2",
        })

    def test_run_action_success_path_runs_setup_compute_store_callback(self):
        # status_w/status_ok/status_ko must be real ems.limesurvey_header selection values.
        header = self.header
        header.is_running = False
        header.state = 'computed'
        persistent_data = {}
        compute = MagicMock()

        def fake_run_in_thread(self_header, setup, compute_fn, store, callback, *a, **kw):
            # autospec on a class-level patch passes `self` explicitly as the first arg.
            setup(header)
            compute_fn()
            store(header)
            callback(header)

        with patch.object(type(header), 'run_in_thread', side_effect=fake_run_in_thread, autospec=True):
            result = run_action(header, "Test action", "Test", "uploading", "uploaded", "computed", compute, persistent_data)

        self.assertTrue(result)
        self.assertFalse(header.is_running)
        self.assertEqual(header.state, 'uploaded')
        compute.assert_called_once()

    def test_run_action_recovers_when_run_in_thread_raises_synchronously(self):
        # Regression test: run_in_thread() failing synchronously used to crash callback()
        # with a TypeError (wrong arg count), silently swallowed by `finally: return True`,
        # leaving is_running stuck True forever with no notification. Fixed by threading the
        # error through persistent_data instead of passing it as an extra positional arg.
        header = self.header
        header.is_running = False
        header.state = 'computed'
        persistent_data = {}
        compute = MagicMock()

        with patch.object(type(header), 'run_in_thread', side_effect=RuntimeError("can't start new thread"), autospec=True):
            result = run_action(header, "Test action", "Test", "uploading", "uploaded", "computed", compute, persistent_data)

        self.assertTrue(result)
        self.assertFalse(header.is_running)
        self.assertEqual(header.state, 'computed')

    def test_run_action_skips_when_already_running(self):
        header = self.header
        header.is_running = True
        header.state = 'uploading'
        persistent_data = {}
        compute = MagicMock()

        with patch.object(type(header), 'run_in_thread', autospec=True) as mock_run:
            result = run_action(header, "Test action", "Test", "uploading", "uploaded", "computed", compute, persistent_data)

        self.assertTrue(result)
        mock_run.assert_not_called()
        self.assertEqual(header.state, 'uploading')  # untouched, already-running guard fired first

        header.is_running = False  # cleanup so later tests in this class aren't blocked
