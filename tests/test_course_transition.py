import base64
from datetime import date
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
            'level_id': self.level.id, 'study_id': self.study.id,
            'subject_id': self.subject_int.id,
            'group_ids': [(6, 0, [group.id for group in groups])],
            'space_id': self.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2098, 12, 31),
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
        self.assertEqual(self.study.copy().transition_state, 'active')

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

    def test_declined_applicants_ignore_an_applicant_with_a_live_offer(self):
        """An offer still in draft/sent is one we are waiting on, not a declined one:
        archiving it would cut off the very confirmation we are expecting."""
        applicant = self.env['res.partner'].create({
            'name': 'CTW Live Offer', 'contact_type': 'applicant',
            'study_id': self.study.id})
        self._order(applicant, self.group1, state='sent')
        wizard = self._wizard(archive_declined_applicants=True)
        wizard.action_preview()
        self.assertNotIn(applicant, wizard._declined_applicants(
            wizard._target_orders_by_partner()))

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

    def test_flip_clears_the_enrollment_default_of_the_incoming_course(self):
        """Once it is the running course it is nobody's 'next course' any more."""
        self._transition_everything_else()
        self._applied()
        self.assertFalse(self.target_course.is_enrollment_default)

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
        """D6: the year record already froze attendance_issue_count."""
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

