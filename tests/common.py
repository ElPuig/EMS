# -*- coding: utf-8 -*-
"""Shared test utilities - see docs/en/developers/shared/testing.md for the rationale
(extracted after the DTON rollout found the same fixture/mock boilerplate hand-written
identically across dozens of test files)."""

from unittest.mock import patch


def create_level_study(cls, prefix, **overrides):
    """Creates a level+study pair with `prefix`-derived unique codes.
    overrides: optional 'level'/'study' sub-dicts to override any field."""
    level = cls.env['ems.level'].create({
        'acronym': prefix, 'name': f'Test {prefix} Level', **overrides.get('level', {}),
    })
    study = cls.env['ems.study'].create({
        'code': f'{prefix}-01', 'acronym': prefix, 'name': f'Test {prefix} Study',
        'date': '2026-01-01', 'deprecated': False, 'level_id': level.id,
        **overrides.get('study', {}),
    })
    return level, study


def create_level_study_group(cls, prefix, **overrides):
    """Creates a level+study+group triple with `prefix`-derived unique codes.
    overrides: optional 'level'/'study'/'group' sub-dicts to override any field."""
    level, study = create_level_study(cls, prefix, level=overrides.get('level', {}), study=overrides.get('study', {}))
    group = cls.env['ems.group'].create({
        'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
        **overrides.get('group', {}),
    })
    return level, study, group


def mock_outgoing_email(cls):
    """Neutralizes real SMTP delivery for the duration of the test class - see CLAUDE.md's
    'Email safety in tests'. Call once from setUpClass. Returns the mock (e.g. to later assert
    on call count with cls.mail_transport.assert_not_called() / .reset_mock())."""
    patcher = patch(
        'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
        return_value='test-message-id',
    )
    mock = patcher.start()
    cls.addClassCleanup(patcher.stop)
    return mock


def force_user_language_to_english(test, user):
    """Force `user`'s language to en_US for the duration of the current test only, restored
    via test.addCleanup() (on top of the test's own transaction rollback, for clarity since
    this mutates a real, pre-existing user rather than one created fresh in the test).

    Required by any tour/HttpCase test that logs in as a real, pre-existing account (e.g.
    base.user_admin, login="admin") and asserts on literal English button/field text - this
    box's real accounts are not guaranteed to have lang='en_US' (this dev DB's admin is
    'es_ES'), and a freshly created res.users record without an explicit 'lang' key isn't
    guaranteed en_US either (confirmed on this box: defaults to 'ca_ES'). See CLAUDE.md's
    "Tour tests and language" testing convention."""
    original_lang = user.lang
    user.lang = 'en_US'
    test.addCleanup(lambda: user.write({'lang': original_lang}))


def make_synchronous_run_in_thread(record):
    """A run_in_thread() replacement that runs setup/compute/store/callback synchronously
    against `record`, for tests that need run_action()'s wiring without real threading or a
    real LimesurveyApi call. Use as: patch.object(type(record), 'run_in_thread',
    side_effect=make_synchronous_run_in_thread(record), autospec=True)."""
    def fake_run_in_thread(self_record, setup, compute, store, callback, *args, **kwargs):
        setup(record)
        compute()
        store(record)
        callback(record)
    return fake_run_in_thread
