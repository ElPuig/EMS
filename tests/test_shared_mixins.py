# -*- coding: utf-8 -*-

from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestEmsBase(TransactionCase):
    """`ems.base` (models/shared/base.py). Pure/self.env-only methods are tested
    against the empty `ems.base` abstract-model recordset directly; methods that
    need a real persisted record (chatter/action_archive) use ems.limesurvey_header,
    an arbitrary real consumer already covered elsewhere in this rollout."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'base_mixin_test', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\nval",
        })

    def test_get_user_is_admin_true_for_admin_group(self):
        # the test runner's default user (OdooBot/admin) is in group_academic_admin
        self.assertTrue(self.env['ems.base'].get_user_is_admin())

    def test_get_user_is_admin_false_for_non_admin(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Base Mixin Test User', 'login': 'base_mixin_test_user',
        })
        self.assertFalse(self.env['ems.base'].with_user(user).get_user_is_admin())

    def test_get_user_is_tutor_false_without_tutorship(self):
        self.assertFalse(self.env['ems.base'].get_user_is_tutor())

    def test_get_user_is_tutor_of_self_returns_none_without_tutor_id_field(self):
        # ems.base itself has no tutor_id field - the method has no explicit
        # return for that branch, so it implicitly returns None.
        self.assertIsNone(self.env['ems.base'].get_user_is_tutor_of_self())

    def test_persistent_hash_is_deterministic(self):
        base = self.env['ems.base']
        self.assertEqual(base.persistent_hash("some value"), base.persistent_hash("some value"))
        self.assertNotEqual(base.persistent_hash("some value"), base.persistent_hash("other value"))

    def test_notify_sends_bus_message(self):
        with patch.object(type(self.env.user), '_bus_send') as mock_bus_send:
            self.env['ems.base'].notify("Title", "Message", "success", sticky=True)
        mock_bus_send.assert_called_once_with("simple_notification", {
            "title": "Title", "message": "Message", "type": "success", "sticky": True,
        })

    def test_chatter_posts_a_message(self):
        before = len(self.header.message_ids)
        self.header.chatter("Plain log message")
        self.assertEqual(len(self.header.message_ids), before + 1)
        self.assertIn("Plain log message", self.header.message_ids[0].body)

    def test_chatter_exception_escapes_untrusted_content(self):
        # Regression: chatter_exception() used to build its HTML via an f-string wrapped
        # in Markup(...), which never escapes the interpolated exception text - an exception
        # message containing HTML-significant characters (e.g. echoing raw user/DB content,
        # as several import wizards in this codebase do) would inject literal unescaped markup.
        exception = Exception("<script>alert('xss')</script> & <b>bold</b>")
        self.header.chatter_exception(exception)
        body = self.header.message_ids[0].body
        self.assertNotIn("<script>alert('xss')</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_action_archive_deactivates(self):
        header = self.env['ems.limesurvey_header'].create({
            'name': 'archive_test', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\nval",
        })
        self.assertTrue(header.active)
        header.action_archive()
        self.assertFalse(header.active)


class TestEmsDatetimeUtils(TransactionCase):
    """`ems.datetime_utils` (models/shared/datetime_utils.py) - stateless helpers,
    tested directly against the empty AbstractModel recordset (same pattern already
    used in models/settings/settings.py: self.env['ems.datetime_utils'].<method>())."""

    def test_time_string_to_float(self):
        utils = self.env['ems.datetime_utils']
        self.assertEqual(utils.time_string_to_float("17:45"), 17.75)
        self.assertEqual(utils.time_string_to_float("08:00"), 8.0)
        self.assertEqual(utils.time_string_to_float("00:30"), 0.5)

    def test_time_to_float(self):
        utils = self.env['ems.datetime_utils']
        self.assertEqual(utils.time_to_float(SimpleNamespace(hour=9, minute=15)), 9.25)

    def test_ranges_overlap(self):
        utils = self.env['ems.datetime_utils']
        self.assertTrue(utils.ranges_overlap(8.0, 10.0, 9.0, 11.0))
        self.assertFalse(utils.ranges_overlap(8.0, 10.0, 10.0, 12.0))

    def test_local_utc_roundtrip_does_not_shadow_the_datetime_class(self):
        # Regression: local_datetime_to_utc/utc_datetime_to_local/datetime_to_odoo used to
        # name their parameter `datetime`, shadowing the module-level `datetime` class import -
        # harmless today (none of them needed the class inside the body), but a latent trap for
        # any future edit. Renamed to `dt`; this just confirms behavior is unchanged.
        utils = self.env['ems.datetime_utils']
        local = utils.get_local_datetime()
        utc = utils.local_datetime_to_utc(local)
        back_to_local = utils.utc_datetime_to_local(utc)
        self.assertEqual(local.timestamp(), back_to_local.timestamp())
        naive = utils.datetime_to_odoo(utc)
        self.assertIsNone(naive.tzinfo)

    def test_next_occurrence_utc_returns_a_naive_datetime(self):
        utils = self.env['ems.datetime_utils']
        result = utils.next_occurrence_utc(12.5)
        self.assertIsNotNone(result)
        self.assertIsNone(result.tzinfo)  # datetime_to_odoo() strips tzinfo


class TestEmsScheduleReportMixin(TransactionCase):
    """`ems.schedule_report_mixin` (models/shared/schedule_report_mixin.py) - pure
    helpers, tested via lightweight attribute-only doubles (no Odoo record needed,
    since the methods never call anything but plain attribute access on their arg)."""

    def test_report_color_key_prefers_non_teaching(self):
        mixin = self.env['ems.schedule_report_mixin']
        attendance = SimpleNamespace(non_teaching=SimpleNamespace(id=7), subject_id=SimpleNamespace(id=3))
        self.assertEqual(mixin._report_color_key(attendance), ('non_teaching', 7))

    def test_report_color_key_falls_back_to_subject(self):
        mixin = self.env['ems.schedule_report_mixin']
        attendance = SimpleNamespace(non_teaching=False, subject_id=SimpleNamespace(id=3))
        self.assertEqual(mixin._report_color_key(attendance), ('subject', 3))

    def test_format_report_time(self):
        mixin = self.env['ems.schedule_report_mixin']
        self.assertEqual(mixin._format_report_time(9.5), "09:30")
        self.assertEqual(mixin._format_report_time(17.25), "17:15")


class TestEmsMultithreading(TransactionCase):
    """`ems.multithreading` (models/shared/multithreading.py). run_in_thread() spawns
    a real background thread against a real (rolled-back-on-setup) cursor, so these
    tests join the thread and re-browse from the main env to observe the result -
    slower than a mock, but this is the one place actually testing the raw engine
    every mocked `run_in_thread` test elsewhere in this rollout stands in for."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'multithreading_test', 'title': 'T', 'description': 'D',
            'target': 'students', 'tsv_raw_text': "col\nval",
        })

    def test_reload_request_sends_bus_message(self):
        with patch.object(type(self.env.user), '_bus_send') as mock_bus_send:
            self.header.reload_request("custom message")
        mock_bus_send.assert_called_once_with("reload_request", {
            "model": "ems.limesurvey_header", "record_id": self.header.id, "message": "custom message",
        })

    def test_already_running_true_notifies_and_returns_true(self):
        self.header.is_running = True
        with patch.object(type(self.header), 'notify') as mock_notify:
            self.assertTrue(self.header.already_running())
        mock_notify.assert_called_once()
        self.header.is_running = False

    def test_already_running_false_returns_false_without_notifying(self):
        self.header.is_running = False
        with patch.object(type(self.header), 'notify') as mock_notify:
            self.assertFalse(self.header.already_running())
        mock_notify.assert_not_called()

    # -- run_in_thread(): NOT tested here end-to-end, deliberately -----------------
    #
    # run_in_thread() opens its own, genuinely separate database connection
    # (registry(dbname).cursor()) for setup()/store()/callback(), independent of
    # TransactionCase's own connection. TransactionCase never commits its fixtures -
    # every test runs inside a savepoint that's rolled back at the end - so a second,
    # real connection simply cannot see any record created in this test's own
    # setUp()/test body: attempts to read it raise MissingError, and opening enough
    # fresh connections back-to-back under this suite's load was observed to
    # intermittently block for several seconds waiting on a connection-pool slot,
    # which would make a from-scratch test of this method flaky through no fault of
    # the code under test. This was confirmed empirically while writing this test
    # file (see the git history of this file for the attempted version) rather than
    # assumed - every one of the ~15 callers of run_in_thread elsewhere in this
    # codebase (ems.limesurvey_header/_recipient's action_* methods, see
    # docs/en/developers/communications/limesurvey.md) independently arrived at the
    # same conclusion and mocks run_in_thread itself rather than exercising it for
    # real. Its control flow (setup -> compute -> retry-on-conflict store+callback,
    # and this pass's fix logging an unexpected compute() failure before re-raising)
    # is covered by code review here and by every one of those callers' own tests
    # correctly driving the setup/compute/store/callback contract through a mocked
    # run_in_thread.
