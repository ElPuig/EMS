import importlib.util
import os
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from .common import create_level_study_group


class TestExitManagement(TransactionCase):
    """Fase 3: graduation/withdrawal wizards, transition_status, uses_enrollment_flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        # The current course is driven by the "Current course" setting
        # (company.current_course_id), which syncs ems.course.is_current.
        cls.current_course = Course.create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = cls.current_course
        cls.next_course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})

        cls.level, cls.study, cls.group = create_level_study_group(cls, 'EXM', level={'name': 'Exit Level'}, study={
            'code': 'EXM001', 'acronym': 'EXMS', 'name': 'Exit Study',
        })
        cls.study_no_flow = cls.env['ems.study'].create({
            'code': 'EXM002', 'acronym': 'EXNF', 'name': 'Exit Study No Flow',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id})
        # Enrollment template makes cls.study a "flow" study.
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Exit Enrollment Template', 'ems_study_id': cls.study.id})

    def _student(self, name, **vals):
        return self.env['res.partner'].create(dict(
            {'name': name, 'contact_type': 'student', 'main_group_id': self.group.id}, **vals))

    # --- uses_enrollment_flow -----------------------------------------------

    def test_uses_enrollment_flow_compute(self):
        self.assertTrue(self.study.uses_enrollment_flow)
        self.assertFalse(self.study_no_flow.uses_enrollment_flow)

    def test_uses_enrollment_flow_search(self):
        flow_studies = self.env['ems.study'].search([('uses_enrollment_flow', '=', True)])
        self.assertIn(self.study, flow_studies)
        self.assertNotIn(self.study_no_flow, flow_studies)
        no_flow = self.env['ems.study'].search([('uses_enrollment_flow', '=', False)])
        self.assertIn(self.study_no_flow, no_flow)

    # --- transition_status --------------------------------------------------

    def test_transition_status_former(self):
        alumni = self._student('TS Alumni', contact_type='alumni')
        self.assertEqual(alumni.transition_status, 'former')

    def test_transition_status_former_includes_expelled(self):
        expelled = self._student('TS Expelled', contact_type='expelled')
        self.assertEqual(expelled.transition_status, 'former')

    def test_transition_status_graduated(self):
        grad = self._student('TS Grad', exit_type='graduation',
                             exit_course_id=self.current_course.id)
        self.assertEqual(grad.transition_status, 'graduated')

    def test_transition_status_enrolled(self):
        student = self._student('TS Enrolled')
        # Enrolled *with* a destination group -> fully placed. ems_study_id is required
        # alongside ems_group_id (sale.order._check_group_matches_study): a destination
        # group always implies the study it belongs to.
        self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id,
            'ems_study_id': self.study.id, 'ems_group_id': self.group.id})
        self.assertEqual(student.transition_status, 'enrolled')

    def test_transition_status_unplaced(self):
        student = self._student('TS Unplaced')
        # Enrolled but no destination group yet -> unplaced (needs a group).
        self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id})
        self.assertEqual(student.transition_status, 'unplaced')

    def test_transition_status_missing_and_search(self):
        student = self._student('TS Missing')
        self.assertEqual(student.transition_status, 'missing')
        missing = self.env['res.partner'].search([
            ('contact_type', '=', 'student'), ('transition_status', '=', 'missing')])
        self.assertIn(student, missing)

    # --- graduation wizard --------------------------------------------------

    def test_graduation_wizard_marks_without_converting(self):
        student = self._student('GW Student')
        wizard = self.env['ems.graduation_wizard'].with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()
        self.assertTrue(student.has_graduated)
        self.assertEqual(student.exit_type, 'graduation')
        self.assertEqual(student.exit_course_id, self.current_course)
        # Deferred mark: still a student, group intact, no conversion.
        self.assertEqual(student.contact_type, 'student')
        self.assertEqual(student.main_group_id, self.group)

    def test_graduation_only_last_course(self):
        # A study with two courses: only the last-course student may graduate.
        study = self.env['ems.study'].create({
            'code': 'EXM003', 'acronym': 'EXLC', 'name': 'Exit Last Course',
            'date': date.today(), 'deprecated': False, 'level_id': self.level.id})
        g1 = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': self.level.id, 'study_id': study.id})
        g2 = self.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': self.level.id, 'study_id': study.id})
        first = self.env['res.partner'].create({
            'name': 'First Year', 'contact_type': 'student', 'main_group_id': g1.id})
        last = self.env['res.partner'].create({
            'name': 'Last Year', 'contact_type': 'student', 'main_group_id': g2.id})
        wizard = self.env['ems.graduation_wizard'].with_context(
            active_ids=(first + last).ids).create({})
        wizard.action_apply()
        # First-year student is blocked (not in the last course).
        self.assertFalse(first.has_graduated)
        self.assertNotEqual(first.exit_type, 'graduation')
        first_line = wizard.line_ids.filtered(lambda l: l.student_id == first)
        self.assertTrue(first_line.blocked)
        # Last-year student graduates normally.
        self.assertTrue(last.has_graduated)
        self.assertEqual(last.exit_type, 'graduation')

    def test_graduation_wizard_unmark_keeps_has_graduated(self):
        student = self._student('GW Unmark')
        wizard = self.env['ems.graduation_wizard'].with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()
        wizard.action_unmark()
        self.assertFalse(student.exit_type)
        self.assertFalse(student.exit_course_id)
        # has_graduated is permanent.
        self.assertTrue(student.has_graduated)

    # --- withdrawal wizard --------------------------------------------------

    def test_withdrawal_wizard_converts_and_cancels_enrollment(self):
        student = self._student('WW Student')
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id})
        self.assertEqual(order.state, 'draft')
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({'exit_reason': 'Moved abroad'})
        wizard.action_apply()
        # Never graduated -> withdrawal.
        self.assertEqual(student.contact_type, 'withdrawal')
        self.assertEqual(student.exit_type, 'withdrawal')
        self.assertEqual(student.exit_reason, 'Moved abroad')
        self.assertFalse(student.main_group_id)
        self.assertEqual(order.state, 'cancel')

    def test_the_wizards_reload_the_list_they_were_launched_from(self):
        """A toast alone left the old rows on screen, which reads as if nothing had
        happened — the withdrawn students even stay in a list they no longer belong to."""
        student = self._student('WW Reload')
        graduation = self.env['ems.graduation_wizard'].with_context(
            active_ids=student.ids).create({})
        withdrawal = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({})
        for action in (graduation.action_apply(), withdrawal.action_apply()):
            self.assertEqual(action['params']['next'],
                             {'type': 'ir.actions.client', 'tag': 'soft_reload'})

    def test_withdrawal_wizard_takes_a_whole_selection(self):
        """What the bulk button of the tutor list relies on: one line per selected
        student, and action_apply() walks them all."""
        first = self._student('WW Bulk One')
        second = self._student('WW Bulk Two')
        third = self.env['res.partner'].create(
            {'name': 'WW Bulk Family', 'contact_type': 'family'})
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=(first + second + third).ids).create({})
        # The family contact is filtered out: only students can be withdrawn.
        self.assertEqual(wizard.line_ids.student_id, first + second)
        wizard.action_apply()
        self.assertEqual(first.contact_type, 'withdrawal')
        self.assertEqual(second.contact_type, 'withdrawal')
        self.assertEqual(third.contact_type, 'family')

    def test_withdrawal_wizard_graduated_becomes_alumni(self):
        student = self._student('WW Grad', has_graduated=True)
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()
        self.assertEqual(student.contact_type, 'alumni')

    def test_withdrawal_wizard_expulsion_converts_to_expelled(self):
        student = self._student('WW Expelled')
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({'exit_kind': 'expulsion'})
        wizard.action_apply()
        self.assertEqual(student.contact_type, 'expelled')
        self.assertEqual(student.exit_type, 'expulsion')
        self.assertFalse(student.main_group_id)

    def test_withdrawal_wizard_expulsion_overrides_has_graduated(self):
        # Even a student who already graduated once ends up 'expelled', not 'alumni',
        # when the admin explicitly picks Expulsion - unlike the default Withdrawal path,
        # which defers entirely to has_graduated.
        student = self._student('WW Expelled Grad', has_graduated=True)
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({'exit_kind': 'expulsion'})
        wizard.action_apply()
        self.assertEqual(student.contact_type, 'expelled')

    def test_withdrawal_wizard_expulsion_archives_student(self):
        student = self._student('WW Expelled Archive')
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({'exit_kind': 'expulsion'})
        wizard.action_apply()
        self.assertFalse(student.active)

    def test_withdrawal_wizard_defaults_to_withdrawal_kind(self):
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=self._student('WW Default Kind').ids).create({})
        self.assertEqual(wizard.exit_kind, 'withdrawal')

    def test_withdrawal_wizard_archives_student(self):
        # Withdrawal now archives the student too, mirroring how an employee's
        # departure wizard archives the employee (see toggle_active override).
        student = self._student('WW Archive')
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()
        self.assertFalse(student.active)

    def test_withdrawal_wizard_skips_archive_when_portal_revoke_fails(self):
        # A failed portal revoke is logged as an issue, not raised (see
        # _ems_revoke_student_portal). If the archive ran anyway, res.partner's
        # base write() would raise "cannot archive a contact linked to an
        # active user" and abort the whole batch instead of just this student.
        student = self._student('WW Portal Fail', student_email='wwfail@example.com')
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'WW Portal Fail', 'login': 'wwfail@example.com',
            'email': 'wwfail@example.com', 'partner_id': student.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({})
        with patch.object(
            type(student), '_ems_revoke_student_portal',
            return_value={'revoked': [], 'skipped': [], 'issues': ['simulated failure']},
        ):
            result = wizard.action_apply()
        self.assertTrue(student.active)
        self.assertIn('simulated failure', result['params']['message'])

    def test_withdrawal_by_secretary_removes_from_attendance(self):
        # Regression: the secretary has no write access to attendance templates; the
        # wizard must detach the withdrawn student via sudo without raising AccessError.
        secretary = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Sec Exit', 'login': 'sec_exit',
            'groups_id': [(4, self.env.ref('ems.group_secretary').id)]})
        space_type = self.env['ems.space_type'].create({'name': 'Classroom X'})
        work_loc = self.env['hr.work.location'].create({
            'name': 'WL Exit', 'address_id': self.env.company.partner_id.id})
        space = self.env['ems.space'].create({
            'code': 'SPX', 'name': 'Space X',
            'space_type_id': space_type.id, 'work_location_id': work_loc.id})
        teacher = self.env['hr.employee'].create({
            'name': 'Teacher Exit', 'employee_type': 'teacher'})
        subject = self.env['ems.subject'].create({
            'code': 'SUBX', 'acronym': 'SBX', 'name': 'Subject X',
            'study_ids': [(6, 0, [self.study.id])]})
        template = self.env['ems.attendance_template'].create({
            'start_date': date.today(), 'end_date': date.today(),
            'teacher_ids': [(6, 0, [teacher.id])], 'level_id': self.level.id, 'study_id': self.study.id,
            'subject_id': subject.id, 'space_id': space.id,
            'group_ids': [(6, 0, [self.group.id])]})
        student = self._student('Att Withdrawal')
        template.student_ids = [(4, student.id)]
        self.assertIn(student, template.student_ids)
        wizard = self.env['ems.withdrawal_wizard'].with_user(secretary).with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()
        self.assertEqual(student.contact_type, 'withdrawal')
        self.assertNotIn(student, template.student_ids)

    def test_withdrawal_clears_operational_records(self):
        """Once the history is frozen, the withdrawal must leave nothing operational
        behind: an ex-student enrolled in the group's subjects keeps showing up in the
        evaluation matrix, in the attendance sessions and in the EM grading wizard."""
        subject = self.env['ems.subject'].create({
            'code': 'SUBW', 'acronym': 'SBW', 'name': 'Subject W',
            'study_ids': [(6, 0, [self.study.id])]})
        student = self._student('Cleanup Withdrawal')
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.group.id, 'subject_id': subject.id})
        session = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': subject.id, 'round': '1'})
        session.fill_students()
        self.assertTrue(session.grade_subject_line_ids.filtered(
            lambda line: line.student_id == student))
        self.group.delegate_id = student

        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()

        self.assertEqual(student.contact_type, 'withdrawal')
        # The history keeps what the operational records said.
        self.assertTrue(student.year_record_ids)
        self.assertFalse(self.env['ems.enrollment'].search(
            [('student_id', '=', student.id)]))
        self.assertFalse(self.env['ems.grade_subject_line'].search(
            [('student_id', '=', student.id)]))
        self.assertFalse(self.env['ems.grade_outcome_line'].search(
            [('student_id', '=', student.id)]))
        self.assertFalse(self.env['ems.attendance_session_line'].search(
            [('student_id', '=', student.id)]))
        self.assertNotIn(student, self.group.enrolled_student_ids)
        self.assertFalse(self.group.delegate_id)

    def test_gw_suspend_on_ex_student_conversion(self):
        # With Google Workspace enabled, converting a student to ex-student must be
        # able to suspend the account (the worker no longer requires contact_type=='student').
        self.env.company.write({'google_ws_enabled': True, 'google_ws_dry_run': True})
        student = self._student('GW Withdraw', student_email='gw.withdraw@elpuig.xeill.net')
        student._ems_convert_to_ex_student()
        self.assertEqual(student.contact_type, 'withdrawal')
        # Run the (dry-run) worker synchronously; the relaxed guard lets it proceed.
        student.action_suspend_google_account()
        self.assertTrue(student.google_ws_suspended)

    # --- google_ws_state (single source of truth for header buttons) --------

    def test_gw_state_none_for_non_student(self):
        contact = self.env['res.partner'].create({'name': 'GW Not A Student'})
        self.assertEqual(contact.google_ws_state, 'none')

    def test_gw_state_none_without_student_email(self):
        student = self._student('GW State None')
        self.assertEqual(student.google_ws_state, 'none')

    def test_gw_state_active(self):
        student = self._student('GW State Active', student_email='gw.state.active@elpuig.xeill.net')
        self.assertEqual(student.google_ws_state, 'active')

    def test_gw_state_suspended(self):
        student = self._student(
            'GW State Suspended', student_email='gw.state.suspended@elpuig.xeill.net',
            google_ws_suspended=True)
        self.assertEqual(student.google_ws_state, 'suspended')

    def test_revoke_portal_helper_no_relations(self):
        # Lone student with no family relations and no portal user: no crash, empty summary.
        student = self._student('RP Lone')
        summary = student._ems_revoke_student_portal()
        self.assertEqual(summary, {'revoked': [], 'skipped': [], 'issues': []})

    # --- archiving a student opens the withdrawal wizard (toggle_active) ----

    def test_toggle_active_single_student_opens_withdrawal_wizard(self):
        # Mirrors hr.employee: archiving a single student pops a reason wizard
        # instead of archiving directly. Nothing happens until it is confirmed.
        student = self._student('TA Single')
        result = student.toggle_active()
        self.assertEqual(result.get('res_model'), 'ems.withdrawal_wizard')
        self.assertEqual(result.get('context', {}).get('active_ids'), student.ids)

    def test_action_archive_single_student_opens_withdrawal_wizard(self):
        # This is what the UI actually calls (Archive button/action_menu), not
        # toggle_active() directly — must go through the same wizard.
        student = self._student('TA Action Archive Single')
        result = student.action_archive()
        self.assertEqual(result.get('res_model'), 'ems.withdrawal_wizard')
        self.assertTrue(student.active)

    def test_action_archive_multiple_students_opens_withdrawal_wizard(self):
        # Unlike hr.employee (whose wizard only pops for a single record), this
        # must also work for a multi-selection archive from the list.
        s1 = self._student('TA Action Archive 1')
        s2 = self._student('TA Action Archive 2')
        result = (s1 + s2).action_archive()
        self.assertEqual(result.get('res_model'), 'ems.withdrawal_wizard')
        self.assertEqual(set(result.get('context', {}).get('active_ids')), set((s1 + s2).ids))
        self.assertTrue(s1.active)
        self.assertTrue(s2.active)

    def test_toggle_active_mixed_recordset_archives_others_and_opens_wizard(self):
        # A recordset mixing a student with a non-student (e.g. a family contact)
        # archives the non-student directly and still opens the wizard for the
        # student — the two are independent operations bundled in one call.
        student = self._student('TA Mixed Student')
        family = self.env['res.partner'].create({
            'name': 'TA Mixed Family', 'contact_type': 'family'})
        result = (student + family).toggle_active()
        self.assertEqual(result.get('res_model'), 'ems.withdrawal_wizard')
        self.assertEqual(result.get('context', {}).get('active_ids'), student.ids)
        self.assertTrue(student.active)
        self.assertFalse(family.active)

    def test_toggle_active_non_student_archives_directly(self):
        family = self.env['res.partner'].create({
            'name': 'TA Family', 'contact_type': 'family'})
        family.toggle_active()
        self.assertFalse(family.active)

    def test_toggle_active_reactivate_no_wizard(self):
        # Unarchiving never pops the wizard, for a student or anyone else.
        # (Archived directly, as the withdrawal wizard itself would do, since a
        # lone active student going through toggle_active would just reopen
        # the wizard instead of archiving — see the single-student test above.)
        student = self._student('TA Reactivate')
        student.write({'active': False})
        result = student.toggle_active()
        self.assertTrue(student.active)
        self.assertIsNone(result)

    # --- migration: archive pre-existing alumni/withdrawal (18.0.0.22.0) -----

    @classmethod
    def _load_post_migrate_module(cls):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migrations', '18.0.0.22.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_post_migrate_18_0_0_22_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_archives_existing_alumni_and_withdrawal(self):
        alumni = self._student('Migration Alumni', contact_type='alumni')
        withdrawal = self._student('Migration Withdrawal', contact_type='withdrawal')
        # A plain (never withdrawn) student must be left untouched.
        student = self._student('Migration Untouched')

        migration = self._load_post_migrate_module()
        migration._archive_existing_ex_students(self.env)
        for partner in (alumni, withdrawal, student):
            partner.invalidate_recordset()

        self.assertFalse(alumni.active)
        self.assertFalse(withdrawal.active)
        self.assertTrue(student.active)

    def test_migration_keeps_active_when_portal_revoke_fails(self):
        alumni = self._student('Migration Portal Fail', contact_type='alumni',
                                student_email='migrationfail@example.com')
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Migration Portal Fail', 'login': 'migrationfail@example.com',
            'email': 'migrationfail@example.com', 'partner_id': alumni.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        migration = self._load_post_migrate_module()
        with patch.object(
            type(alumni), '_ems_revoke_student_portal',
            return_value={'revoked': [], 'skipped': [], 'issues': ['simulated failure']},
        ):
            migration._archive_existing_ex_students(self.env)
        self.assertTrue(alumni.active)

    # --- migration: backfill google_ws_suspended (18.0.0.22.0) ---------------

    def test_migration_backfills_suspended_for_alumni_and_withdrawal(self):
        alumni = self._student('Migration GW Alumni', contact_type='alumni',
                                student_email='migration.gw.alumni@example.com')
        withdrawal = self._student('Migration GW Withdrawal', contact_type='withdrawal',
                                    student_email='migration.gw.withdrawal@example.com')
        # No corporate email yet: nothing to mark as suspended.
        no_email = self._student('Migration GW No Email', contact_type='withdrawal')
        # Still an active student: must be left untouched.
        active_student = self._student('Migration GW Untouched',
                                        student_email='migration.gw.active@example.com')

        migration = self._load_post_migrate_module()
        migration._backfill_google_ws_suspended(self.env)
        for partner in (alumni, withdrawal, no_email, active_student):
            partner.invalidate_recordset()

        self.assertTrue(alumni.google_ws_suspended)
        self.assertTrue(withdrawal.google_ws_suspended)
        self.assertFalse(no_email.google_ws_suspended)
        self.assertFalse(active_student.google_ws_suspended)
