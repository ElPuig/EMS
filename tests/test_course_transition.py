import base64
from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCourseTransition(TransactionCase):
    """Fase 6: course transition wizard — 'ems.study.transition_state', the
    latecomer branch it activates in 'sale.order._ems_admit_student()' and the
    dry-run preview (blockers, warnings and scope)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The apply revokes portal access, which walks the whole mail stack. This
        # database carries real credentialed SMTP servers, so the transport is mocked:
        # every recipient-resolution path still runs, nothing ever leaves the machine.
        mail_patch = patch('odoo.addons.base.models.ir_mail_server.IrMailServer.send_email')
        mail_patch.start()
        cls.addClassCleanup(mail_patch.stop)

        Course = cls.env['ems.course']
        cls.source_course = Course.create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = cls.source_course
        cls.target_course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})

        cls.level = cls.env['ems.level'].create({'acronym': 'CTWL', 'name': 'Transition Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'CTW001', 'acronym': 'CTWS', 'name': 'Transition Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id})
        # A second study, deliberately left OUT of every preview scope: proves the
        # wizard never reaches beyond study_ids, and keeps the global flip pending.
        cls.study_other = cls.env['ems.study'].create({
            'code': 'CTW002', 'acronym': 'CTWO', 'name': 'Transition Study Other',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id})

        # Subject with a work placement weight (90/10) and one internal-only (100/0).
        cls.subject_ext = cls.env['ems.subject'].create({
            'code': 'CTWSUB1', 'acronym': 'CTW1', 'name': 'Transition Subject Ext',
            'study_ids': [(4, cls.study.id)]})
        cls.subject_int = cls.env['ems.subject'].create({
            'code': 'CTWSUB2', 'acronym': 'CTW2', 'name': 'Transition Subject Int',
            'study_ids': [(4, cls.study.id)]})
        cls.outcome_ext = cls.env['ems.outcome'].create({
            'code': 'CTWSUB1_01RA', 'acronym': 'RA1', 'name': 'Outcome Ext',
            'subject_id': cls.subject_ext.id})
        cls.outcome_int = cls.env['ems.outcome'].create({
            'code': 'CTWSUB2_01RA', 'acronym': 'RA1', 'name': 'Outcome Int',
            'subject_id': cls.subject_int.id})
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject_ext.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome_ext.id, 'ponderation': 100.0})]})
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject_int.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome_int.id, 'ponderation': 100.0})]})

        cls.group1 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.group2 = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.group_other = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study_other.id})

        cls.teacher = cls.env['hr.employee'].create({
            'name': 'CTW Teacher', 'employee_type': 'teacher'})
        space_type = cls.env['ems.space_type'].create({'name': 'CTW Space Type'})
        work_location = cls.env['hr.work.location'].create({
            'name': 'CTW Work Location', 'address_id': cls.env.company.partner_id.id})
        cls.space = cls.env['ems.space'].create({
            'code': 'CTW-SPACE', 'name': 'CTW Space',
            'space_type_id': space_type.id, 'work_location_id': work_location.id})

    # --- helpers -------------------------------------------------------------

    def _template(self, groups):
        return self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject_int.id,
            'group_ids': [(6, 0, [group.id for group in groups])],
            'start_date': date(2020, 1, 1), 'end_date': date(2098, 12, 31),
        })

    def _calendar_block(self, calendar, groups, weekday='0', hour_from=9.0, hour_to=10.0, subject=None):
        # 'subject' defaults to the same subject '_template()' always uses - a real teaching
        # block always carries both 'subject_id'/'group_ids' together (see
        # 'ems.attendance_mixin.find_schedule_lines_for_teaching', matched by teacher+subject+
        # group overlap, no longer by weekday/time/room - a block missing its own subject would
        # never match any template's schedule line).
        return self.env['resource.calendar.attendance'].create({
            'calendar_id': calendar.id, 'name': 'Test Block (Course Transition)',
            'dayofweek': weekday, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            'subject_id': (subject or self.subject_int).id,
            'group_ids': [group.id for group in groups],
        })

    def _attendance_issue(self, student):
        tutor_issue = self.env['ems.attendance_issue_tutor'].create({
            'tutor_id': self.teacher.id, 'issue_date': date(2026, 5, 1)})
        return self.env['ems.attendance_issue_student'].create({
            'attendance_issue_tutor_id': tutor_issue.id, 'student_id': student.id})


    def _student(self, name, group=None, **vals):
        return self.env['res.partner'].create(dict(
            {'name': name, 'contact_type': 'student',
             'main_group_id': (group or self.group1).id}, **vals))

    def _order(self, partner, group=None, state=None, course=None):
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'ems_study_id': self.study.id,
            'ems_course_id': (course or self.target_course).id,
            'ems_group_id': group.id if group else False,
            'shift': 'morning',
        })
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        if state == 'sale':
            order.action_confirm()
        elif state:
            order.state = state
        return order

    def _session(self, group, subject, round="1", state='final'):
        session = self.env['ems.grade_session'].create({
            'group_id': group.id, 'subject_id': subject.id, 'round': round})
        session.state = state
        return session

    def _graduate(self, name='CTW Graduate', **vals):
        """A student the graduation wizard has already marked for the outgoing course."""
        return self._student(name, group=self.group2, exit_type='graduation',
                             exit_course_id=self.source_course.id, has_graduated=True, **vals)

    def _applied(self, studies=None, **vals):
        """Preview + apply, the only supported sequence."""
        wizard = self._wizard(studies, backup_done=True, **vals)
        wizard.action_preview()
        wizard.action_apply()
        return wizard

    def _wizard(self, studies=None, **vals):
        return self.env['ems.course_transition_wizard'].create(dict({
            'source_course_id': self.source_course.id,
            'target_course_id': self.target_course.id,
            'study_ids': [(6, 0, (studies or self.study).ids)],
        }, **vals))

    def _scored(self, student, group, subject, outcome, state='final'):
        """Enroll, open a session and score every RA of 'subject' for 'student'."""
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': group.id, 'subject_id': subject.id})
        session = self._session(group, subject, state='open')
        session.fill_students()
        session.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == student and line.outcome_id == outcome
        ).write({'score': 7, 'is_scored': True})
        session.state = state
        return session

    # --- ems.study.transition_state -----------------------------------------

    def test_transition_state_defaults_to_active(self):
        self.assertEqual(self.study.transition_state, 'active')

    def test_transition_state_is_not_copied(self):
        """A duplicated study must start its own life as 'active', never inherit
        the transitioned mark of the study it was copied from."""
        self.assertFalse(self.env['ems.study']._fields['transition_state'].copy)
        self.study.transition_state = 'transitioned'
        # 'code' is unique - override it so this copy doesn't collide with the
        # original; not what this test is about, just what copy() needs here.
        self.assertEqual(self.study.copy({'code': 'CTW001-COPY'}).transition_state, 'active')

    # --- latecomer branch of _ems_admit_student() ---------------------------

    def test_latecomer_is_placed_when_study_transitioned(self):
        """Once the study has been transitioned, the bulk placement has already
        run, so a late confirmation must place the student on its own."""
        self.study.transition_state = 'transitioned'
        applicant = self.env['res.partner'].create({
            'name': 'CTW Latecomer', 'contact_type': 'applicant', 'study_id': self.study.id})
        self._order(applicant, self.group1)._ems_admit_student()
        self.assertEqual(applicant.contact_type, 'student')
        self.assertEqual(applicant.main_group_id, self.group1)
        self.assertEqual(applicant.enrollment_ids.mapped('subject_id'), self.subject_int)

    def test_no_placement_while_study_active(self):
        """The mirror case: while the study is still active the transition wizard
        has not run yet, so placement is left to the bulk step."""
        applicant = self.env['res.partner'].create({
            'name': 'CTW Early', 'contact_type': 'applicant', 'study_id': self.study.id})
        self._order(applicant, self.group1)._ems_admit_student()
        self.assertEqual(applicant.contact_type, 'student')
        self.assertFalse(applicant.main_group_id)
        self.assertFalse(applicant.enrollment_ids)

    # --- preview: blockers ---------------------------------------------------

    def test_blocks_when_target_is_the_source_course(self):
        wizard = self._wizard(target_course_id=self.source_course.id)
        wizard.action_preview()
        self.assertTrue(wizard.has_blockers)

    def test_does_not_block_a_graduate_enrolled_in_the_target_course(self):
        """Finishing a study and enrolling into another one are independent facts:
        a CFGM graduate moving up to a CFGS does both at once."""
        graduate = self._graduate()
        self._order(graduate, self.group1, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)

    def test_blocks_when_the_last_round_is_not_final(self):
        self._session(self.group1, self.subject_int, round="1", state='open')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertTrue(wizard.has_blockers)

    def test_does_not_block_when_only_an_earlier_round_is_open(self):
        """Only the LAST round has to be closed: an earlier one left open is the
        normal state of affairs once a later round exists."""
        self._session(self.group1, self.subject_int, round="1", state='open')
        self._session(self.group1, self.subject_int, round="2", state='final')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)

    def test_sessions_of_a_study_out_of_scope_do_not_block(self):
        self._session(self.group_other, self.subject_int, round="1", state='open')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)

    # --- preview: warnings and lines ----------------------------------------

    def test_lists_students_with_no_destination(self):
        """D8: students with no enrollment for the next course are listed one by
        one, so the withdrawal decisions are on screen when the run finishes."""
        stranded = self._student('CTW Stranded')
        placed = self._student('CTW Placed')
        self._order(placed, self.group2, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        missing = wizard.line_ids.filtered(lambda line: line.action == 'missing')
        self.assertEqual(missing.student_id, stranded)
        self.assertEqual(wizard.missing_count, 1)

    def test_lists_confirmed_enrollment_without_group_as_unplaced(self):
        student = self._student('CTW Unplaced')
        self._order(student, group=False, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        unplaced = wizard.line_ids.filtered(lambda line: line.action == 'unplaced')
        self.assertEqual(unplaced.student_id, student)

    def _enrollment_flow(self):
        """Make the study use the enrollment flow. uses_enrollment_flow keys on having
        an active sale.order.template, which this fixture deliberately has none of —
        ESO and BTX are exactly that case in production."""
        return self.env['sale.order.template'].create({
            'name': 'CTW Flow Template', 'ems_study_id': self.study.id, 'study_year': 1})

    def test_blocks_a_student_with_no_enrollment_when_the_study_uses_the_flow(self):
        """Settle them BEFORE the freeze: afterwards the student has no group, and the
        graduation wizard needs it to tell whether they are in the last course, so
        graduating them becomes impossible."""
        self._enrollment_flow()
        stranded = self._student('CTW Flow Stranded', group=self.group2)
        wizard = self._wizard()
        wizard.action_preview()
        self.assertTrue(wizard.has_blockers)
        self.assertIn(stranded.display_name, wizard.blocking_html)
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_does_not_block_a_student_with_no_enrollment_without_the_flow(self):
        """ESO and BTX do not enroll through sale.order: 478 of 493 ESO students have
        no enrollment, and that is the expected state until the September re-import."""
        stranded = self._student('CTW No Flow Stranded', group=self.group2)
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)
        self.assertEqual(wizard.missing_count, 1)
        self.assertIn(stranded.display_name, wizard.warning_html)

    def test_a_draft_enrollment_clears_the_no_enrollment_blocker(self):
        """An offer nobody has confirmed still means somebody looked at the student."""
        self._enrollment_flow()
        student = self._student('CTW Flow Offered', group=self.group2)
        self._order(student, self.group1)
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)
        line = wizard.line_ids.filtered(lambda line: line.student_id == student)
        self.assertEqual(line.action, 'pending')

    def test_lists_an_unconfirmed_enrollment_as_pending(self):
        """The preview used to promise 'joins its group' for anybody whose enrollment
        carried one, confirmed or not — but step 3 only executes confirmed ones, so
        the counter the operator reads before applying was overstating the placement."""
        student = self._student('CTW Pending Order')
        self._order(student, self.group2, state='sent')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == student)
        self.assertEqual(line.action, 'pending')
        self.assertEqual(wizard.pending_count, 1)
        self.assertEqual(wizard.place_count, 0)

    def test_an_unconfirmed_enrollment_without_group_is_pending_too(self):
        """Not 'unplaced': that one blocks the run, and an offer nobody has confirmed
        must not, since there is nothing to place either way."""
        student = self._student('CTW Pending No Group')
        self._order(student, group=False, state='sent')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == student)
        self.assertEqual(line.action, 'pending')
        self.assertEqual(wizard.unplaced_count, 0)
        self.assertFalse(wizard.has_blockers)

    def test_place_counts_only_what_the_apply_will_really_move(self):
        confirmed = self._student('CTW Really Placed')
        self._order(confirmed, self.group2, state='sale')
        unconfirmed = self._student('CTW Not Yet')
        self._order(unconfirmed, self.group2, state='sent')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertEqual(wizard.place_count, 1)
        self.assertEqual(wizard.pending_count, 1)
        wizard.backup_done = True
        wizard.action_apply()
        self.assertEqual(confirmed.main_group_id, self.group2)
        self.assertFalse(unconfirmed.main_group_id)

    def test_a_confirmed_enrollment_elsewhere_is_not_labelled_as_placed(self):
        """A confirmed enrollment into a study this run is not transitioning is not
        executed here (_apply_placement filters by study_ids), so calling it 'place'
        promised a move that never happened — in the preview and, worse, in the audit
        CSV that is the reference for undoing a case by hand. Reproduced twice during
        the first full rehearsal: 17 students shown as placed came out with no group."""
        student = self._student('CTW Elsewhere')
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study_other.id,
            'ems_course_id': self.target_course.id, 'ems_group_id': self.group_other.id,
            'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        order.action_confirm()
        wizard = self._wizard(studies=self.study)
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == student)
        self.assertEqual(line.action, 'place_later')
        self.assertFalse(line.destination_group_id)
        self.assertEqual(wizard.place_count, 0)
        self.assertEqual(wizard.place_later_count, 1)
        self.assertIn(student.display_name, wizard.warning_html)
        wizard.backup_done = True
        wizard.action_apply()
        self.assertFalse(student.main_group_id)

    def test_preview_warns_about_students_with_no_group_at_all(self):
        """The scope is captured through main_group_id, so an active student with no group
        belongs to no run whatever studies are picked: no year record is frozen for them and
        their operational records are never cleaned. The wizard used to hide that instead of
        surfacing it — the first full rehearsal ended with 8 such students holding 197
        attendance lines and no academic record for the year."""
        # Relative to a baseline: the working database legitimately carries its own
        # orphans (the rehearsal found 8), and this test is about detecting one more.
        baseline = self._wizard()
        baseline.action_preview()
        before = baseline.orphan_count
        orphan = self.env['res.partner'].create(
            {'name': 'CTW No Group At All', 'contact_type': 'student'})
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.line_ids.filtered(lambda line: line.student_id == orphan))
        self.assertEqual(wizard.orphan_count, before + 1)

    def test_preview_does_not_warn_about_students_detached_by_an_earlier_run(self):
        """They keep study_id on purpose (_apply_detach_unplaced), which is exactly what
        tells them apart: after transitioning ESO/BTX/AO first there are hundreds of
        group-less students whose history IS frozen, and warning about those would bury the
        handful that are really unaccounted for."""
        baseline = self._wizard()
        baseline.action_preview()
        before = baseline.orphan_count
        detached = self._student('CTW Detached', group=self.group1)
        detached.write({'main_group_id': False, 'study_id': self.study.id})
        wizard = self._wizard()
        wizard.action_preview()
        self.assertEqual(wizard.orphan_count, before)
        self.assertNotIn(detached.display_name, wizard.warning_html)

    def test_incomplete_evaluation_ignores_the_missing_em_before_the_last_course(self):
        """D9: the work placement only exists in the last course, so a first-course
        subject with an external weight but no EM grade is NOT incomplete — its
        promotion is decided by the internal grade alone."""
        student = self._student('CTW First Course')
        self._scored(student, self.group1, self.subject_ext, self.outcome_ext)
        wizard = self._wizard()
        wizard.action_preview()
        self.assertEqual(wizard.incomplete_evaluation_count, 0)

    def test_incomplete_evaluation_demands_the_em_in_the_last_course(self):
        """The mirror of the rule above: in the last course the external part is
        genuinely due, so the very same subject counts as incomplete without it."""
        student = self._student('CTW Last Course', group=self.group2)
        self._scored(student, self.group2, self.subject_ext, self.outcome_ext)
        wizard = self._wizard()
        wizard.action_preview()
        self.assertEqual(wizard.incomplete_evaluation_count, 1)

    def test_preview_reports_the_studies_left_pending(self):
        """The global course flip only happens when no study stays active."""
        wizard = self._wizard()
        wizard.action_preview()
        self.assertFalse(wizard.will_flip)
        self.assertIn(self.study_other, wizard.pending_study_ids)

    # --- preview is a dry run -----------------------------------------------

    def test_preview_writes_nothing(self):
        graduate = self._graduate('CTW Dry Graduate')
        placed = self._student('CTW Dry Placed')
        self._order(placed, self.group2, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertEqual(graduate.contact_type, 'student')
        self.assertTrue(graduate.active)
        self.assertEqual(placed.main_group_id, self.group1)
        self.assertEqual(self.study.transition_state, 'active')
        self.assertEqual(self.env.company.current_course_id, self.source_course)

    def test_apply_refuses_without_the_backup_checkbox(self):
        wizard = self._wizard()
        wizard.action_preview()
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_apply_refuses_before_the_preview(self):
        with self.assertRaises(UserError):
            self._wizard(backup_done=True).action_apply()

    def test_apply_refuses_while_there_are_blockers(self):
        self._session(self.group1, self.subject_int, round="1", state='open')
        wizard = self._wizard(backup_done=True)
        wizard.action_preview()
        with self.assertRaises(UserError):
            wizard.action_apply()

    # --- apply step 0: academic history --------------------------------------

    def test_apply_freezes_the_history_of_the_whole_scope(self):
        """Captured by group, so a stranded student gets its record too."""
        placed = self._student('CTW Hist Placed')
        self._order(placed, self.group2, state='sale')
        stranded = self._student('CTW Hist Stranded')
        self._applied()
        for student in (placed, stranded):
            self.assertEqual(student.year_record_ids.mapped('course_id'), self.source_course)

    def test_apply_aborts_when_the_history_fails(self):
        """Step 0 gates everything: without a frozen history nothing may be
        converted, because step 8 would later delete the live records."""
        graduate = self._graduate('CTW Abort Graduate')
        target = 'odoo.addons.ems.models.grades.year_record.EmsStudentYearRecord.generate_for_students'
        with patch(target, side_effect=ValueError('boom')):
            with self.assertRaises(UserError):
                self._applied()
        self.assertEqual(graduate.contact_type, 'student')
        self.assertTrue(graduate.active)

    # --- graduates who stay at the centre ------------------------------------

    def test_preview_labels_a_graduate_with_a_confirmed_order_as_continuing(self):
        graduate = self._graduate('CTW Continuing')
        self._order(graduate, self.group1, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == graduate)
        self.assertEqual(line.action, 'graduate_continue')
        self.assertEqual(line.destination_group_id, self.group1)
        self.assertEqual(wizard.graduate_continue_count, 1)
        self.assertEqual(wizard.graduate_count, 0)

    def test_preview_labels_a_graduate_with_an_unconfirmed_order_as_pending(self):
        """An offer still on the table is neither a placement nor a departure."""
        graduate = self._graduate('CTW Pending Sent')
        self._order(graduate, self.group1, state='sent')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == graduate)
        self.assertEqual(line.action, 'graduate_pending')
        self.assertFalse(line.destination_group_id)
        self.assertEqual(wizard.graduate_pending_count, 1)
        self.assertEqual(wizard.graduate_count, 0)
        self.assertEqual(wizard.graduate_continue_count, 0)

    def test_apply_turns_a_graduate_pending_confirmation_into_an_applicant(self):
        """#357 archives every alumnus, and Odoo refuses to archive a contact with an
        active portal user — so an alumnus has no portal and could not confirm the
        offer. 'applicant' already models exactly this situation."""
        graduate = self._graduate('CTW Pending Applicant')
        self._order(graduate, self.group1, state='sent')
        self._applied()
        self.assertEqual(graduate.contact_type, 'applicant')
        self.assertTrue(graduate.active)
        self.assertFalse(graduate.exit_type)
        self.assertTrue(graduate.has_graduated)

    def test_apply_keeps_the_portal_of_a_graduate_pending_confirmation(self):
        """Without portal there is no /my/gestion-matriculas, and the offer could
        never be confirmed."""
        graduate = self._graduate('CTW Pending Portal', email='ctw.pending@example.com')
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'CTW Pending User', 'login': 'ctw_pending_user',
            'partner_id': graduate.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self._order(graduate, self.group1, state='sent')
        self._applied()
        self.assertTrue(graduate._has_active_portal_user())
        self.assertTrue(graduate.active)

    def test_pending_graduate_takes_the_study_of_its_destination(self):
        """So it is indistinguishable from any other applicant of that study."""
        graduate = self._graduate('CTW Pending Study')
        order = self.env['sale.order'].create({
            'partner_id': graduate.id, 'ems_study_id': self.study_other.id,
            'ems_course_id': self.target_course.id, 'ems_group_id': self.group_other.id,
            'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        order.state = 'sent'
        self._applied()
        self.assertEqual(graduate.contact_type, 'applicant')
        self.assertEqual(graduate.study_id, self.study_other)

    def test_preview_labels_a_graduate_without_any_order_as_leaving(self):
        graduate = self._graduate('CTW Leaving')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == graduate)
        self.assertEqual(line.action, 'graduate')
        self.assertEqual(wizard.graduate_count, 1)
        self.assertEqual(wizard.graduate_continue_count, 0)

    def test_apply_keeps_a_continuing_graduate_active_and_places_it(self):
        graduate = self._graduate('CTW Continuing Placed')
        self._order(graduate, self.group1, state='sale')
        self._applied()
        self.assertTrue(graduate.active)
        self.assertEqual(graduate.contact_type, 'student')
        self.assertEqual(graduate.main_group_id, self.group1)

    def test_apply_clears_the_exit_metadata_of_a_continuing_graduate(self):
        """Point 4: an active student of the incoming course must not carry the
        exit date of the study it has just finished. has_graduated is permanent."""
        graduate = self._graduate('CTW Continuing Exit')
        self._order(graduate, self.group1, state='sale')
        self._applied()
        self.assertFalse(graduate.exit_type)
        self.assertFalse(graduate.exit_course_id)
        self.assertTrue(graduate.has_graduated)

    def test_apply_freezes_the_year_record_before_clearing_the_exit_metadata(self):
        """Load-bearing order: year_record._generate_one() stamps the exit through
        'exit_course_id', so step 0 has to run before the metadata is cleared."""
        graduate = self._graduate('CTW Continuing History')
        self._order(graduate, self.group1, state='sale')
        self._applied()
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', graduate.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.exit_type, 'graduation')
        self.assertEqual(record.group_id, self.group2)

    def test_a_pending_graduate_keeps_the_record_frozen_before_the_conversion(self):
        """Step 0 freezes the whole scope before step 2d turns anybody into an
        applicant, so the record is written while the student still has its group."""
        graduate = self._graduate('CTW Pending History')
        self._scored(graduate, self.group2, self.subject_int, self.outcome_int)
        self._order(graduate, self.group1, state='sent')
        self._applied()
        self.assertEqual(graduate.contact_type, 'applicant')
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', graduate.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.group_id, self.group2)
        self.assertTrue(record.subject_record_ids)

    def test_an_unconfirmed_offer_leaves_a_non_graduate_as_a_student(self):
        """Only GRADUATES holding an unconfirmed offer become applicants. Everybody
        else keeps being a student — they simply lose the group until they confirm."""
        student = self._student('CTW Pending Student', group=self.group2)
        self._scored(student, self.group2, self.subject_int, self.outcome_int)
        self._order(student, self.group1, state='sent')
        self._applied()
        self.assertEqual(student.contact_type, 'student')
        self.assertFalse(student.main_group_id)
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(record.group_id, self.group2)
        self.assertTrue(record.subject_record_ids)

    def test_a_destination_outside_the_run_is_not_promised(self):
        """Each run only places into its OWN studies (_incoming_orders filters by
        study_ids), so showing the destination group of a student heading elsewhere
        promised a move this run never makes — and step 4b then detaches them."""
        graduate = self._graduate('CTW Cross Promise')
        order = self.env['sale.order'].create({
            'partner_id': graduate.id, 'ems_study_id': self.study_other.id,
            'ems_course_id': self.target_course.id, 'ems_group_id': self.group_other.id,
            'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        order.action_confirm()
        wizard = self._wizard(studies=self.study)
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == graduate)
        self.assertEqual(line.action, 'graduate_continue')
        self.assertFalse(line.destination_group_id)
        self.assertIn(graduate.display_name, wizard.warning_html)
        wizard.backup_done = True
        wizard.action_apply()
        self.assertFalse(graduate.main_group_id)
        self.assertEqual(graduate.contact_type, 'student')

    def test_a_destination_inside_the_run_is_still_promised(self):
        graduate = self._graduate('CTW Same Study Promise')
        self._order(graduate, self.group1, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == graduate)
        self.assertEqual(line.destination_group_id, self.group1)

    def test_apply_still_archives_a_graduate_with_no_enrollment(self):
        graduate = self._graduate('CTW Leaving Archived')
        self._applied()
        self.assertEqual(graduate.contact_type, 'alumni')
        self.assertFalse(graduate.active)

    def test_a_graduate_continuing_into_another_study_is_not_archived(self):
        """Point 1: the case is not exclusive to CFGM. A CFGS graduate enrolling
        into a different CFGS, even of another family, is the same situation."""
        graduate = self._graduate('CTW Cross Study')
        order = self.env['sale.order'].create({
            'partner_id': graduate.id, 'ems_study_id': self.study_other.id,
            'ems_course_id': self.target_course.id, 'ems_group_id': self.group_other.id,
            'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        order.action_confirm()
        self._applied(studies=self.study | self.study_other)
        self.assertTrue(graduate.active)
        self.assertEqual(graduate.main_group_id, self.group_other)

    def test_a_pending_graduate_becomes_a_student_again_when_it_confirms(self):
        """The offer survives the transition (only the OUTGOING course is cancelled)
        and the applicant path takes the graduate back in, exactly as it does for an
        outsider who preinscribed."""
        graduate = self._graduate('CTW September')
        order = self._order(graduate, self.group1, state='sent')
        self._applied()
        self.assertEqual(order.state, 'sent')
        self.assertEqual(graduate.contact_type, 'applicant')
        self.assertTrue(graduate.active)
        order.action_confirm()
        self.assertEqual(graduate.contact_type, 'student')
        self.assertEqual(graduate.main_group_id, self.group1)
        self.assertTrue(graduate.has_graduated)

    def test_admit_student_reactivates_an_archived_ex_student(self):
        """A genuine returner: archived last year, enrolls again. The individual
        path has to convert and unarchive, exactly as the bulk placement does."""
        self.study.transition_state = 'transitioned'
        returner = self._student('CTW Returner', group=self.group2,
                                 has_graduated=True)
        returner._ems_convert_to_ex_student()
        returner.active = False
        order = self._order(returner, self.group1)
        order.action_confirm()
        self.assertTrue(returner.active)
        self.assertEqual(returner.contact_type, 'student')
        self.assertEqual(returner.main_group_id, self.group1)

    # --- history frozen on the way out of the group --------------------------

    def _cross_order(self, student):
        """Confirmed enrollment into the OTHER study, so the student is placed by a
        run that does not have its own study in scope."""
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study_other.id,
            'ems_course_id': self.target_course.id, 'ems_group_id': self.group_other.id,
            'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        return order

    def test_placement_freezes_the_origin_history_of_a_student_from_another_study(self):
        """Ordering the runs is not enough: with ASIX->DAM and DAM->ASIX the same
        year no order works, so the history is frozen on the way out of the group."""
        student = self._student('CTW Cross History', group=self.group2)
        self._cross_order(student).action_confirm()
        self._applied(studies=self.study_other)
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.group_id, self.group2)
        self.assertEqual(record.study_id, self.study)
        self.assertEqual(student.main_group_id, self.group_other)

    def test_the_origin_history_survives_the_transition_of_its_own_study(self):
        """The record frozen on the way out is not overwritten, and not duplicated,
        when the origin study transitions afterwards."""
        student = self._student('CTW Cross Later', group=self.group2)
        self._cross_order(student).action_confirm()
        self._applied(studies=self.study_other)
        self._applied(studies=self.study)
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.group_id, self.group2)

    def test_blocks_when_the_origin_study_of_a_placement_is_still_evaluating(self):
        """Freezing a history half-way is worse than refusing to run."""
        student = self._student('CTW Cross Open', group=self.group2)
        self._cross_order(student).action_confirm()
        self._session(self.group2, self.subject_int, round="1", state='open')
        wizard = self._wizard(studies=self.study_other)
        wizard.action_preview()
        self.assertTrue(wizard.has_blockers)
        self.assertIn(self.study.display_name, wizard.blocking_html)

    def test_does_not_block_when_the_origin_study_is_in_the_same_run(self):
        """A study inside the scope is already covered by the last-round blocker."""
        student = self._student('CTW Cross Same Run', group=self.group2)
        self._cross_order(student).action_confirm()
        wizard = self._wizard(studies=self.study | self.study_other)
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)

    def test_cleanup_clears_the_enrollments_of_the_outgoing_groups(self):
        """A student already placed out by another study's run is no longer in
        _scope_students(), so its old subject enrollments go by group instead."""
        student = self._student('CTW Cross Enrollment', group=self.group2)
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.group2.id,
            'subject_id': self.subject_int.id})
        self._cross_order(student).action_confirm()
        self._applied(studies=self.study_other)
        self._applied(studies=self.study)
        self.assertFalse(self.env['ems.enrollment'].search_count([
            ('group_id', '=', self.group2.id)]))

    # --- apply steps 1-2: graduates ------------------------------------------

    def test_apply_converts_graduates_to_alumni(self):
        graduate = self._graduate('CTW Alumni')
        self._applied()
        self.assertEqual(graduate.contact_type, 'alumni')
        self.assertFalse(graduate.main_group_id)

    def test_apply_archives_the_graduates(self):
        """D4: alumni are archived, same as withdrawals (issue #357)."""
        graduate = self._graduate('CTW Archived')
        self._applied()
        self.assertFalse(graduate.active)

    def test_apply_revokes_the_portal_before_archiving(self):
        """res.partner.write() refuses to archive a contact still linked to an
        active portal user, so the order of steps 2 and 2b is load-bearing."""
        graduate = self._graduate('CTW Portal', email='ctw.portal@example.com')
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'CTW Portal User', 'login': 'ctw_portal_user',
            'partner_id': graduate.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.assertTrue(graduate._has_active_portal_user())
        self._applied()
        self.assertFalse(graduate._has_active_portal_user())
        self.assertFalse(graduate.active)

    def test_apply_ignores_a_graduation_marked_for_another_course(self):
        """A mark carrying a different exit course belongs to another transition."""
        other_course = self.env['ems.course'].create({'start': 2050, 'end': 2051})
        stale = self._student('CTW Stale Graduate', group=self.group2,
                              exit_type='graduation', exit_course_id=other_course.id,
                              has_graduated=True)
        self._applied()
        self.assertEqual(stale.contact_type, 'student')
        self.assertTrue(stale.active)

    def test_apply_leaves_studies_out_of_scope_untouched(self):
        outsider = self._student('CTW Outsider', group=self.group_other,
                                 exit_type='graduation', exit_course_id=self.source_course.id,
                                 has_graduated=True)
        self._applied()
        self.assertEqual(outsider.contact_type, 'student')
        self.assertTrue(outsider.active)
        self.assertFalse(outsider.year_record_ids)

    def test_apply_is_idempotent_on_graduates(self):
        graduate = self._graduate('CTW Twice')
        self._applied()
        self._applied()
        self.assertEqual(graduate.contact_type, 'alumni')
        self.assertFalse(graduate.active)

    # --- apply steps 3-4: placement and subject enrollments ------------------

    def test_apply_detaches_a_student_with_no_destination(self):
        """Groups are reused year after year, so a student left pointing at the
        outgoing group turns up next September inside the new cohort."""
        stranded = self._student('CTW Detach Missing', group=self.group2)
        self._applied()
        self.assertFalse(stranded.main_group_id)
        self.assertEqual(stranded.contact_type, 'student')
        self.assertTrue(stranded.active)

    def test_apply_detaches_a_student_whose_offer_is_not_confirmed(self):
        stranded = self._student('CTW Detach Unplaced', group=self.group2)
        self._order(stranded, group=None, state='sent')
        self._applied()
        self.assertFalse(stranded.main_group_id)

    def test_apply_detaches_a_graduate_whose_enrollment_is_not_confirmed(self):
        graduate = self._graduate('CTW Detach Pending')
        self._order(graduate, self.group1, state='sent')
        self._applied()
        self.assertFalse(graduate.main_group_id)
        self.assertEqual(graduate.contact_type, 'applicant')
        self.assertTrue(graduate.has_graduated)

    def test_apply_keeps_the_group_of_a_student_promoted_within_the_same_study(self):
        """The detach must key on who was actually placed, not on 'still sitting in a
        group of the scope': promoting 1st to 2nd year lands in a scope group too."""
        promoted = self._student('CTW Detach Promoted', group=self.group1)
        self._order(promoted, self.group2, state='sale')
        self._applied()
        self.assertEqual(promoted.main_group_id, self.group2)

    def test_apply_detaches_a_student_whose_destination_study_runs_later(self):
        """Its order is not in _incoming_orders() of this run, so nobody places it
        here; it stays groupless until its destination study transitions."""
        crossing = self._student('CTW Detach Crossing', group=self.group2)
        order = self.env['sale.order'].create({
            'partner_id': crossing.id, 'ems_study_id': self.study_other.id,
            'ems_course_id': self.target_course.id, 'ems_group_id': self.group_other.id,
            'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': self.subject_int.product_id.id})]
        order.action_confirm()
        self._applied(studies=self.study)
        self.assertFalse(crossing.main_group_id)
        self._applied(studies=self.study_other)
        self.assertEqual(crossing.main_group_id, self.group_other)

    def test_a_latecomer_is_placed_after_the_course_has_flipped(self):
        """The flip puts every study back to 'active', so keying the individual
        placement on transition_state alone left the normal end state — everything
        transitioned — unable to place anybody."""
        late = self._student('CTW Late After Flip', group=self.group2)
        order = self._order(late, self.group1, state='sent')
        self._transition_everything_else()
        self._applied()
        self.assertEqual(self.env.company.current_course_id, self.target_course)
        self.assertEqual(self.study.transition_state, 'active')
        order.action_confirm()
        self.assertEqual(late.main_group_id, self.group1)

    def test_filling_the_group_of_a_confirmed_enrollment_places_the_student(self):
        """action_confirm() cannot be run twice ('Some orders are not in a state
        requiring confirmation'), so without this the repair was impossible."""
        student = self._student('CTW Late Group', group=self.group2)
        order = self._order(student, group=None, state='sale')
        self.study.transition_state = 'transitioned'
        student.main_group_id = False
        order.ems_group_id = self.group1
        self.assertEqual(student.main_group_id, self.group1)
        self.assertEqual(student.enrollment_ids.mapped('subject_id'), self.subject_int)

    def test_filling_the_group_does_not_move_an_already_placed_student(self):
        """_ems_apply_destination_placement() creates the new group's enrollments but
        does not remove the old ones, so re-pointing a placed student would leave it
        enrolled in two groups at once. Moving somebody is a different operation."""
        student = self._student('CTW Already Placed', group=self.group2)
        order = self._order(student, self.group1, state='sale')
        self.study.transition_state = 'transitioned'
        order._ems_apply_destination_placement()
        self.assertEqual(student.main_group_id, self.group1)
        order.ems_group_id = self.group2
        self.assertEqual(student.main_group_id, self.group1)

    def test_apply_places_the_student_in_its_destination_group(self):
        student = self._student('CTW Promoted')
        self._order(student, self.group2, state='sale')
        self._applied()
        self.assertEqual(student.main_group_id, self.group2)
        self.assertEqual(student.enrollment_ids.mapped('subject_id'), self.subject_int)

    def test_apply_syncs_study_and_level_with_the_destination_group(self):
        """Study and level are stored fields, not derived from the group: without
        an explicit sync a student would keep pointing at the previous study."""
        student = self._student('CTW Synced')
        student.write({'study_id': self.study_other.id, 'level_id': False})
        self._order(student, self.group2, state='sale')
        self._applied()
        self.assertEqual(student.study_id, self.study)
        self.assertEqual(student.level_id, self.level)

    def test_apply_converts_an_applicant_before_placing_it(self):
        applicant = self.env['res.partner'].create({
            'name': 'CTW Incoming', 'contact_type': 'applicant', 'study_id': self.study.id})
        self._order(applicant, self.group1, state='sale')
        self._applied()
        self.assertEqual(applicant.contact_type, 'student')
        self.assertEqual(applicant.main_group_id, self.group1)
        self.assertTrue(applicant.enrollment_ids)

    def test_apply_takes_a_returning_ex_student_back(self):
        alumnus = self.env['res.partner'].create({
            'name': 'CTW Returning', 'contact_type': 'alumni', 'has_graduated': True})
        self._order(alumnus, self.group1, state='sale')
        self._applied()
        self.assertEqual(alumnus.contact_type, 'student')
        self.assertEqual(alumnus.main_group_id, self.group1)

    def test_blocks_a_confirmed_enrollment_without_a_destination_group(self):
        """It used to be a warning saying they would be skipped, but the outcome was
        not recoverable: the student ended with no group, no subjects and no way back
        through the UI. Better to refuse and let 'Suggest destination group' run."""
        student = self._student('CTW No Group')
        self._order(student, group=False, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        self.assertTrue(wizard.has_blockers)
        self.assertEqual(wizard.unplaced_count, 1)
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_apply_ignores_enrollments_still_in_draft(self):
        student = self._student('CTW Draft')
        self._order(student, self.group2)
        self._applied()
        self.assertFalse(student.main_group_id)

    def test_apply_placement_is_idempotent(self):
        student = self._student('CTW Placed Twice')
        self._order(student, self.group2, state='sale')
        self._applied()
        self._applied()
        self.assertEqual(student.main_group_id, self.group2)
        self.assertEqual(len(student.enrollment_ids), 1)

    # --- apply step 5: transitioned mark and conditional flip ----------------

    def test_apply_marks_the_scope_as_transitioned(self):
        self._applied()
        self.assertEqual(self.study.transition_state, 'transitioned')
        self.assertEqual(self.study_other.transition_state, 'active')

    def test_apply_does_not_flip_while_another_study_is_pending(self):
        self._applied()
        self.assertEqual(self.env.company.current_course_id, self.source_course)
        self.assertTrue(self.target_course.is_enrollment_default)

    def _transition_everything_else(self):
        self.env['ems.study'].search([('id', '!=', self.study.id)]).write(
            {'transition_state': 'transitioned'})

    def test_apply_flips_when_nothing_is_left_pending(self):
        self._transition_everything_else()
        self._applied()
        self.assertEqual(self.env.company.current_course_id, self.target_course)
        self.assertTrue(self.target_course.is_current)
        self.assertFalse(self.source_course.is_current)

    def test_flip_keeps_the_enrollment_default_on_the_incoming_course(self):
        """Enrollments keep being processed in September for the course that has just
        started, so the incoming one stays the enrollment default. Clearing it left no
        course flagged, and everything that resolves "the enrollment course" through
        is_enrollment_default (enrollment.py, the proposal wizard, _next_course,
        transition_status, academic_result) got an empty recordset instead."""
        self._transition_everything_else()
        self._applied()
        self.assertTrue(self.target_course.is_enrollment_default)

    def test_flip_leaves_exactly_one_enrollment_default(self):
        """The guard against the opposite mistake: keeping the flag must not end up
        with the outgoing course marked too, which @api.constrains would reject."""
        self._transition_everything_else()
        self._applied()
        defaults = self.env['ems.course'].search([('is_enrollment_default', '=', True)])
        self.assertEqual(defaults, self.target_course)

    def test_flip_puts_every_study_back_to_active(self):
        """A fresh year: they are all pending again for the next transition."""
        self._transition_everything_else()
        self._applied()
        self.assertEqual(self.study.transition_state, 'active')
        self.assertEqual(self.study_other.transition_state, 'active')

    # --- apply step 6: outgoing enrollments ----------------------------------

    def test_apply_locks_the_confirmed_outgoing_enrollments(self):
        """A confirmed enrollment is a legal record: locked, never cancelled."""
        student = self._student('CTW Outgoing Confirmed')
        order = self._order(student, self.group1, state='sale', course=self.source_course)
        self._applied()
        self.assertTrue(order.locked)
        self.assertEqual(order.state, 'sale')

    def test_apply_cancels_the_never_confirmed_outgoing_enrollments(self):
        student = self._student('CTW Outgoing Draft')
        order = self._order(student, self.group1, course=self.source_course)
        self._applied()
        self.assertEqual(order.state, 'cancel')

    def test_apply_keeps_the_incoming_draft_enrollments(self):
        """The latecomer's draft must survive: cancelling it would take away the
        very enrollment that lets them be placed later."""
        student = self._student('CTW Latecomer Draft')
        order = self._order(student, self.group2)
        self._applied()
        self.assertEqual(order.state, 'draft')

    # --- apply steps 7-8: templates and operational cleanup ------------------

    def test_apply_archives_the_attendance_templates_of_the_scope(self):
        template = self._template([self.group1])
        self._applied()
        self.assertFalse(template.active)

    def test_apply_keeps_a_template_shared_with_a_study_out_of_scope(self):
        """Archiving it would take away the schedule of a study still running."""
        template = self._template([self.group1, self.group_other])
        self._applied()
        self.assertTrue(template.active)

    def test_apply_archives_the_schedule_lines_of_an_archived_template(self):
        """Regression test for a real bug: '_apply_cleanup' used to archive templates via a bare
        write({'active': False}), which never triggers EmsAttendanceTemplate.action_archive()'s own
        cascade to attendance_schedule_ids - the template went inactive but its lines stayed
        active=True forever, so a later import could still find them as a genuine "existing
        schedule conflict" against a study that had already transitioned. The two tests above never
        caught this because their own '_template()' fixture creates a template with zero schedule
        lines."""
        template = self._template([self.group1])
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0,
            'space_id': self.space.id,
        })
        self._applied()
        schedule.invalidate_recordset()
        self.assertFalse(schedule.active)

    # --- _migrating_calendar_blocks (phase 5b of the teacher-schedule archival plan) ------

    def test_migrating_calendar_blocks_finds_a_block_for_a_group_in_scope(self):
        block = self._calendar_block(self.teacher.resource_calendar_id, [self.group1])

        found = self._wizard()._migrating_calendar_blocks()

        self.assertIn(block, found)

    def test_migrating_calendar_blocks_excludes_a_group_out_of_scope(self):
        block = self._calendar_block(self.teacher.resource_calendar_id, [self.group_other])

        found = self._wizard()._migrating_calendar_blocks()

        self.assertNotIn(block, found)

    def test_migrating_calendar_blocks_excludes_framework_calendars(self):
        framework = self.env['resource.calendar'].create({
            'name': 'Test Framework (Course Transition)', 'is_framework': True})
        block = self._calendar_block(framework, [self.group1])

        found = self._wizard()._migrating_calendar_blocks()

        self.assertNotIn(block, found)

    def test_preview_sets_calendar_block_count(self):
        self._calendar_block(self.teacher.resource_calendar_id, [self.group1])
        wizard = self._wizard()

        wizard.action_preview()

        self.assertEqual(wizard.calendar_block_count, 1)

    # --- _apply_calendar_archival (phase 5c of the teacher-schedule archival plan) --------

    def test_apply_archives_the_migrating_calendar_block(self):
        block = self._calendar_block(self.teacher.resource_calendar_id, [self.group1])

        self._applied()

        block.invalidate_recordset()
        self.assertFalse(block.active)

    def test_apply_leaves_an_out_of_scope_calendar_block_active(self):
        block = self._calendar_block(self.teacher.resource_calendar_id, [self.group_other])

        self._applied()

        block.invalidate_recordset()
        self.assertTrue(block.active)

    def test_apply_archives_the_matching_schedule_line_and_its_sessions(self):
        template = self._template([self.group1])
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date(2098, 9, 15),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        self._calendar_block(
            self.teacher.resource_calendar_id, [self.group1], weekday='0', hour_from=9.0, hour_to=10.0)

        self._applied()

        schedule.invalidate_recordset()
        session.invalidate_recordset()
        self.assertFalse(schedule.active)
        self.assertFalse(session.active)

    def test_apply_archives_the_template_once_its_only_line_is_archived(self):
        template = self._template([self.group1])
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        self._calendar_block(
            self.teacher.resource_calendar_id, [self.group1], weekday='0', hour_from=9.0, hour_to=10.0)

        self._applied()

        template.invalidate_recordset()
        self.assertFalse(template.active)

    def test_apply_removes_only_the_departing_teacher_when_another_still_has_an_active_block(self):
        """Defensive fallback (decision 3/4 of the plan): the template itself covers group_other
        (OUT of scope, so _templates_to_archive() never touches it) - but self.teacher's own
        calendar block drifted to reference group1 (IN scope), so self.teacher still counts as
        'migrating' via the calendar side alone. teacher_other's own calendar correctly still shows
        group_other and is never touched. The line must survive for teacher_other; only the
        departing self.teacher is dropped from teacher_ids."""
        teacher_other = self.env['hr.employee'].create({
            'name': 'CTW Teacher Other', 'employee_type': 'teacher'})
        template = self._template([self.group_other])
        # ems_bypass_template_lock: 'teacher_ids' is otherwise locked (2026-08-11 refinement) - this
        # is legitimate test setup, same bypass the calendar-sync pipeline itself uses internally.
        template.with_context(ems_bypass_template_lock=True).write({'teacher_ids': [(4, teacher_other.id)]})
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        self._calendar_block(
            self.teacher.resource_calendar_id, [self.group1], weekday='0', hour_from=9.0, hour_to=10.0)
        self._calendar_block(
            teacher_other.resource_calendar_id, [self.group_other], weekday='0', hour_from=9.0, hour_to=10.0)

        self._applied()

        schedule.invalidate_recordset()
        template.invalidate_recordset()
        self.assertTrue(schedule.active)
        self.assertEqual(template.teacher_ids, teacher_other)

    def test_apply_creates_a_new_template_version_when_the_departing_teacher_has_sessions(self):
        """teacher_ids is a locked identity field once real attendance history exists - a raw write
        would retroactively rewrite the already-taken session's own template_teacher_ids (related),
        corrupting who ACTUALLY co-taught it. The departing teacher must be dropped via a fresh
        template version (_write_or_new_version), leaving the archived original - and its session -
        historically untouched."""
        teacher_other = self.env['hr.employee'].create({
            'name': 'CTW Teacher Other', 'employee_type': 'teacher'})
        template = self._template([self.group_other])
        # ems_bypass_template_lock: 'teacher_ids' is otherwise locked (2026-08-11 refinement) - this
        # is legitimate test setup (adding a co-teacher before any real session exists), same bypass
        # the calendar-sync pipeline itself uses internally.
        template.with_context(ems_bypass_template_lock=True).write({'teacher_ids': [(4, teacher_other.id)]})
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date(2098, 9, 15),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        self._calendar_block(
            self.teacher.resource_calendar_id, [self.group1], weekday='0', hour_from=9.0, hour_to=10.0)
        self._calendar_block(
            teacher_other.resource_calendar_id, [self.group_other], weekday='0', hour_from=9.0, hour_to=10.0)

        self._applied()

        template.invalidate_recordset()
        session.invalidate_recordset()
        self.assertFalse(template.active)
        # The historical record is untouched: the already-taken session still points at the
        # ARCHIVED original, whose teacher_ids still lists both teachers exactly as it did at the
        # time the session was actually taken.
        self.assertEqual(session.attendance_schedule_id.attendance_template_id, template)
        self.assertEqual(template.teacher_ids, self.teacher | teacher_other)
        new_template = self.env['ems.attendance_template'].search([
            ('subject_id', '=', template.subject_id.id), ('active', '=', True),
        ])
        self.assertEqual(len(new_template), 1)
        self.assertEqual(new_template.teacher_ids, teacher_other)
        self.assertTrue(new_template.attendance_schedule_ids.active)

    def test_apply_archives_an_orphaned_line_with_no_calendar_support_left(self):
        """Developer feedback (2026-08-10): "lo que manda es el calendario" - a migrating
        teacher's OWN still-active line whose (subject, group, weekday, time) is no longer backed
        by ANY of their current calendar blocks at all - not just the one that triggered their
        departure - must be archived too, even though no single calendar block ever directly
        matched it (e.g. the teacher edited their calendar by hand, bypassing the normal sync, and
        this old line/template was simply never cleaned up)."""
        stale_template = self._template([self.group_other])  # group_other: out of scope
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': stale_template.id,
            'weekday': '1', 'start_time': 11.0, 'end_time': 12.0, 'space_id': self.space.id,
        })
        # self.teacher's calendar has NO block at all for (subject, group_other) anymore - only
        # this unrelated one, which is what makes self.teacher count as "migrating" in the first
        # place (group1 IS in scope).
        self._calendar_block(self.teacher.resource_calendar_id, [self.group1])

        self._applied()

        stale_template.invalidate_recordset()
        self.assertFalse(stale_template.active)

    def test_apply_archives_orphaned_sessions_of_an_already_archived_line_with_no_migrating_teacher(self):
        """Developer feedback (2026-08-10), found re-running a real transition: a line already
        archived by an EARLIER run/edit, whose session catch-up was never reached back then, must
        still get its sessions archived now - even though nothing about its own teacher is
        "migrating" in THIS run at all (zero active calendar blocks, so they never enter
        'affected_teachers'). Real scenario: a teacher already fully rolled over to a new
        calendar in an earlier run, but one of their old lines' session catch-up was simply
        missed back then."""
        template = self._template([self.group1])
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date(2098, 9, 15),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        # Already archived by something else, BEFORE this transition even starts - simulates the
        # leftover from an earlier run. No calendar block at all for self.teacher here - they are
        # not "migrating" in this run by any measure the wizard normally checks.
        # ems_bypass_template_lock: this test is about the transition wizard's own catch-up
        # logic, not point 3's archival lock - bypass it as test setup.
        template.with_context(ems_bypass_template_lock=True).action_archive()

        self._applied()

        session.invalidate_recordset()
        self.assertFalse(session.active)

    def test_apply_with_no_migrating_calendar_blocks_is_a_no_op(self):
        self._applied()  # must not raise

    # --- _apply_calendar_rollover (phases 6-7 of the teacher-schedule archival plan) ------

    def test_apply_rolls_a_teacher_over_to_a_fresh_calendar_once_teaching_empties_out(self):
        old_calendar = self.teacher.resource_calendar_id
        self._calendar_block(old_calendar, [self.group1])

        self._applied()

        self.teacher.invalidate_recordset()
        old_calendar.invalidate_recordset()
        new_calendar = self.teacher.resource_calendar_id
        self.assertNotEqual(new_calendar, old_calendar)
        self.assertEqual(new_calendar.employee_id, self.teacher)
        self.assertEqual(new_calendar.course_id, self.target_course)
        self.assertFalse(old_calendar.active)

    def test_apply_keeps_the_calendar_when_teaching_remains(self):
        old_calendar = self.teacher.resource_calendar_id
        self._calendar_block(old_calendar, [self.group1])
        self._calendar_block(old_calendar, [self.group_other], weekday='1', hour_from=10.0, hour_to=11.0)

        self._applied()

        self.teacher.invalidate_recordset()
        old_calendar.invalidate_recordset()
        self.assertEqual(self.teacher.resource_calendar_id, old_calendar)
        self.assertTrue(old_calendar.active)

    def test_apply_rolls_over_even_if_only_non_teaching_entries_remain(self):
        """Phase 7's own rule: a non-teaching commitment (guard duty, a meeting...) never counts as
        'teaching left' - it must not block the rollover."""
        old_calendar = self.teacher.resource_calendar_id
        self._calendar_block(old_calendar, [self.group1])
        non_teaching = self.env.ref('ems.non_teaching_g')
        self.env['resource.calendar.attendance'].create({
            'calendar_id': old_calendar.id, 'name': 'Test Guard (Course Transition)',
            'dayofweek': '1', 'hour_from': 10.0, 'hour_to': 11.0, 'day_period': 'morning',
            'non_teaching': non_teaching.id,
        })

        self._applied()

        self.teacher.invalidate_recordset()
        old_calendar.invalidate_recordset()
        self.assertNotEqual(self.teacher.resource_calendar_id, old_calendar)
        self.assertFalse(old_calendar.active)

    def test_apply_reactivates_an_existing_archived_calendar_for_the_target_course(self):
        old_calendar = self.teacher.resource_calendar_id
        self._calendar_block(old_calendar, [self.group1])
        archived_next = self.env['resource.calendar'].create({
            'employee_id': self.teacher.id, 'course_id': self.target_course.id,
        })
        archived_next.action_archive()

        self._applied()

        self.teacher.invalidate_recordset()
        self.assertEqual(self.teacher.resource_calendar_id, archived_next)
        self.assertTrue(archived_next.active)
        self.assertEqual(self.env['resource.calendar'].search([
            ('employee_id', '=', self.teacher.id), ('course_id', '=', self.target_course.id),
        ]), archived_next)

    def test_apply_seeds_the_new_calendar_from_the_old_ones_framework(self):
        old_calendar = self.teacher.resource_calendar_id
        framework = self.env.company.default_schedule_framework_id
        self.assertEqual(old_calendar.source_framework_id, framework)
        self._calendar_block(old_calendar, [self.group1])

        self._applied()

        self.teacher.invalidate_recordset()
        self.assertEqual(self.teacher.resource_calendar_id.source_framework_id, framework)

    def test_apply_deletes_the_grade_sessions_of_the_scope(self):
        session = self._session(self.group1, self.subject_int)
        self._applied()
        self.assertFalse(session.exists())

    def test_apply_keeps_the_grade_sessions_out_of_scope(self):
        session = self._session(self.group_other, self.subject_int)
        self._applied()
        self.assertTrue(session.exists())

    def test_a_session_can_be_recreated_after_the_transition(self):
        """The reason the deletion is mandatory: UNIQUE(group, subject, round)
        carries no course, so next year's round 1 needs the old one gone."""
        self._session(self.group1, self.subject_int, round="1")
        self._applied()
        recreated = self._session(self.group1, self.subject_int, round="1")
        self.assertTrue(recreated.exists())

    def test_apply_deletes_the_attendance_issues(self):
        """D6: the year record already froze attendance_issue_count. Also pins down the
        2026-08-10 reordering fix: _apply_attendance_records_archival() (which would otherwise
        archive this same empty issue first, making it invisible to the search below) now runs
        AFTER this deletion, not before - if that ordering ever regresses, this issue would
        survive archived instead of gone, and this assertion would catch it."""
        student = self._student('CTW Issues')
        issue = self._attendance_issue(student)
        tutor_issue = issue.attendance_issue_tutor_id
        self._applied()
        self.assertFalse(issue.exists())
        self.assertFalse(tutor_issue.exists())

    def test_the_withdrawal_helper_also_clears_the_attendance_issues(self):
        """D6 lives in the shared helper, so a withdrawal gets the same cleanup."""
        student = self._student('CTW Issues Withdrawn')
        issue = self._attendance_issue(student)
        student._ems_clear_operational_records()
        self.assertFalse(issue.exists())

    def _archived_session_line_fixture(self, name):
        """A template/schedule/session in scope (group1), for a student with NO main_group_id
        at all - matches the real leftover data found auditing this (2026-08-10): a student
        already stranded by an earlier process falls outside '_scope_students()' forever, so
        '_ems_clear_operational_records()' (which deletes by student scope) never runs for them
        - isolating what '_apply_attendance_records_archival()' (keyed on the SESSION's own
        archived state, not student scope) needs to catch instead. The calendar block is what
        actually gets the SESSION itself archived (via '_apply_calendar_archival()''s explicit
        catch-up step) - '_templates_to_archive()' alone only reaches the template/schedule line,
        never the session (see 'docs/en/developers/attendance/attendance_schedule.md'). Returns
        (student, line)."""
        template = self._template([self.group1])
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        student = self._student(name, group=self.group1)
        student.main_group_id = False
        schedule.student_ids = [(4, student.id)]
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date(2020, 9, 15),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        self._calendar_block(
            self.teacher.resource_calendar_id, [self.group1], weekday='0', hour_from=9.0, hour_to=10.0)
        line = session.attendance_session_line_ids.filtered(lambda line: line.student_id == student)
        return student, line

    def test_apply_archives_orphaned_attendance_issues_referencing_an_archived_session(self):
        """Developer feedback (2026-08-10): the transition must also catch up
        ems.attendance_issue_status/_student/_tutor records left active once their own
        underlying session gets archived - not just delete them for a student still in
        '_scope_students()' (the existing, unrelated D6 mechanism above)."""
        student, line = self._archived_session_line_fixture('CTW Stranded Issue')
        tutor_issue = self.env['ems.attendance_issue_tutor'].create({
            'tutor_id': self.teacher.id, 'issue_date': date(2020, 9, 15)})
        student_issue = self.env['ems.attendance_issue_student'].create({
            'attendance_issue_tutor_id': tutor_issue.id, 'student_id': student.id})
        status_issue = self.env['ems.attendance_issue_status'].create({
            'attendance_issue_student_id': student_issue.id,
            'attendance_session_line_id': line.id, 'send_to': 'test@example.com',
        })

        self._applied()

        status_issue.invalidate_recordset()
        student_issue.invalidate_recordset()
        tutor_issue.invalidate_recordset()
        self.assertFalse(status_issue.active)
        self.assertFalse(student_issue.active)
        self.assertFalse(tutor_issue.active)

    def test_apply_leaves_an_attendance_issue_active_when_its_session_is_not_archived(self):
        """Negative case: an issue whose own session is untouched by this run (out-of-scope
        group) must not be swept up just because it happens to exist."""
        template = self._template([self.group_other])
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '2', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        student = self._student('CTW Not Stranded Issue', group=self.group_other)
        student.main_group_id = False
        schedule.student_ids = [(4, student.id)]
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date(2020, 9, 16),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        line = session.attendance_session_line_ids.filtered(lambda line: line.student_id == student)
        tutor_issue = self.env['ems.attendance_issue_tutor'].create({
            'tutor_id': self.teacher.id, 'issue_date': date(2020, 9, 16)})
        student_issue = self.env['ems.attendance_issue_student'].create({
            'attendance_issue_tutor_id': tutor_issue.id, 'student_id': student.id})
        status_issue = self.env['ems.attendance_issue_status'].create({
            'attendance_issue_student_id': student_issue.id,
            'attendance_session_line_id': line.id, 'send_to': 'test@example.com',
        })

        self._applied()

        status_issue.invalidate_recordset()
        self.assertTrue(status_issue.active)

    def test_apply_archives_an_orphaned_justification_referencing_an_archived_session(self):
        student, line = self._archived_session_line_fixture('CTW Stranded Justification')
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id, 'student_id': student.id,
            'start_date': datetime(2020, 9, 15, 8, 0), 'end_date': datetime(2020, 9, 15, 11, 0),
            'attendance_session_line_ids': [(6, 0, line.ids)],
        })

        self._applied()

        justification.invalidate_recordset()
        self.assertFalse(justification.active)

    def test_apply_archives_a_past_justification_with_no_session_at_all(self):
        """Developer feedback (2026-08-10), found re-running a real transition after the fix
        above: 'attendance_session_line_ids' is a form-editing M2M, not the real link - a real,
        dated-in-the-past justification can genuinely have ZERO entries there (the real link,
        'ems.attendance_session_line.attendance_justification_id'/'attendance_prevision_id', is
        set by session auto-creation, never synced back onto the justification's own M2M). Once
        its own end_date is in the past, it should be archived regardless - there's no session
        left to ever populate it now that the course it covered is over."""
        student = self._student('CTW Past No Session Justification', group=self.group1)
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id, 'student_id': student.id,
            'start_date': datetime(2020, 9, 15, 8, 0), 'end_date': datetime(2020, 9, 15, 11, 0),
        })

        self._applied()

        justification.invalidate_recordset()
        self.assertFalse(justification.active)

    def test_apply_leaves_a_future_justification_with_no_session_active(self):
        """Negative case: a genuine future 'prevision' (submitted ahead of an expected absence
        that hasn't happened yet) must not be swept up just because no session has been created
        for it yet - only a PAST end_date makes zero-lines archivable."""
        student = self._student('CTW Future No Session Justification', group=self.group1)
        future = datetime.now().replace(year=datetime.now().year + 5)
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id, 'student_id': student.id,
            'start_date': future, 'end_date': future.replace(hour=23, minute=0),
        })

        self._applied()

        justification.invalidate_recordset()
        self.assertTrue(justification.active)

    def test_apply_archives_an_attendance_issue_student_with_no_children_at_all(self):
        """Developer feedback (2026-08-10), found re-running a real transition after the fix
        above: an issue_student/_tutor with ZERO status children from the start never appears in
        the 'just archived' set the first version of this method derived its cleanup from, so it
        was never re-checked. Must be caught for a STRANDED student (outside '_scope_students()',
        so '_ems_clear_operational_records()' would never delete it either) - the negative case
        right below confirms a scoped student's own empty issue is left for that deletion instead."""
        student = self._student('CTW Stranded Empty Issue', group=self.group1)
        student.main_group_id = False
        tutor_issue = self.env['ems.attendance_issue_tutor'].create({
            'tutor_id': self.teacher.id, 'issue_date': date(2020, 9, 15)})
        student_issue = self.env['ems.attendance_issue_student'].create({
            'attendance_issue_tutor_id': tutor_issue.id, 'student_id': student.id})

        self._applied()

        student_issue.invalidate_recordset()
        tutor_issue.invalidate_recordset()
        self.assertFalse(student_issue.active)
        self.assertFalse(tutor_issue.active)

    def test_apply_keeps_the_new_enrollments_after_the_cleanup(self):
        """The cleanup deletes EVERY ems.enrollment of the student with no group
        filter, so running it after the placement would destroy the enrollments the
        transition had just created. This is what pins the order of the steps."""
        student = self._student('CTW Survives Cleanup')
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.group1.id,
            'subject_id': self.subject_int.id})
        self._order(student, self.group2, state='sale')
        self._applied()
        self.assertEqual(student.main_group_id, self.group2)
        self.assertEqual(student.enrollment_ids.mapped('group_id'), self.group2)

    def test_apply_clears_the_delegate_of_the_emptied_groups(self):
        """A graduate has lost its main_group_id by the time the shared helper runs,
        so the delegate has to be cleared from the group side."""
        delegate = self._graduate('CTW Delegate')
        self.group2.delegate_id = delegate
        self._applied()
        self.assertFalse(self.group2.delegate_id)

    # --- apply step 9: audit -------------------------------------------------

    def test_apply_logs_the_transition_on_the_company(self):
        """res.company has no chatter of its own, so the trace goes on its partner."""
        self._student('CTW Audited')
        before = len(self.env.company.partner_id.message_ids)
        self._applied()
        self.assertEqual(len(self.env.company.partner_id.message_ids), before + 1)

    def test_apply_attaches_the_rollback_csv(self):
        student = self._student('CTW Audit CSV')
        self._order(student, self.group2, state='sale')
        wizard = self._applied()
        self.assertTrue(wizard.audit_file)
        self.assertTrue(wizard.audit_file_name.endswith('.csv'))
        content = base64.b64decode(wizard.audit_file).decode('utf-8-sig')
        self.assertIn(student.display_name, content)
        self.assertIn(self.group2.name, content)

    def test_the_audit_note_is_internal(self):
        """An internal note: the transition concerns the staff, and the company
        partner may well have followers who must not be notified about it."""
        self._applied()
        message = self.env.company.partner_id.message_ids[0]
        self.assertEqual(message.subtype_id, self.env.ref('mail.mt_note'))

    # --- D2: the graduation mark --------------------------------------------

    def test_the_graduation_wizard_reports_the_study(self):
        student = self._student('CTW D2', group=self.group2)
        wizard = self.env['ems.graduation_wizard'].with_context(
            active_ids=student.ids).create({})
        self.assertEqual(wizard.line_ids.study_id, student.study_id)

    def test_preview_lists_the_incoming_applicants(self):
        """They are placed by the same steps, so they belong in the preview even
        though the scope-by-group capture cannot see them."""
        applicant = self.env['res.partner'].create({
            'name': 'CTW Preview Incoming', 'contact_type': 'applicant', 'study_id': self.study.id})
        self._order(applicant, self.group1, state='sale')
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda line: line.student_id == applicant)
        self.assertEqual(line.action, 'place')
        self.assertEqual(line.destination_group_id, self.group1)


    def test_withdrawing_after_the_transition_keeps_the_frozen_record(self):
        """The manual sends the operator here: register the leavers AFTER applying.
        Regenerating would have read an empty group and blanked the only surviving
        trace of the year."""
        student = self._student('CTW Withdraw After', group=self.group2)
        self._scored(student, self.group2, self.subject_int, self.outcome_int)
        self._applied()
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(record.group_id, self.group2)
        subjects = len(record.subject_record_ids)
        self.assertTrue(subjects)

        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=student.ids).create({})
        wizard.action_apply()

        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('course_id', '=', self.source_course.id)])
        self.assertEqual(record.group_id, self.group2)
        self.assertEqual(len(record.subject_record_ids), subjects)
        self.assertEqual(student.contact_type, 'withdrawal')
