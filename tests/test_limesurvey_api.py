# -*- coding: utf-8 -*-

import base64
import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.ems.models.communications.limesurvey import LimesurveyApi


def _response(status_code=200, json_data=None, text=""):
    """Builds a fake requests.Response replacement, since no test here may
    ever touch the real, production-connected LimeSurvey API."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_data if json_data is not None else {}
    return response


class TestLimesurveyApi(TransactionCase):
    """Every test mocks requests.post: this class talks to a real, production
    LimeSurvey instance in normal operation, so no test may reach the network."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.limesurvey_api = "https://limesurvey.example.com/index.php/admin/remotecontrol"
        cls.env.company.limesurvey_usr = "admin"
        cls.env.company.limesurvey_pwd = "secret"
        cls.env.company.limesurvey_gid = 1
        cls.api = LimesurveyApi(cls.env)

    def _mock_post(self, session_result="SESSIONKEY123", results=None, statuses=None, texts=None):
        """Every _run_api_request() call opens and releases its own session, so
        each item in `results`/`statuses`/`texts` expands to three HTTP calls:
        get_session_key, the method itself, release_session_key."""
        results = results or []
        statuses = statuses or [200] * len(results)
        texts = texts or [""] * len(results)
        responses = []
        for result, status, text in zip(results, statuses, texts):
            responses.append(_response(json_data={"result": session_result}))
            responses.append(_response(status_code=status, json_data={"result": result}, text=text))
            responses.append(_response(json_data={"result": "OK"}))  # release_session_key
        patcher = patch("odoo.addons.ems.models.communications.limesurvey.requests.post", side_effect=responses)
        mock_post = patcher.start()
        self.addCleanup(patcher.stop)
        return mock_post

    # -- session key handshake -------------------------------------------------

    def test_run_api_request_gets_and_releases_session_key(self):
        mock_post = self._mock_post(results=["42"])
        result = self.api._run_api_request("some_method", ["param"])

        self.assertEqual(result, "42")
        self.assertEqual(mock_post.call_count, 3)  # get_session_key, some_method, release_session_key

        first_payload = json.loads(mock_post.call_args_list[0].kwargs["data"])
        self.assertEqual(first_payload["method"], "get_session_key")

        last_payload = json.loads(mock_post.call_args_list[-1].kwargs["data"])
        self.assertEqual(last_payload["method"], "release_session_key")
        self.assertEqual(last_payload["params"], ["SESSIONKEY123"])

    def test_run_api_request_raises_without_session_key(self):
        patcher = patch(
            "odoo.addons.ems.models.communications.limesurvey.requests.post",
            side_effect=[_response(json_data={"result": None})],
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        with self.assertRaises(UserError):
            self.api._run_api_request("some_method")

    def test_run_api_request_raises_on_null_result(self):
        self._mock_post(results=[None])
        with self.assertRaises(UserError):
            self.api._run_api_request("some_method")

    def test_parse_api_response_raises_on_non_json(self):
        response = _response(status_code=200, text="not json")
        response.json.side_effect = ValueError("no JSON")
        with self.assertRaises(UserError):
            self.api._parse_api_response(response)

    def test_parse_api_response_raises_on_http_error(self):
        response = _response(status_code=500, text='<h2 class="error-title">Boom</h2>')
        response.reason = "Internal Server Error"
        with self.assertRaises(UserError):
            self.api._parse_api_response(response)

    def test_parse_api_response_raises_on_error_field(self):
        response = _response(json_data={"error": "Invalid session key"})
        with self.assertRaises(UserError):
            self.api._parse_api_response(response)

    def test_extract_limesurvey_html_error_strips_markup(self):
        html_content = '<html><body><h2 class="error-title">  Invalid   session  \n key  </h2></body></html>'
        self.assertEqual(self.api._extract_limesurvey_html_error(html_content), "Invalid session key")

    def test_extract_limesurvey_html_error_falls_back_to_raw_text(self):
        self.assertEqual(self.api._extract_limesurvey_html_error("plain text"), "plain text")

    # -- create_survey -----------------------------------------------------

    def test_create_survey_success(self):
        self._mock_post(results=["123", {"status": "OK"}, {"status": "OK"}])
        result = self.api.create_survey("col1\tcol2\nval1\tval2")
        self.assertEqual(result, "123")

    def test_create_survey_failure_raises(self):
        self._mock_post(results=[{"status": "Error: not a valid file"}])
        with self.assertRaises(Exception):
            self.api.create_survey("garbage")

    @patch.object(LimesurveyApi, "delete_survey")
    def test_create_survey_cleans_up_on_post_create_failure(self, mock_delete):
        # import_survey and set_survey_properties succeed, activate_tokens fails -> delete_survey(result), then re-raise.
        self._mock_post(
            results=["123", {"status": "OK"}, None],
            statuses=[200, 200, 500],
            texts=["", "", "boom"],
        )

        with self.assertRaises(Exception):
            self.api.create_survey("col1\tcol2\nval1\tval2")
        mock_delete.assert_called_once_with("123")

    # -- participants --------------------------------------------------------

    def test_add_participants(self):
        self._mock_post(results=[[{"email": "porrino.fernando+1@example.com"}]])
        result = self.api.add_participants("123", [{"email": "porrino.fernando+1@example.com"}])
        self.assertEqual(result, [{"email": "porrino.fernando+1@example.com"}])

    def test_delete_participants_success(self):
        self._mock_post(results=[{"1": "Deleted"}])
        self.api.delete_participants("123", ["1"])  # no exception raised

    def test_delete_participants_tolerates_already_invalid_token(self):
        self._mock_post(results=[{"1": "Invalid token ID"}])
        self.api.delete_participants("123", ["1"])  # no exception raised

    def test_delete_participants_raises_on_real_error(self):
        self._mock_post(results=[{"1": "Some other error"}])
        with self.assertRaises(Exception):
            self.api.delete_participants("123", ["1"])

    def test_update_participant_data_success(self):
        self._mock_post(results=[{"emailstatus": "OK"}])
        self.api.update_participant_data("123", "1", {"email": "porrino.fernando+2@example.com"})

    def test_update_participant_data_raises_on_error_field(self):
        self._mock_post(results=[{"error": "Invalid token ID"}])
        with self.assertRaises(Exception):
            self.api.update_participant_data("123", "1", {})

    def test_update_participant_data_raises_on_bad_emailstatus(self):
        self._mock_post(results=[{"emailstatus": "Error: bad email"}])
        with self.assertRaises(Exception):
            self.api.update_participant_data("123", "1", {})

    def test_list_participants(self):
        self._mock_post(results=[[{"email": "a@example.com"}, {"email": "b@example.com"}]])
        result = self.api.list_participants("123")
        self.assertEqual(len(result), 2)

    def test_count_participants_none_found(self):
        self._mock_post(results=[{"status": "No survey participants found."}])
        self.assertEqual(self.api.count_participants("123"), 0)

    def test_count_participants_counts_list(self):
        self._mock_post(results=[[{"email": "a@example.com"}, {"email": "b@example.com"}, {"email": "c@example.com"}]])
        self.assertEqual(self.api.count_participants("123"), 3)

    # -- delete_survey --------------------------------------------------------

    def test_delete_survey_ok(self):
        self._mock_post(results=[{"status": "OK"}])
        self.api.delete_survey("123")  # no exception raised

    def test_delete_survey_no_permission_but_already_gone(self):
        self._mock_post(results=[{"status": "No permission"}, {"status": "Error: Invalid survey ID"}])
        self.api.delete_survey("123")  # no exception raised, treated as already deleted

    def test_delete_survey_no_permission_and_still_exists(self):
        self._mock_post(results=[{"status": "No permission"}, {"foo": "still here, no status key"}])
        with self.assertRaises(Exception):
            self.api.delete_survey("123")

    def test_delete_survey_unknown_error(self):
        self._mock_post(results=[{"foo": "bar"}])
        with self.assertRaises(Exception):
            self.api.delete_survey("123")

    # -- get_group (case-insensitive match — fixed in this pass) --------------

    def test_get_group_matches_case_insensitively(self):
        self._mock_post(results=[[{"gsid": 1, "name": "Students"}, {"gsid": 2, "name": "Teachers"}]])
        result = self.api.get_group("STUDENTS")
        self.assertEqual(result["gsid"], 1)

    def test_get_group_not_found(self):
        self._mock_post(results=[[{"gsid": 1, "name": "Students"}]])
        self.assertIsNone(self.api.get_group("Unknown"))

    def test_get_group_no_groups_at_all(self):
        self._mock_post(results=[[]])
        self.assertIsNone(self.api.get_group("Students"))

    # -- activate / deactivate / reactivate survey ----------------------------

    def test_activate_survey_ok(self):
        self._mock_post(results=[{"status": "OK"}, {"status": "OK"}])
        self.api.activate_survey("123")

    def test_activate_survey_already_active_is_tolerated(self):
        self._mock_post(results=[{"status": "OK"}, {"status": "Error: Survey already active"}])
        self.api.activate_survey("123")

    def test_activate_survey_raises_on_other_error(self):
        self._mock_post(results=[{"status": "OK"}, {"status": "Error: something else"}])
        with self.assertRaises(Exception):
            self.api.activate_survey("123")

    def test_deactivate_survey_ok(self):
        self._mock_post(results=[{"expires": True}])
        self.api.deactivate_survey("123")

    def test_deactivate_survey_raises_on_bad_result(self):
        self._mock_post(results=[{"status": "Error: no such survey"}])
        with self.assertRaises(Exception):
            self.api.deactivate_survey("123")

    def test_reactivate_survey_ok(self):
        self._mock_post(results=[{"expires": True}])
        self.api.reactivate_survey("123")

    # -- export_survey_responses ----------------------------------------------

    def test_export_survey_responses_no_data(self):
        self._mock_post(results=[{"status": "No Data, survey table does not exist."}])
        self.assertEqual(self.api.export_survey_responses("123"), [])

    def test_export_survey_responses_dict_wrapper(self):
        encoded = base64.b64encode(json.dumps({"responses": [{"id": 1}, {"id": 2}]}).encode()).decode()
        self._mock_post(results=[encoded])
        result = self.api.export_survey_responses("123")
        self.assertEqual(result, [{"id": 1}, {"id": 2}])

    def test_export_survey_responses_list(self):
        encoded = base64.b64encode(json.dumps([{"id": 1}]).encode()).decode()
        self._mock_post(results=[encoded])
        self.assertEqual(self.api.export_survey_responses("123"), [{"id": 1}])

    def test_export_survey_responses_raises_on_unexpected_status(self):
        self._mock_post(results=[{"status": "Error: no permission"}])
        with self.assertRaises(Exception):
            self.api.export_survey_responses("123")

    # -- invite / remind participants ------------------------------------------

    def test_invite_participants_stops_when_nothing_left(self):
        mock_post = self._mock_post(results=[{"status": "0 left to send"}])
        self.api.invite_participants("123")
        self.assertEqual(mock_post.call_count, 3)  # session key, one invite call, release

    def test_invite_participants_raises_on_unknown_status(self):
        self._mock_post(results=[{"foo": "bar"}])
        with self.assertRaises(Exception):
            self.api.invite_participants("123")

    def test_remind_participants_passes_part_ids_when_given(self):
        mock_post = self._mock_post(results=[{"status": "0 left to send"}])
        self.api.remind_participants("123", part_ids=["1", "2"])

        remind_payload = json.loads(mock_post.call_args_list[1].kwargs["data"])
        self.assertEqual(remind_payload["params"], ["SESSIONKEY123", "123", ["1", "2"]])

    def test_remind_participants_without_part_ids(self):
        mock_post = self._mock_post(results=[{"status": "0 left to send"}])
        self.api.remind_participants("123")

        remind_payload = json.loads(mock_post.call_args_list[1].kwargs["data"])
        self.assertEqual(remind_payload["params"], ["SESSIONKEY123", "123"])
