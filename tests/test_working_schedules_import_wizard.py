import base64
import json
from datetime import date

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestWorkingSchedulesImportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The wizard requires a "current course" (company.current_course_id) to be set.
        if not cls.env.company.current_course_id:
            cls.env.company.current_course_id = cls.env['ems.course'].create({'start': 2098, 'end': 2099})
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Wizard Teacher (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher.import.wizard@example.com',
        })
        cls.level, cls.study = create_level_study(cls, 'TWIW', level={'name': 'Test Level (Import Wizard)'}, study={
            'code': 'TWIW001', 'name': 'Test Study (Import Wizard)', 'date': fields.Date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWIW001',
            'acronym': 'TWIW',
            'name': 'Test Subject (Import Wizard)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TWIW-A',
            'name': 'Test Space (Import Wizard)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'TWIW',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.space.id,
        })
        # A level's only group: EMS always keeps the trailing letter ("TWIW2A"), while the external
        # planner names it without one ("TWIW2") — see test_import_single_group_without_trailing_a_falls_back.
        cls.single_group = cls.env['ems.group'].create({
            'course': 2,
            'acronym': 'A',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.space.id,
        })
        cls.other_subject = cls.env['ems.subject'].create({
            'code': 'TWIW002',
            'acronym': 'TWIW2',
            'name': 'Test Subject 2 (Import Wizard)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # Deliberately NOT associated with 'cls.study' (or any study) - the "wrong subject for the
        # group's own study" fixture for the 'subjects' step's own tests (real error this screen
        # was built for, 2026-08-10: "The subject '...' is not available in the following selected
        # studies: ...").
        cls.wrong_subject = cls.env['ems.subject'].create({
            'code': 'TWIW003',
            'acronym': 'TWIW3',
            'name': 'Test Wrong Subject (Import Wizard)',
        })
        # A group belonging to a study that teaches NEITHER 'cls.subject' nor 'cls.other_subject' -
        # the "wrong group for the file's own (otherwise valid) subject" fixture, the other real
        # variant of this same mismatch (developer feedback 2026-08-11: "el error era el (o los)
        # grupo, o el error era la asignatura" - either side can be the actual mistake).
        cls.wrong_study = cls.env['ems.study'].create({
            'code': 'TWIW004', 'acronym': 'TWIW4', 'name': 'Test Wrong Study (Import Wizard)',
            'date': fields.Date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.wrong_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'WRONGGRP', 'level_id': cls.level.id, 'study_id': cls.wrong_study.id,
            'space_id': cls.space.id,
        })
        # No 'space_id' — ems.group.space_id is optional, but ems.attendance_template.space_id (taken
        # from the group) is required; see test_import_group_without_space_raises_clear_error.
        cls.spaceless_group = cls.env['ems.group'].create({
            'course': 3,
            'acronym': 'NOSPACE',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
        })
        # Reinforcement groups have no level/study/course of their own — the name is set manually to
        # match whatever the external planner exports, since '_compute_name' only derives it for 'main'.
        cls.reinforcement_group = cls.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Reforç TWIW',
            'space_id': cls.space.id,
        })
        # A study with a single course AND a single group: the planner exports just the bare study
        # acronym ("TDEV"), omitting BOTH the course number and the trailing letter EMS always stores
        # ("TDEV1A") — unlike 'single_group' above (course present, only the letter missing).
        cls.bare_acronym_study = cls.env['ems.study'].create({
            'code': 'TDEV001', 'acronym': 'TDEV', 'name': 'Test Bare Acronym Study (Import Wizard)',
            'date': fields.Date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        # 'self.subject' is imported for groups belonging to this study too (see e.g.
        # test_import_bare_study_acronym_resolves_single_course_single_group) - must be one of its
        # own allowed studies, or ems.attendance_template's own subject/study validity check
        # (_check_subject_valid_for_all_studies) correctly rejects the combination.
        cls.subject.study_ids = [(4, cls.bare_acronym_study.id)]
        cls.bare_acronym_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.bare_acronym_study.id,
            'space_id': cls.space.id,
        })

    def _import(self, vals):
        """Creates the wizard and clicks 'Continue' through every step to the final one, then runs
        the real write - mirrors what a real user does clicking through the wizard. Since
        2026-08-05's multi-step redesign, a ValidationError for an unresolved subject/e-mail or a
        blocking conflict surfaces at the final 'import_planner_data()' call; an unresolved GROUP
        name (see 'ems.working_schedules_import_wizard._continue_from_groups') surfaces instead
        while still leaving the 'groups' step, since this helper never fills in
        'group_line_ids.group_id' - a test that needs to actually resolve one should drive the
        wizard by hand instead of using this helper."""
        wizard = self.env['ems.working_schedules_import_wizard'].create(vals)
        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()
        return wizard

    def _xml_file(self, teacher_name_attr):
        # Minimal file the parser accepts: one teacher node -> one day -> one hour -> a NonTeaching
        # entry ('G'/Guard already exists as an ems.non_teaching_type seed record, so no subject/group lookup needed).
        xml = (
            '<root>'
            f'<T name="{teacher_name_attr}">'
            '<D name="1 Monday">'
            '<H name="1 09:00"><NonTeaching name="G Guard"/></H>'
            '</D></T></root>'
        )
        return base64.b64encode(xml.encode())

    def _xml_file_with_hour_node(self, teacher_name_attr, hour_children_xml):
        xml = (
            '<root>'
            f'<T name="{teacher_name_attr}">'
            '<D name="1 Monday">'
            f'<H name="1 09:00">{hour_children_xml}</H>'
            '</D></T></root>'
        )
        return base64.b64encode(xml.encode())

    def _xml_file_multiple_teachers(self, *teacher_name_attrs):
        teachers = "".join(
            f'<T name="{attr}"><D name="1 Monday"><H name="1 09:00"><NonTeaching name="G Guard"/></H></D></T>'
            for attr in teacher_name_attrs
        )
        return base64.b64encode(f'<root>{teachers}</root>'.encode())

    def _xml_file_with_hours(self, teacher_name_attr, start_times):
        # One 'NonTeaching' hour node per start time (same day), so hour_from/hour_to inference can
        # be exercised without depending on subject/group fixtures.
        hours = "".join(f'<H name="1 {start}"><NonTeaching name="G Guard"/></H>' for start in start_times)
        xml = (
            '<root>'
            f'<T name="{teacher_name_attr}">'
            f'<D name="1 Monday">{hours}</D>'
            '</T></root>'
        )
        return base64.b64encode(xml.encode())

    def _xml_two_teachers_same_slot(self, teacher_a, hour_children_a, teacher_b, hour_children_b, start='09:00'):
        """Two DIFFERENT teachers, each with one hour-entry at the exact same weekday/time - the
        raw material for a within-batch (screen 4) collision test."""
        xml = (
            '<root>'
            f'<T name="{teacher_a}"><D name="1 Monday"><H name="1 {start}">{hour_children_a}</H></D></T>'
            f'<T name="{teacher_b}"><D name="1 Monday"><H name="1 {start}">{hour_children_b}</H></D></T>'
            '</root>'
        )
        return base64.b64encode(xml.encode())

    def _attachment_ids(self, *xml_contents, names=None):
        """Wrap one or more already-base64-encoded XML byte strings into the 'attachment_ids' m2m
        command this wizard's only import path (create()/onchange) reads."""
        names = names or [f'planner{i}.xml' for i in range(len(xml_contents))]
        ids = [
            self.env['ir.attachment'].create({'name': name, 'datas': content}).id
            for content, name in zip(xml_contents, names)
        ]
        return [(6, 0, ids)]

    def test_import_matches_by_email(self):
        self._import({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)

    def test_import_unknown_email_defaults_to_create_new_pending_teacher(self):
        # Deferred to the 'teachers' step (2026-08-05). 'teacher_line.create_new' defaults to True
        # (changed 2026-08-06: a genuinely never-hired teacher turned out to be the more common
        # real case), so '_import()`'s blind continue-through - never touching the line - now
        # succeeds by default, creating a pending-identification teacher for that e-mail, instead
        # of raising (see test_continue_from_teachers_raises_when_neither_employee_nor_create_new
        # for the still-raising case, which now requires explicitly unticking 'create_new').
        self._import({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'unknown.import.wizard@example.com')])
        self.assertTrue(teacher)
        self.assertTrue(teacher.resource_calendar_id.attendance_ids)

    def test_import_placeholder_code_creates_pending_teacher(self):
        # A code with no '@' (e.g. "X1") isn't a real e-mail typo: the external planner uses it for a
        # not-yet-staffed post, so a pending-identification teacher is created instead of raising. The
        # raw XML 'name' attribute for this kind of row is just the code itself, with no discardable
        # label after it (unlike a real teacher's "<email> <display name>" row) — see
        # test_import_placeholder_full_name_kept_whole below for the case where that identifier is a
        # multi-word real name instead of a short code.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'X1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'X1')])
        self.assertTrue(teacher)
        self.assertEqual(teacher.employee_type, 'teacher')
        self.assertTrue(teacher.pending_identification)
        attendance = teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertEqual(attendance.subject_id, self.subject)
        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertTrue(template)

    def test_import_placeholder_code_reuses_same_employee_on_reimport(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file('X2')),
        })
        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'X2')])

        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file('X2')),
        })

        self.assertEqual(
            self.env['hr.employee'].search_count([('schedule_import_code', '=', 'X2')]), 1
        )
        self.assertEqual(teacher, self.env['hr.employee'].search([('schedule_import_code', '=', 'X2')]))

    def test_import_placeholder_full_name_kept_whole(self):
        # A not-yet-hired teacher may have no code at all in the planner export — just their own real,
        # multi-word name (no '@' anywhere in it). Reported 2026-08-01: naively taking the raw 'name'
        # attribute's first whitespace-separated token (as if it were always "<code> <label>") silently
        # truncated this to just the first word. The full value must be kept as the identifier.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file('Fulanito Menganito')),
        })

        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'Fulanito Menganito')])
        self.assertTrue(teacher)
        self.assertTrue(teacher.pending_identification)
        self.assertFalse(
            self.env['hr.employee'].search([('schedule_import_code', '=', 'Fulanito')])
        )

    def test_import_with_no_file_raises(self):
        with self.assertRaises(ValidationError):
            self._import({})

    def test_import_with_multiple_attachment_ids_processes_every_file(self):
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 2 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher2.import.wizard@example.com',
        })
        attachment_1 = self.env['ir.attachment'].create({
            'name': 'planner1.xml',
            'datas': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })
        attachment_2 = self.env['ir.attachment'].create({
            'name': 'planner2.xml',
            'datas': self._xml_file('test.wizard.teacher2.import.wizard@example.com Someone Else'),
        })

        self._import({
            'attachment_ids': [(6, 0, [attachment_1.id, attachment_2.id])],
        })

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)
        self.assertTrue(second_teacher.resource_calendar_id.attendance_ids)

    def test_import_non_teaching_hour_sent_as_subject_node_without_students(self):
        # The external planner app now sends non-teaching hours as a 'Subject' node too, whose only
        # observable difference from a real subject is the missing 'Students' sibling. The code ('G')
        # must still be recognized as non-teaching (via ems.non_teaching_type), not looked up as a
        # real ems.subject.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<Subject name="G Guard"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertEqual(attendance.non_teaching, self.env.ref('ems.non_teaching_g'))
        self.assertFalse(attendance.subject_id)

    def test_import_real_subject_sent_as_subject_node_with_students(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertFalse(attendance.non_teaching)
        self.assertEqual(attendance.subject_id, self.subject)
        self.assertEqual(attendance.group_ids, self.group)

    def test_import_two_main_groups_share_one_session(self):
        # Real scenario: a level split into two official groups sharing the same classroom (a
        # "desdoblament") - distinct from a reinforcement group. The planner file lists them as two
        # separate <Students> nodes under the same hour; both must end up in the same attendance row.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>'
                f'<Students name="{self.single_group.name} Group"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.group | self.single_group)

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(template.group_ids, self.group | self.single_group)

    def test_import_reinforcement_group_resolved_by_exact_name(self):
        # A reinforcement group's name is free-form and can contain spaces (e.g. "Reforç Programació"),
        # and the real planner export never appends anything to it (unlike 'main' groups' " Group"
        # suffix convention used elsewhere in this file) — it must resolve by matching the full
        # '<Students name="...">' value exactly as-is.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.reinforcement_group.name}"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertEqual(attendance.group_ids, self.reinforcement_group)

    def test_import_single_group_without_trailing_a_falls_back(self):
        # The external planner names a level's only group "TWIW2" (no trailing letter), while EMS
        # always stores it as "TWIW2A" even when it's the only group of that level/course.
        self.assertEqual(self.single_group.name, 'TWIW2A')

        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TWIW2 Group"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.single_group)

    def test_import_bare_study_acronym_resolves_single_course_single_group(self):
        # The external planner names a study with only one course and one group by its bare acronym
        # ("TDEV"), with neither the course number nor the trailing letter EMS always stores ("TDEV1A").
        self.assertEqual(self.bare_acronym_group.name, 'TDEV1A')

        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TDEV Group"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.bare_acronym_group)

    def test_import_bare_study_acronym_with_several_groups_raises(self):
        # If the study actually has more than one group, a bare acronym is genuinely ambiguous - the
        # importer must not guess which one the planner meant. Deferred to the 'groups' step
        # (2026-08-05) rather than raised immediately: '_import()' never fills in a pick for it, so
        # leaving that step still raises, same as before from the caller's point of view.
        self.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': self.level.id, 'study_id': self.bare_acronym_study.id,
            'space_id': self.space.id,
        })

        with self.assertRaises(ValidationError):
            self._import({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    '<Students name="TDEV Group"/>',
                )),
            })

    def test_import_group_still_not_found_after_fallback_raises(self):
        # Deferred to the 'groups' step (2026-08-05): '_import()' never fills in a pick for the
        # resulting 'group_line', so leaving that step still raises, same as a real user cancelling
        # out rather than picking a group would.
        with self.assertRaises(ValidationError):
            self._import({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    '<Students name="NOPE Group"/>',
                )),
            })

    def test_import_last_period_of_day_inherits_previous_period_duration(self):
        # Real-world bug: the last period of the day was always clamped to the fixed company
        # setting (schedule_import_last_entry_time, 21:00), instead of keeping the same 1h duration
        # as the rest of the day. 19:20-20:20 (1h) is followed by a period starting at 20:20, which
        # should now end at 21:20, not the company's fixed 21:00.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hours(
                'test.wizard.teacher.import.wizard@example.com Someone',
                ['19:20', '20:20'],
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids.sorted('hour_from')
        self.assertEqual(len(attendance), 2)
        self.assertAlmostEqual(attendance[0].hour_from, 19 + 20 / 60)
        self.assertAlmostEqual(attendance[0].hour_to, 20 + 20 / 60)
        self.assertAlmostEqual(attendance[1].hour_from, 20 + 20 / 60)
        self.assertAlmostEqual(attendance[1].hour_to, 21 + 20 / 60)

    def test_import_single_period_day_still_uses_company_fallback(self):
        # No preceding period to infer a duration from: falls back to the company setting, same as
        # before this fix.
        self._import({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.hour_to, self.env.company.schedule_import_last_entry_time)

    def test_continue_from_intro_placeholder_code_unresolved_group_defers_to_groups_step(self):
        # Reported 2026-08-01: a not-yet-identified (pending-code) teacher's schedule content must
        # still be parsed (not skipped just because its own identity isn't resolved yet). Updated
        # 2026-08-05: an unresolvable group acronym in that row no longer blocks the intro screen -
        # it's deferred to the new 'groups' step instead (see 'plans/
        # working_schedule_import_redesign.md's step 2), same as for an identified teacher.
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_pending_bad_group.xml',
            'datas': self._xml_file_with_hour_node(
                'X4',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="NOPE Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard.action_continue()

        self.assertEqual(wizard.state, 'groups')
        self.assertEqual(wizard.group_line_ids.mapped('raw_name'), ['NOPE Group'])
        self.assertFalse(wizard.group_line_ids.group_id)

    def test_ready_to_import_reflects_attachment_ids(self):
        # 'ready_to_import' is now a plain computed field (2026-08-05: no more content validation
        # gates the intro screen at all - see 'ems.working_schedules_import_wizard.ready_to_import's
        # own docstring) - just whether any file is attached.
        wizard = self.env['ems.working_schedules_import_wizard'].new({})
        self.assertFalse(wizard.ready_to_import)

        attachment = self.env['ir.attachment'].create({
            'name': 'planner_known.xml',
            'datas': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })
        wizard.attachment_ids = [(6, 0, [attachment.id])]

        self.assertTrue(wizard.ready_to_import)

    def _xml_teacher_subject_then_gap(self, email_and_name, hour1, subject, group, hour2):
        return (
            f'<T name="{email_and_name}">'
            '<D name="1 Monday">'
            f'<H name="1 {hour1}">'
            f'<Subject name="{subject.code} {subject.name}"/>'
            f'<Students name="{group.name} Group"/>'
            '</H>'
            f'<H name="2 {hour2}"><NonTeaching name="CT Coordination Time"/></H>'
            '</D></T>'
        )

    def test_batch_swapped_times_across_two_teachers_sharing_a_room_does_not_raise(self):
        # Real-world bug: importing several teachers from one file synced each teacher's
        # ems.attendance_template fully (archive + write) before moving to the next one, so an early
        # teacher's fresh line could falsely collide with a later teacher's still-stale line when they
        # share a classroom (same group's default space). The whole import must not raise.
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 3 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher3.import.wizard@example.com',
        })
        xml = '<root>' + (
            self._xml_teacher_subject_then_gap(
                'test.wizard.teacher.import.wizard@example.com Someone', '09:00', self.subject, self.group, '10:00',
            ) + self._xml_teacher_subject_then_gap(
                'test.wizard.teacher3.import.wizard@example.com Someone Else', '17:00', self.other_subject, self.group, '18:00',
            )
        ) + '</root>'
        self._import({
            'attachment_ids': [(6, 0, [self.env['ir.attachment'].create({
                'name': 'planner_shared_room.xml', 'datas': base64.b64encode(xml.encode()),
            }).id])],
        })

        # Swap: 'self.teacher' takes over what used to be 'second_teacher's slot in the SAME room.
        xml_swapped = '<root>' + (
            self._xml_teacher_subject_then_gap(
                'test.wizard.teacher.import.wizard@example.com Someone', '17:00', self.subject, self.group, '18:00',
            ) + self._xml_teacher_subject_then_gap(
                'test.wizard.teacher3.import.wizard@example.com Someone Else', '09:00', self.other_subject, self.group, '10:00',
            )
        ) + '</root>'
        # import_mode='replace': a genuine swap means each teacher's OLD slot must actually go
        # away, not just gain a second one alongside it - the default 'combine' mode (2026-09-02,
        # see plans/calendar_pipeline_simplification.md) never removes a slot this file doesn't
        # redescribe, so under 'combine' this second import would leave BOTH teachers still
        # holding their ORIGINAL slot too, which would make this genuinely collide with the new
        # one sharing the same room - exactly the false-vs-real collision distinction this test
        # exists to draw, just via the mode now instead of an implicit always-wipe default.
        self._import({
            'attachment_ids': [(6, 0, [self.env['ir.attachment'].create({
                'name': 'planner_shared_room_swapped.xml', 'datas': base64.b64encode(xml_swapped.encode()),
            }).id])],
            'import_mode': 'replace',
        })

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', second_teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertEqual(other_template.attendance_schedule_ids.mapped('start_time'), [9])

    def test_import_prevail_left_default_archives_conflicting_external_session(self):
        # A teacher simply absent from the file being (re)imported can still hold an active schedule
        # line in a room the new import now also wants at an overlapping time, for a DIFFERENT
        # subject/group - a genuine double-booking, not co-teaching. Updated 2026-08-05: this no
        # longer raises unconditionally - it's now a 'db_conflicts' screen 'plain_conflict' line
        # (both sides genuinely share the SAME room here, since they both use 'self.group'). Updated
        # again 2026-08-06 (developer feedback): a genuine same-room 'plain_conflict' now defaults to
        # 'reassign_rooms' instead of "left prevails" - picking a room is the actual fix for a real
        # room conflict - so this test explicitly picks 'prevail_left' by hand instead of relying on
        # '_import()`'s blind continue-through, to keep testing the archiving behavior itself.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        first_schedule = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
            ('attendance_template_id.subject_id', '=', self.subject.id),
        ])
        self.assertTrue(first_schedule.active)

        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 4 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher4.import.wizard@example.com',
        })
        # 'self.teacher' is NOT part of this second import — only 'second_teacher' is, teaching a
        # DIFFERENT subject in the SAME group/room/time.
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher4.import.wizard@example.com Someone Else',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        while wizard.state != 'db_conflicts':
            wizard.action_continue()
        wizard.external_conflict_line_ids.resolution = 'prevail_left'
        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        first_schedule.invalidate_recordset()
        self.assertFalse(first_schedule.active)
        self.assertTrue(second_teacher.resource_calendar_id.attendance_ids)

    def test_import_prevail_left_default_archives_conflict_when_new_teacher_is_pending_code(self):
        # Same shape as the test above, but the NEW side is a pending-identification teacher (no
        # e-mail, no pre-existing hr.employee) instead of an already-existing one.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        first_schedule = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
            ('attendance_template_id.subject_id', '=', self.subject.id),
        ])

        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'PENDINGCONFLICT',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        while wizard.state != 'db_conflicts':
            wizard.action_continue()
        wizard.external_conflict_line_ids.resolution = 'prevail_left'
        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        first_schedule.invalidate_recordset()
        self.assertFalse(first_schedule.active)
        pending_teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'PENDINGCONFLICT')])
        self.assertTrue(pending_teacher.resource_calendar_id.attendance_ids)

    def test_import_co_teaching_merges_into_one_shared_template(self):
        # Real-world case (two teachers importing the exact same subject+group+time+room): must end
        # up sharing a SINGLE ems.attendance_template (and therefore a single, jointly-visible
        # attendance session) rather than one template each.
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 7 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher7.import.wizard@example.com',
        })
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher7.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        templates = self.env['ems.attendance_template'].search([
            ('subject_id', '=', self.subject.id),
            ('group_ids', 'in', self.group.id),
        ])
        self.assertEqual(len(templates), 1)
        self.assertEqual(set(templates.teacher_ids.ids), {self.teacher.id, second_teacher.id})

    def test_import_group_without_space_raises_clear_error(self):
        # ems.group.space_id is optional, but ems.attendance_template.space_id (taken from the
        # group) is required — without this check, Odoo's generic "mandatory field is not set" error
        # would surface instead of naming which group is missing a classroom. Caught on the 'groups'
        # step since 2026-08-12 (developer feedback, after hitting this exact error only at the very
        # last Import click: "quiero que podamos arreglarlo desde 'Resolve groups'") - '_import()'
        # never fills in 'space_line_ids.space_id', so it surfaces there, not at Import. The final
        # 'import_planner_data()' raise (see 'test_apply_import_raises_final_safety_net_for_a_group_
        # only_known_missing_space_after_groups_step' below) is now only a safety net for a group that
        # only becomes known-missing-space AFTER the 'groups' step (e.g. newly created on the spot).
        with self.assertRaises(ValidationError) as capture:
            self._import({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    f'<Students name="{self.spaceless_group.name} Group"/>',
                )),
            })

        self.assertIn(self.spaceless_group.name, str(capture.exception))

    def test_continue_from_intro_lists_group_missing_a_classroom_on_the_groups_step(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            )),
        })

        wizard.action_continue()

        self.assertEqual(wizard.state, 'groups')
        self.assertEqual(wizard.space_line_ids.group_id, self.spaceless_group)
        self.assertFalse(wizard.space_line_ids.space_id)

    def test_continue_from_groups_raises_when_a_classroom_is_still_unassigned(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups

        with self.assertRaises(ValidationError) as capture:
            wizard.action_continue()

        self.assertEqual(wizard.state, 'groups')
        self.assertIn(self.spaceless_group.name, str(capture.exception))

    def test_continue_from_groups_assigning_a_classroom_writes_it_on_the_real_group_and_continues(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.space_line_ids.space_id = self.space.id

        wizard.action_continue()  # groups -> subjects

        self.assertEqual(wizard.state, 'subjects')
        # The fix is permanent, not wizard-scoped - it's written straight onto the real group.
        self.assertEqual(self.spaceless_group.space_id, self.space)

    def test_apply_import_raises_final_safety_net_for_a_group_only_known_missing_space_after_groups_step(self):
        """A group only reachable by resolving an UNRESOLVED raw name on the 'groups' step (not
        matched by name at parse time, so '_continue_from_intro' never saw it in any node_cache
        'group_ids' and 'space_line_ids' stayed empty) is still caught - just later, by '_apply_
        import()'s own end-of-pipeline check, not pre-emptively on the 'groups' step itself (see
        '_groups_without_space's own docstring)."""
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_unknown_group_no_space.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TWIWNOTAREALGROUP Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': [(6, 0, [attachment.id])],
        })
        wizard.action_continue()  # intro -> groups
        self.assertFalse(wizard.space_line_ids)
        wizard.group_line_ids.group_id = self.spaceless_group.id

        while wizard.state != 'summary':
            wizard.action_continue()

        with self.assertRaises(ValidationError) as capture:
            wizard.import_planner_data()

        self.assertIn(self.spaceless_group.name, str(capture.exception))

    def test_continue_from_intro_unknown_group_defers_to_groups_step(self):
        # Updated 2026-08-05: an unresolvable group no longer blocks the intro screen - it's
        # deferred to the 'groups' step instead (see 'plans/working_schedule_import_redesign.md's
        # step 2). Unlike an unknown e-mail (deferred all the way to Import), this one still needed
        # '_parse_schedule_entries' itself to keep producing entries for the node instead of raising
        # - see 'pending_group_names'.
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_unknown_group.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TWIWNOTAREALGROUP Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard.action_continue()

        self.assertEqual(wizard.state, 'groups')
        self.assertEqual(wizard.group_line_ids.mapped('raw_name'), ['TWIWNOTAREALGROUP Group'])
        self.assertFalse(wizard.group_line_ids.group_id)

    def test_continue_from_intro_unknown_subject_code_raises(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_unknown_subject.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<Subject name="ZZZZ Unknown subject"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        with self.assertRaises(ValidationError) as capture:
            wizard.action_continue()

        self.assertIn('ZZZZ', str(capture.exception))
        self.assertEqual(wizard.state, 'intro')

    def _create_self_conflict_setup(self):
        """A second space + group, unrelated to self.space/self.group, so a same-teacher,
        same-day/time, different-room import can be built without colliding with 'classify_
        external_conflicts' own same-space check - this must be caught by 'find_self_conflicts'."""
        other_space = self.env['ems.space'].create({
            'code': 'TWIW-B', 'name': 'Test Space B (Import Wizard)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        return self.env['ems.group'].create({
            'course': 1, 'acronym': 'TWIWB', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': other_space.id,
        })

    def test_import_prevail_left_default_archives_conflicting_self_session(self):
        # A teacher imported in one department's file, then imported again later in a DIFFERENT
        # department's file at the SAME day/time but for another subject/group/room, is a genuine
        # double-booking of that one teacher - 'classify_external_conflicts' can't see it (it only
        # ever looks for OTHER teachers sharing the same space), so this is exactly what
        # 'find_self_conflicts'-based detection is for. Updated 2026-08-05: no longer raises
        # unconditionally - it's now a 'db_conflicts' 'plain_conflict' line (different subject,
        # rooms genuinely differ here too - proving self-conflict detection doesn't depend on a
        # shared room, unlike the external case), defaulting to "left prevails", which archives the
        # first department's own template and keeps the second.
        other_group = self._create_self_conflict_setup()
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        first_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertTrue(first_template.active, "sanity check: department A's import created an active template")

        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{other_group.name} Group"/>',
            )),
        })

        # 'first_template' had exactly one schedule line - archiving it (the "left prevails"
        # default) leaves the template with none, so the now-empty template is archived too (see
        # '_continue_from_db_conflicts's own "archives/trims the template" comment).
        first_template.invalidate_recordset()
        self.assertFalse(first_template.active)
        second_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertTrue(second_template.active)
        # The CALENDAR itself must reflect the same resolution, not just the template - both
        # imports used the same Monday 09:00 slot, so the second one's own calendar write (still
        # 'combine', the default) should have replaced the first department's row at that exact
        # slot rather than leaving both.
        rows = self.teacher.resource_calendar_id.attendance_ids.filtered(lambda a: a.subject_id)
        self.assertEqual(rows.subject_id, self.other_subject)

    # --- import_mode: combine vs. replace (2026-09-02, see plans/calendar_pipeline_simplification.md) ---

    def _bounded_monday_file(self, email_and_name, hour1, subject, group, hour2):
        """A single-teacher planner file with one real class period (hour1) explicitly bounded by
        an EMPTY closing hour node at hour2 - 'hour_to' is inferred from 'hour2' instead of
        falling back to the generous company-wide 'schedule_import_last_entry_time' default
        (21:00) a lone period would get (needed so two files at genuinely different hours don't
        appear to overlap by construction), and the empty closing node itself never becomes a
        real entry/calendar row - it has no 'Subject'/'NonTeaching' child, so it never gets a
        'name' and is dropped by '_parse_schedule_entries' 's own 'if e.get("name")' filter.
        Deliberately NOT '_xml_teacher_subject_then_gap' (used by the room-swap test above): its
        own trailing gap is a REAL 'NonTeaching' entry, which (with no third node to bound IT in
        turn) inherits the same generous fallback itself and would still collide with a second
        file's own later period."""
        xml = (
            f'<root><T name="{email_and_name}">'
            '<D name="1 Monday">'
            f'<H name="1 {hour1}"><Subject name="{subject.code} {subject.name}"/>'
            f'<Students name="{group.name} Group"/></H>'
            f'<H name="2 {hour2}"></H>'
            '</D></T></root>'
        )
        return base64.b64encode(xml.encode())

    def test_import_mode_combine_default_preserves_unrelated_earlier_schedule(self):
        """'combine' (the default) never touches a weekday slot a later, separate import doesn't
        even mention - the fix for the real bug this whole feature grew out of (a teacher shared
        between two departments, imported in separate wizard runs, used to lose the first run's
        own contribution entirely)."""
        self._import({
            'attachment_ids': self._attachment_ids(self._bounded_monday_file(
                'test.wizard.teacher.import.wizard@example.com Someone', '09:00', self.subject, self.group, '10:00',
            )),
        })
        self._import({
            'attachment_ids': self._attachment_ids(self._bounded_monday_file(
                'test.wizard.teacher.import.wizard@example.com Someone', '11:00', self.other_subject, self.group, '12:00',
            )),
        })

        rows = self.teacher.resource_calendar_id.attendance_ids.filtered(lambda a: a.subject_id)
        self.assertEqual(set(rows.mapped('subject_id').ids), {self.subject.id, self.other_subject.id})
        templates = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])
        self.assertEqual(set(templates.mapped('subject_id').ids), {self.subject.id, self.other_subject.id})

    def test_import_mode_replace_drops_unrelated_earlier_schedule(self):
        """'replace': the developer's own explicit design ("si se quieren hacer ajustes, se deben
        hacer a mano") - a chosen import fully redescribes each teacher's schedule, on purpose,
        even for a slot it doesn't mention at all."""
        self._import({
            'attachment_ids': self._attachment_ids(self._bounded_monday_file(
                'test.wizard.teacher.import.wizard@example.com Someone', '09:00', self.subject, self.group, '10:00',
            )),
        })
        self._import({
            'attachment_ids': self._attachment_ids(self._bounded_monday_file(
                'test.wizard.teacher.import.wizard@example.com Someone', '11:00', self.other_subject, self.group, '12:00',
            )),
            'import_mode': 'replace',
        })

        rows = self.teacher.resource_calendar_id.attendance_ids.filtered(lambda a: a.subject_id)
        self.assertEqual(rows.subject_id, self.other_subject)
        templates = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('active', '=', True),
        ])
        self.assertEqual(templates.subject_id, self.other_subject)

    def test_import_mode_replace_skips_self_conflict_against_own_pre_existing_session(self):
        """A same-teacher self-conflict (see '_create_self_conflict_setup') against that teacher's
        OWN pre-existing session must never surface at all in 'replace' mode -
        '_write_teacher_schedule' unconditionally unlinks the ENTIRE existing weekday schedule for
        a 'replace'-mode teacher regardless of overlap, so whatever this row's resolution would
        have been, the DB row is gone at Import time anyway. Found 2026-09-06 from real test data:
        a same-subject, different-group file for an already-scheduled teacher wrongly surfaced as a
        'Co-teaching'/'Split session' conflict against their own about-to-be-replaced row. Contrast
        with 'test_import_prevail_left_default_archives_conflicting_self_session' - same fixture,
        default 'combine' mode, where this conflict is genuine and must still be resolved."""
        other_group = self._create_self_conflict_setup()
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{other_group.name} Group"/>',
            )),
            'import_mode': 'replace',
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (only one teacher in this batch)
        wizard.action_continue()  # internal_conflicts -> db_conflicts

        self.assertEqual(wizard.state, 'db_conflicts')
        self.assertFalse(wizard.external_conflict_line_ids)
        self.assertFalse(wizard.continue_disabled)

    def test_import_mode_replace_still_shows_genuine_external_conflict(self):
        """'replace' only ever wipes the BATCH's own teachers' schedules - a real room/time clash
        against a DIFFERENT teacher not in this batch at all must still surface and be resolved,
        regardless of import_mode. Mirrors 'test_continue_from_internal_conflicts_builds_co_
        teaching_line_against_existing_db_session', with 'import_mode=replace' this time - a
        regression guard for the fix above, which must only skip SELF collisions, never
        'external_candidates' ones."""
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
            'import_mode': 'replace',
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (nothing, only one teacher in this batch)
        wizard.action_continue()  # internal_conflicts -> db_conflicts, builds the external conflict line

        self.assertEqual(wizard.state, 'db_conflicts')
        line = wizard.external_conflict_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.kind, 'co_teaching_eligible')

    def test_import_mode_replace_full_apply_does_not_raise_on_own_pre_existing_session(self):
        """Reproduces a real reported bug (2026-09-06) that the two tests above did NOT catch: both
        only drove the wizard up to the 'db_conflicts' screen, never all the way to
        'import_planner_data()' - which is where the actual failure happened. '_apply_import' has
        its OWN separate self-conflict safety net ('find_self_conflicts', called from
        '_apply_import' directly, not through the wizard screen) that reads 'ems.attendance_schedule'
        - a model only brought in sync with the calendar by 'sync_from_schedule_batch', which runs
        AFTER this check, not before. In 'replace' mode this means the check always sees the
        teacher's now-stale PRE-import 'ems.attendance_schedule' rows (the calendar itself was
        already correctly rewritten earlier in the same call), producing the exact same false
        positive this whole fix is about - just one step later in the pipeline than the interactive
        screen. Must reach import_planner_data() to catch this - the true regression guard."""
        other_group = self._create_self_conflict_setup()
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{other_group.name} Group"/>',
            )),
            'import_mode': 'replace',
        })

        rows = self.teacher.resource_calendar_id.attendance_ids.filtered(lambda a: a.subject_id)
        self.assertEqual(rows.subject_id, self.other_subject)

    def test_import_two_files_together_merge_for_a_shared_teacher(self):
        """Confirmed directly with the developer (2026-09-02): a teacher shared between two
        departments (e.g. informática + administración), uploaded TOGETHER in the SAME wizard
        run, ends up with the union of both files - independent of import_mode, since both are
        part of this one run, not a later, separate re-import."""
        self._import({
            'attachment_ids': self._attachment_ids(
                self._bounded_monday_file(
                    'test.wizard.teacher.import.wizard@example.com Someone', '09:00', self.subject, self.group, '10:00',
                ),
                self._bounded_monday_file(
                    'test.wizard.teacher.import.wizard@example.com Someone', '11:00', self.other_subject, self.group, '12:00',
                ),
            ),
        })

        rows = self.teacher.resource_calendar_id.attendance_ids.filtered(lambda a: a.subject_id)
        self.assertEqual(set(rows.mapped('subject_id').ids), {self.subject.id, self.other_subject.id})
        templates = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])
        self.assertEqual(set(templates.mapped('subject_id').ids), {self.subject.id, self.other_subject.id})

    def test_wizard_starts_at_intro_state(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({})
        self.assertEqual(wizard.state, 'intro')
        self.assertFalse(wizard.parsed_entries_json)

    def test_action_continue_from_intro_caches_entries_and_advances_to_groups(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })

        wizard.action_continue()

        self.assertEqual(wizard.state, 'groups')
        self.assertTrue(wizard.parsed_entries_json)

    def test_action_continue_from_intro_raises_without_attachments(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({})
        with self.assertRaises(ValidationError):
            wizard.action_continue()
        self.assertEqual(wizard.state, 'intro')

    def test_action_continue_from_intro_dedups_same_unresolved_group_name(self):
        # The same typo'd group appearing in several hour-nodes across the batch is ONE correction
        # line, not one per occurrence - picking a group for it applies to all of them at once.
        xml = (
            '<root><T name="test.wizard.teacher.import.wizard@example.com Someone">'
            '<D name="1 Monday">'
            f'<H name="1 09:00"><Subject name="{self.subject.code} {self.subject.name}"/><Students name="NOPE Group"/></H>'
            f'<H name="2 10:00"><Subject name="{self.subject.code} {self.subject.name}"/><Students name="NOPE Group"/></H>'
            '</D></T></root>'
        )
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(base64.b64encode(xml.encode())),
        })

        wizard.action_continue()

        self.assertEqual(wizard.group_line_ids.mapped('raw_name'), ['NOPE Group'])

    def test_continue_from_groups_raises_when_a_line_has_no_group_picked(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="NOPE Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups

        with self.assertRaises(ValidationError) as capture:
            wizard.action_continue()

        self.assertIn('NOPE Group', str(capture.exception))
        self.assertEqual(wizard.state, 'groups')

    def test_continue_from_groups_resolves_pending_group_and_completes_import(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="NOPE Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.group_line_ids.group_id = self.group.id
        wizard.action_continue()  # groups -> subjects, substitutes the pick
        wizard.action_continue()  # subjects -> teachers (no mismatch in this fixture)

        self.assertEqual(wizard.state, 'teachers')
        self.assertNotIn('pending_group_names', wizard.parsed_entries_json)

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.group)

    def test_continue_from_groups_builds_subject_line_for_mismatched_subject(self):
        # Real error this screen was built for (2026-08-10): 'self.wrong_subject' isn't taught in
        # 'self.group's own study ('self.study'), so the mismatch must surface here instead of
        # only as a confusing error at the very end of the wizard.
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        self.assertEqual(wizard.state, 'subjects')
        self.assertEqual(len(wizard.subject_line_ids), 1)
        line = wizard.subject_line_ids
        self.assertEqual(line.raw_group_ids, self.group)
        # 'group_ids' (the editable, corrected pick) also defaults to the file's own group.
        self.assertEqual(line.group_ids, self.group)
        self.assertEqual(line.raw_subject_id, self.wrong_subject)
        # Defaults to the file's own (wrong) subject - a Many2one 'domain' only restricts what's
        # searchable when the field is reopened, it never hides an already-set out-of-domain value.
        self.assertEqual(line.subject_id, self.wrong_subject)
        self.assertEqual(line.allowed_subject_ids, self.subject | self.other_subject)

    def test_continue_from_subjects_correcting_the_group_alone_can_resolve_the_mismatch(self):
        # The other real variant of this same mismatch (developer feedback 2026-08-11): the FILE's
        # subject ('self.subject') is genuinely fine, it's 'self.wrong_group' (a different study,
        # teaching neither 'self.subject' nor 'self.other_subject') that's actually the mistake.
        # Correcting 'group_ids' alone, leaving 'subject_id' untouched, must resolve it on its own.
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.wrong_group.name}"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        line = wizard.subject_line_ids
        self.assertEqual(line.raw_group_ids, self.wrong_group)
        self.assertEqual(line.group_ids, self.wrong_group)
        self.assertEqual(line.raw_subject_id, self.subject)
        self.assertFalse(line.allowed_subject_ids)
        self.assertEqual(wizard.state, 'subjects')

        line.group_ids = [(6, 0, [self.group.id])]
        self.assertEqual(line.allowed_subject_ids, self.subject | self.other_subject)
        self.assertIn(line.subject_id.id, line.allowed_subject_ids.ids)

        wizard.action_continue()  # subjects -> teachers, the group correction alone resolved it
        self.assertEqual(wizard.state, 'teachers')
        node_cache = json.loads(wizard.parsed_entries_json)
        self.assertEqual(node_cache[0]['entries'][0]['group_ids'], [self.group.id])
        self.assertEqual(node_cache[0]['entries'][0]['subject_id'], self.subject.id)
        self.assertIn(self.group.name, node_cache[0]['entries'][0]['name'])

    def test_continue_from_groups_no_subject_line_when_subject_is_valid(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        self.assertFalse(wizard.subject_line_ids)

    def test_continue_from_groups_no_subject_line_for_a_group_with_no_study(self):
        # A reinforcement group has no 'study_id' at all - nothing to validate the subject
        # against, matching 'ems.attendance_template._check_subject_valid_for_all_studies's own
        # skip-if-no-study rule.
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
                f'<Students name="{self.reinforcement_group.name}"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        self.assertFalse(wizard.subject_line_ids)

    def test_continue_from_groups_dedups_subject_line_across_repeated_entries(self):
        # The same (group, wrong subject) pair repeated across two different days (a class
        # meeting the same slot every day of the week) is ONE correction line, not one per entry.
        xml = (
            '<root>'
            '<T name="test.wizard.teacher.import.wizard@example.com Someone">'
            '<D name="1 Monday"><H name="1 09:00">'
            f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
            f'<Students name="{self.group.name} Group"/>'
            '</H></D>'
            '<D name="2 Tuesday"><H name="1 09:00">'
            f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
            f'<Students name="{self.group.name} Group"/>'
            '</H></D>'
            '</T></root>'
        )
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(base64.b64encode(xml.encode())),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        self.assertEqual(len(wizard.subject_line_ids), 1)

    def test_continue_from_subjects_raises_when_subject_still_invalid(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        with self.assertRaises(Exception):
            wizard.action_continue()

    def test_continue_from_subjects_raises_translated_message_in_catalan(self):
        # Code (Python '_()') translations in this Odoo version are read straight from this
        # module's own checked-in 'i18n/ca_ES.po' at runtime, with no database round-trip - a
        # functional check under a real 'lang' context is the only way to actually prove this
        # message translates, since there's no DB column to verify via psql the way there is for
        # field_description/arch_db (see test_overall_summary_translates_group_resolution_and_
        # empty_block_into_catalan for the same pattern, established for this exact reason).
        wizard = self.env['ems.working_schedules_import_wizard'].with_context(lang='ca_ES').create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects

        with self.assertRaises(Exception) as cm:
            wizard.action_continue()
        self.assertIn('Seleccioneu una assignatura impartida', str(cm.exception))

    def test_continue_from_subjects_applies_correction_and_completes_import(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.wrong_subject.code} {self.wrong_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects
        wizard.subject_line_ids.subject_id = self.other_subject.id
        wizard.action_continue()  # subjects -> teachers, applies the correction

        self.assertEqual(wizard.state, 'teachers')
        node_cache = json.loads(wizard.parsed_entries_json)
        self.assertEqual(node_cache[0]['entries'][0]['subject_id'], self.other_subject.id)
        self.assertIn(self.other_subject.acronym, node_cache[0]['entries'][0]['name'])
        self.assertIn(self.group.name, node_cache[0]['entries'][0]['name'])

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertTrue(template)
        self.assertEqual(template.group_ids, self.group)

    def test_continue_from_subjects_builds_teacher_line_for_unresolved_email(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups (no Students, nothing to resolve there)
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers

        self.assertEqual(wizard.state, 'teachers')
        self.assertEqual(
            wizard.teacher_line_ids.mapped('raw_identifier'), ['unknown.import.wizard@example.com']
        )
        self.assertFalse(wizard.teacher_line_ids.employee_id)

    def test_continue_from_subjects_dedups_same_unresolved_email_across_teachers(self):
        # The same unresolved e-mail appearing in more than one <T> node (e.g. re-listed across
        # files, or a duplicate row) is ONE correction line, not one per occurrence.
        xml = (
            '<root>'
            '<T name="unknown.import.wizard@example.com Someone">'
            '<D name="1 Monday"><H name="1 09:00"><NonTeaching name="G Guard"/></H></D></T>'
            '<T name="unknown.import.wizard@example.com Someone Again">'
            '<D name="1 Monday"><H name="1 09:00"><NonTeaching name="G Guard"/></H></D></T>'
            '</root>'
        )
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(base64.b64encode(xml.encode())),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers

        self.assertEqual(
            wizard.teacher_line_ids.mapped('raw_identifier'), ['unknown.import.wizard@example.com']
        )

    def test_continue_from_subjects_lists_a_brand_new_pending_identification_code(self):
        # A code with no '@' and no existing employee behind it is a genuinely new placeholder -
        # since the 2026-08-10 merge (see '_pending_teacher_identifiers'), it gets its own
        # correction row right here, exactly like an unresolved e-mail, 'create_new' defaulting
        # to True - it's no longer resolved silently at Import with nothing to correct by hand.
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file('X1')),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers

        self.assertEqual(wizard.teacher_line_ids.mapped('raw_identifier'), ['X1'])
        self.assertTrue(wizard.teacher_line_ids.create_new)

    def test_continue_from_subjects_does_not_list_a_code_already_matching_a_pending_teacher(self):
        # Unlike a brand-new code, one that already reuses an EXISTING employee's
        # 'schedule_import_code' (a re-import of the same batch, or a previously-created pending
        # teacher) resolves silently - nothing to correct, same as an already-known e-mail.
        self.env['hr.employee'].create({
            'name': 'Test Wizard Already Pending Teacher (Import Wizard)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X1',
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file('X1')),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers

        self.assertFalse(wizard.teacher_line_ids)

    def test_continue_from_teachers_raises_when_a_line_has_no_teacher_picked(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; force the "neither" case

        with self.assertRaises(ValidationError) as capture:
            wizard.action_continue()

        self.assertIn('unknown.import.wizard@example.com', str(capture.exception))
        self.assertEqual(wizard.state, 'teachers')

    def test_continue_from_teachers_resolves_pending_email_and_completes_import(self):
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher Resolved (Import Wizard)',
            'employee_type': 'teacher',
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; untick it to pick a real teacher
        wizard.teacher_line_ids.employee_id = second_teacher.id
        wizard.action_continue()  # teachers -> internal_conflicts, substitutes the pick

        self.assertEqual(wizard.state, 'internal_conflicts')

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        self.assertTrue(second_teacher.resource_calendar_id.attendance_ids)

    def test_teacher_line_onchange_create_new_clears_employee_id(self):
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher Resolved (Import Wizard)',
            'employee_type': 'teacher',
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; untick it to pick a real teacher
        wizard.teacher_line_ids.employee_id = second_teacher.id

        wizard.teacher_line_ids._onchange_create_new()
        self.assertEqual(wizard.teacher_line_ids.employee_id, second_teacher)  # not ticked, unaffected

        wizard.teacher_line_ids.create_new = True
        wizard.teacher_line_ids._onchange_create_new()
        self.assertFalse(wizard.teacher_line_ids.employee_id)

    def test_continue_from_teachers_raises_when_neither_employee_nor_create_new(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; force the "neither" case

        with self.assertRaises(ValidationError) as capture:
            wizard.action_continue()

        self.assertIn('unknown.import.wizard@example.com', str(capture.exception))
        self.assertEqual(wizard.state, 'teachers')

    def test_continue_from_teachers_create_new_valid_without_employee_picked(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = True

        self.assertFalse(wizard.continue_disabled)
        wizard.action_continue()  # teachers -> internal_conflicts, no raise
        self.assertEqual(wizard.state, 'internal_conflicts')

    def test_continue_from_teachers_create_new_creates_pending_teacher_with_manual_email(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('genuinely.new.hire@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = True

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'genuinely.new.hire@example.com')])
        self.assertTrue(teacher)
        self.assertEqual(teacher.employee_type, 'teacher')
        self.assertTrue(teacher.pending_identification)
        self.assertEqual(teacher.work_email, 'genuinely.new.hire@example.com')
        self.assertTrue(teacher.google_ws_manual_email)
        self.assertTrue(teacher.resource_calendar_id.attendance_ids)

    def test_continue_from_teachers_create_new_reuses_same_pending_teacher_on_reimport(self):
        first_wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('genuinely.new.hire2@example.com Someone'),
            ),
        })
        first_wizard.action_continue()  # intro -> groups
        first_wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        first_wizard.action_continue()  # subjects -> teachers
        first_wizard.teacher_line_ids.create_new = True
        while first_wizard.state != 'summary':
            first_wizard.action_continue()
        first_wizard.import_planner_data()

        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('genuinely.new.hire2@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups

        # Once created (and NOT yet re-identified with a real personal e-mail), the same
        # 'schedule_import_code' still matches on work_email too now (see 'test_import_matches_by_email'-
        # style resolution) - so this identifier no longer even reaches the 'teachers' step's
        # unresolved-line list; it resolves automatically, exactly like a real already-known teacher.
        self.assertEqual(wizard.state, 'groups')
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        self.assertFalse(wizard.teacher_line_ids)

        self.assertEqual(
            self.env['hr.employee'].search_count([('schedule_import_code', '=', 'genuinely.new.hire2@example.com')]), 1
        )

    def _second_teacher(self, email='test.wizard.teacher2.import.wizard@example.com'):
        return self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 2 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': email,
        })

    def test_continue_from_teachers_builds_co_teaching_line_for_same_subject_same_group(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts, builds the conflict line

        self.assertEqual(wizard.state, 'internal_conflicts')
        self.assertEqual(len(wizard.internal_conflict_line_ids), 1)
        line = wizard.internal_conflict_line_ids
        self.assertEqual(line.kind, 'co_teaching_eligible')
        self.assertEqual(line.resolution, 'co_teaching')
        self.assertFalse(wizard.continue_disabled)

    def test_left_group_key_ignores_group_for_the_same_teacher_and_subject(self):
        # Regression guard for a real bug found the hard way (2026-08-10): 'left_group_key' must
        # stay IDENTICAL across two pairs sharing the same left teacher+subject, even when the
        # left side's own GROUP differs between the two pairs - otherwise the grouped-cards view's
        # whole "group by teacher+subject, ignoring group" premise silently breaks for exactly the
        # realistic case that motivated it (one teacher double-booked across several different
        # classes). Deliberately does NOT reuse the exact same left entry across both pairs (see
        # feedback_vary_the_ignored_dimension_in_fixtures memory) - self.teacher's own two entries
        # here use two DIFFERENT groups (self.group/self.single_group), on two different days, each
        # colliding with a different second teacher in the same shared room.
        second_teacher = self._second_teacher()
        third_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 3 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher3.import.wizard@example.com',
        })
        xml = (
            '<root>'
            f'<T name="{self.teacher.work_email} Someone">'
            f'<D name="1 Monday"><H name="1 09:00"><Subject name="{self.subject.code} {self.subject.name}"/>'
            f'<Students name="{self.group.name} Group"/></H></D>'
            f'<D name="2 Tuesday"><H name="1 09:00"><Subject name="{self.subject.code} {self.subject.name}"/>'
            f'<Students name="{self.single_group.name} Group"/></H></D>'
            '</T>'
            f'<T name="{second_teacher.work_email} Someone Else">'
            f'<D name="1 Monday"><H name="1 09:00"><Subject name="{self.subject.code} {self.subject.name}"/>'
            f'<Students name="{self.group.name} Group"/></H></D>'
            '</T>'
            f'<T name="{third_teacher.work_email} Someone Third">'
            f'<D name="2 Tuesday"><H name="1 09:00"><Subject name="{self.subject.code} {self.subject.name}"/>'
            f'<Students name="{self.single_group.name} Group"/></H></D>'
            '</T>'
            '</root>'
        )
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(base64.b64encode(xml.encode())),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts

        self.assertEqual(len(wizard.internal_conflict_line_ids), 2)
        group_keys = wizard.internal_conflict_line_ids.mapped('left_group_key')
        self.assertEqual(len(set(group_keys)), 1, "left_group_key must be identical regardless of the left side's own group")
        left_labels = wizard.internal_conflict_line_ids.mapped('left_label')
        self.assertEqual(len(set(left_labels)), 2, "left_label itself must still differ (it includes the group)")

    def test_continue_from_teachers_builds_desdoble_line_for_same_subject_different_group(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts

        line = wizard.internal_conflict_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.kind, 'desdoble_eligible')
        self.assertEqual(line.resolution, 'reassign_rooms')
        # Both sides pre-filled with the SAME colliding room - self.group and self.single_group
        # share 'self.space' - so left alone (untouched defaults), this is NOT actually resolved.
        self.assertEqual(line.left_space_id, self.space)
        self.assertEqual(line.right_space_id, self.space)
        self.assertTrue(wizard.continue_disabled)

    def test_continue_from_teachers_builds_plain_conflict_line_for_different_subject(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts

        line = wizard.internal_conflict_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.kind, 'plain_conflict')
        # Both entries share 'self.group', so this is a genuine same-room clash - defaults to
        # 'reassign_rooms' (developer feedback 2026-08-06), pre-filled with the group's own room on
        # both sides (not yet resolved, since both sides are still identical).
        self.assertEqual(line.resolution, 'reassign_rooms')
        self.assertEqual(line.left_space_id, self.space)
        self.assertEqual(line.right_space_id, self.space)
        self.assertTrue(wizard.continue_disabled)

    def test_continue_from_teachers_builds_self_conflict_line_when_two_identifiers_resolve_to_same_employee(self):
        # Developer feedback (2026-08-10, hit against a real import): manually assigning two
        # DIFFERENT raw identifiers to the SAME existing employee (the "same person as" merge
        # confirmed earlier this session) can leave that one real teacher double-booked - and
        # neither '_find_internal_conflicts' (room-based only) nor 'ems.attendance_template.
        # find_self_conflicts' (DB-only, see its own docstring: "does not catch two overlapping
        # entries for the same teacher within the single batch") ever caught it - it surfaced as a
        # raw, unworded check_overlap ValidationError at the final Import click instead of a
        # resolvable line here.
        other_group = self._create_self_conflict_setup()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'SELFX1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                'SELFX2',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{other_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers

        self.assertEqual(sorted(wizard.teacher_line_ids.mapped('raw_identifier')), ['SELFX1', 'SELFX2'])
        wizard.teacher_line_ids.write({'create_new': False, 'employee_id': self.teacher.id})
        wizard.action_continue()  # teachers -> internal_conflicts

        self.assertEqual(wizard.state, 'internal_conflicts')
        self.assertEqual(len(wizard.internal_conflict_line_ids), 1)
        line = wizard.internal_conflict_line_ids
        self.assertEqual(line.kind, 'self_conflict')
        self.assertEqual(line.resolution, 'prevail_left')
        self.assertFalse(line.left_space_id)
        self.assertFalse(line.right_space_id)
        self.assertFalse(wizard.continue_disabled)

    def test_continue_from_teachers_no_self_conflict_line_for_two_different_employees(self):
        # Regression guard: the exact same overlapping-time/different-room shape, but the two
        # identifiers resolve to two DIFFERENT real employees (the ordinary co-teaching-across-
        # different-groups-and-subjects case, i.e. a genuine 'plain_conflict' room clash is NOT
        # what's being tested here - these two entries don't even share a room) - no self_conflict
        # line should ever appear since they are not the same physical teacher.
        second_teacher = self._second_teacher()
        other_group = self._create_self_conflict_setup()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{other_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts

        self.assertFalse(wizard.internal_conflict_line_ids)

    def test_continue_from_internal_conflicts_self_conflict_prevail_left_keeps_left_only(self):
        other_group = self._create_self_conflict_setup()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'SELFX1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                'SELFX2',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{other_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.write({'create_new': False, 'employee_id': self.teacher.id})
        wizard.action_continue()  # teachers -> internal_conflicts (self_conflict, defaults to prevail_left)

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        templates = self.env['ems.attendance_template'].search([('teacher_ids', '=', self.teacher.id)])
        self.assertEqual(templates.mapped('subject_id'), self.subject)
        self.assertEqual(templates.group_ids, self.group)

    def test_continue_from_internal_conflicts_self_conflict_keeps_the_winning_calendar_row(self):
        """Regression test (2026-09-02): two XML teacher nodes ('SELFX1'/'SELFX2') resolving to the
        SAME real teacher, at the same slot - a genuine self-conflict. Each node's own parsed
        'attendance_ids' leads with a bare '(5,)' unlink-all command (see
        '_parse_schedule_entries'); writing it once per NODE instead of once per REAL teacher let
        the second node's write (down to just '[[5]]' once prevail_left drops its one entry) wipe
        the first node's calendar row the moment it was written - found while making the template
        sync read the calendar back (reverted, see plans/calendar_pipeline_simplification.md), but
        this specific within-batch bug was real and worth keeping fixed on its own. Checks the
        CALENDAR directly (the other tests around this one only ever checked the resulting
        template)."""
        other_group = self._create_self_conflict_setup()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'SELFX1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                'SELFX2',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{other_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.write({'create_new': False, 'employee_id': self.teacher.id})
        wizard.action_continue()  # teachers -> internal_conflicts (self_conflict, defaults to prevail_left)

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        rows = self.teacher.resource_calendar_id.attendance_ids.filtered(lambda row: row.subject_id)
        self.assertEqual(rows.subject_id, self.subject)
        self.assertEqual(rows.group_ids, self.group)

    def test_continue_from_internal_conflicts_self_conflict_prevail_right_keeps_right_only(self):
        other_group = self._create_self_conflict_setup()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'SELFX1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                'SELFX2',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{other_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.write({'create_new': False, 'employee_id': self.teacher.id})
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.internal_conflict_line_ids.resolution = 'prevail_right'

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        templates = self.env['ems.attendance_template'].search([('teacher_ids', '=', self.teacher.id)])
        self.assertEqual(templates.mapped('subject_id'), self.other_subject)
        self.assertEqual(templates.group_ids, other_group)

    def test_continue_from_internal_conflicts_self_conflict_reassign_rooms_invalid(self):
        # 'self_conflict' never supports 'reassign_rooms' - the two rooms already genuinely differ
        # by construction; reassigning either fixes nothing since the real problem is one teacher
        # needed in two places at once, not a shared room (same reasoning already documented for
        # the DB-side self-conflict case).
        other_group = self._create_self_conflict_setup()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'SELFX1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                'SELFX2',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{other_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.write({'create_new': False, 'employee_id': self.teacher.id})
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.internal_conflict_line_ids.write({
            'resolution': 'reassign_rooms',
            'left_space_id': self.space.id,
            'right_space_id': other_group.space_id.id,
        })

        with self.assertRaises(ValidationError):
            wizard.action_continue()

    def test_find_internal_conflicts_excludes_non_teaching_entries(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<NonTeaching name="G Guard"/>',
                second_teacher.work_email,
                '<NonTeaching name="G Guard"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts

        self.assertFalse(wizard.internal_conflict_line_ids)
        self.assertFalse(wizard.continue_disabled)

    def test_continue_from_internal_conflicts_raises_for_resolution_invalid_for_kind(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.internal_conflict_line_ids.resolution = 'co_teaching'  # invalid for a plain_conflict

        with self.assertRaises(ValidationError) as capture:
            wizard.action_continue()

        self.assertIn(wizard.internal_conflict_line_ids.left_label, str(capture.exception))
        self.assertEqual(wizard.state, 'internal_conflicts')

    def test_continue_from_internal_conflicts_raises_for_reassign_rooms_same_room(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts, defaults left/right to the SAME room

        with self.assertRaises(ValidationError):
            wizard.action_continue()

    def test_continue_from_internal_conflicts_prevail_left_drops_right_entry_and_completes_import(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (default resolution: reassign_rooms)
        wizard.internal_conflict_line_ids.resolution = 'prevail_left'

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)
        self.assertFalse(second_teacher.resource_calendar_id.attendance_ids)

    def test_continue_from_internal_conflicts_reassign_rooms_writes_different_rooms_and_completes_import(self):
        second_teacher = self._second_teacher()
        other_space = self.env['ems.space'].create({
            'code': 'TWIW-DESDOBLE', 'name': 'Test Space Desdoble (Import Wizard)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.internal_conflict_line_ids.right_space_id = other_space.id
        self.assertFalse(wizard.continue_disabled)

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        left_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        right_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', second_teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(left_template.attendance_schedule_ids.space_id, self.space)
        self.assertEqual(right_template.attendance_schedule_ids.space_id, other_space)

    def test_continue_from_internal_conflicts_co_teaching_merges_both_teachers(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (default resolution: co_teaching)

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)
        self.assertTrue(second_teacher.resource_calendar_id.attendance_ids)
        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(set(template.teacher_ids.ids), {self.teacher.id, second_teacher.id})

    def test_continue_from_internal_conflicts_builds_co_teaching_line_against_existing_db_session(self):
        # 'self.teacher' already has an active session; a NEW, different teacher submits the exact
        # same (subject, group, slot) - this is co-teaching against an EXTERNAL (not-in-this-batch)
        # teacher's existing schedule, not a within-batch collision.
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (nothing, only one teacher in this batch)
        wizard.action_continue()  # internal_conflicts -> db_conflicts, builds the external conflict line

        self.assertEqual(wizard.state, 'db_conflicts')
        line = wizard.external_conflict_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.kind, 'co_teaching_eligible')
        self.assertEqual(line.resolution, 'co_teaching')
        self.assertFalse(wizard.continue_disabled)

    def test_continue_from_internal_conflicts_builds_desdoble_line_against_existing_db_session(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                # 'self.single_group' shares 'self.space' with 'self.group' - same room, different group.
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts

        line = wizard.external_conflict_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.kind, 'desdoble_eligible')
        self.assertEqual(line.resolution, 'reassign_rooms')
        self.assertEqual(line.left_space_id, self.space)
        self.assertEqual(line.right_space_id, self.space)
        self.assertTrue(wizard.continue_disabled)

    def test_continue_from_db_conflicts_raises_for_resolution_invalid_for_kind(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.resolution = 'co_teaching'  # invalid for a plain_conflict

        with self.assertRaises(ValidationError):
            wizard.action_continue()
        self.assertEqual(wizard.state, 'db_conflicts')

    def test_continue_from_db_conflicts_prevail_right_drops_new_entry_and_completes_import(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        existing_schedule = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
        ])
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.resolution = 'prevail_right'

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        existing_schedule.invalidate_recordset()
        self.assertTrue(existing_schedule.active)
        self.assertFalse(second_teacher.resource_calendar_id.attendance_ids)

    def test_continue_from_db_conflicts_reassign_rooms_without_has_sessions_writes_in_place(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        existing_schedule = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
        ])
        self.assertFalse(existing_schedule.has_sessions)
        other_space = self.env['ems.space'].create({
            'code': 'TWIW-REASSIGN', 'name': 'Test Space Reassign (Import Wizard)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.right_space_id = other_space.id

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        existing_schedule.invalidate_recordset()
        self.assertTrue(existing_schedule.active)
        self.assertEqual(existing_schedule.space_id, other_space)

    def test_continue_from_db_conflicts_reassign_rooms_with_has_sessions_archives_and_clones(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        existing_schedule = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
        ])
        self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': existing_schedule.id,
            'date': date(2026, 1, 5),
            'mode': 'scheduled',
            'session_teacher_id': self.teacher.id,
        })
        self.assertTrue(existing_schedule.has_sessions)

        other_space = self.env['ems.space'].create({
            'code': 'TWIW-REASSIGN2', 'name': 'Test Space Reassign 2 (Import Wizard)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.right_space_id = other_space.id

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        existing_schedule.invalidate_recordset()
        self.assertFalse(existing_schedule.active, "the original, locked line was archived, not edited in place")
        new_schedule = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
            ('attendance_template_id.subject_id', '=', self.subject.id),
            ('active', '=', True),
        ])
        self.assertNotEqual(new_schedule, existing_schedule)
        self.assertEqual(new_schedule.space_id, other_space)
        self.assertTrue(existing_schedule.attendance_session_ids, "the original session history is preserved on the archived line")

    # --- "Resolve teachers" also lists placeholder codes (2026-08-10 merge) -------------------

    def test_teachers_step_lists_placeholder_code_teacher(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'X1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        while wizard.state != 'teachers':
            wizard.action_continue()

        self.assertIn('X1', wizard.teacher_line_ids.mapped('raw_identifier'))

    def test_teachers_step_lists_create_new_ticked_email(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        while wizard.state != 'teachers':
            wizard.action_continue()

        self.assertIn('unknown.import.wizard@example.com', wizard.teacher_line_ids.mapped('raw_identifier'))
        self.assertTrue(wizard.teacher_line_ids.create_new)  # defaults to True, never touched by hand

    def test_teachers_step_empty_when_every_teacher_already_exists(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        while wizard.state != 'teachers':
            wizard.action_continue()

        self.assertFalse(wizard.teacher_line_ids)

    def test_teachers_step_dedups_the_same_teacher_across_two_files(self):
        # Different weekday on the second file - deliberately avoids a genuine same-time
        # double-booking, which would raise its own (unrelated) internal-conflict resolution
        # requirement at the next screen, not what this dedup test is about.
        second_file = base64.b64encode((
            '<root><T name="X2"><D name="2 Tuesday"><H name="1 09:00">'
            f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
            f'<Students name="{self.single_group.name} Group"/>'
            '</H></D></T></root>'
        ).encode())
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file_with_hour_node(
                    'X2',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                ),
                second_file,
            ),
        })
        while wizard.state != 'teachers':
            wizard.action_continue()

        self.assertEqual(wizard.teacher_line_ids.mapped('raw_identifier').count('X2'), 1)

    def test_continue_from_teachers_same_employee_assigned_to_two_different_identifiers(self):
        """Developer question (2026-08-10): 'me han puesto al mismo profe de forma diferente...
        si desmarco New a los dos y les pongo el mismo profesor que ya existe, ¿eso funcionaría?'
        - yes: 'identifier_to_employee' in '_continue_from_teachers' is a plain dict with no
        uniqueness constraint on the employee side, so two different raw identifiers (two
        placeholder codes here) both resolving to the SAME existing employee both correctly end
        up with that one employee's id on their own node_cache item, with nothing duplicated."""
        real_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher Same Person (Import Wizard)',
            'employee_type': 'teacher',
        })
        second_file = base64.b64encode((
            '<root><T name="X4"><D name="2 Tuesday"><H name="1 09:00">'
            f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
            f'<Students name="{self.single_group.name} Group"/>'
            '</H></D></T></root>'
        ).encode())
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file_with_hour_node(
                    'X3',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                ),
                second_file,
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers

        self.assertEqual(sorted(wizard.teacher_line_ids.mapped('raw_identifier')), ['X3', 'X4'])
        wizard.teacher_line_ids.write({'create_new': False, 'employee_id': real_teacher.id})
        wizard.action_continue()  # teachers -> internal_conflicts, both identifiers resolve to real_teacher

        node_cache = json.loads(wizard.parsed_entries_json)
        resolved_employee_ids = {item['employee_id'] for item in node_cache}
        self.assertEqual(resolved_employee_ids, {real_teacher.id})

        while wizard.state != 'summary':
            wizard.action_continue()
        wizard.import_planner_data()

        self.assertEqual(
            self.env['hr.employee'].search([('name', '=', real_teacher.name)]), real_teacher,
            "no duplicate employee was created for the second identifier",
        )
        self.assertTrue(real_teacher.resource_calendar_id.attendance_ids)

    # --- "Overall summary" -----------------------------------------------------

    def test_summary_lists_teacher_matched_by_email(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn(self.teacher.name, wizard.overall_summary_html)
        self.assertIn('test.wizard.teacher.import.wizard@example.com', wizard.overall_summary_html)
        # The block's own explanatory note (developer feedback: "deberíamos aclarar cómo se verán
        # afectados") must actually render alongside the affected teacher, not just the count/name.
        self.assertIn("Their weekly schedule will be synced with this file's content", wizard.overall_summary_html)

    def test_summary_attaches_a_downloadable_csv(self):
        """Mirrors 'test_apply_attaches_the_rollback_csv' in test_course_transition.py - the
        same pattern ('summary_file'/'summary_file_name', auto-downloaded via the
        'auto_download_binary' widget), applied here to the import wizard's own last step."""
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertTrue(wizard.summary_file)
        self.assertTrue(wizard.summary_file_name.endswith('.csv'))
        content = base64.b64decode(wizard.summary_file).decode('utf-8-sig')
        self.assertIn(self.teacher.name, content)
        self.assertIn('test.wizard.teacher.import.wizard@example.com', content)

    def test_summary_lists_teacher_resolved_on_the_teachers_step(self):
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown2.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        # 'create_new' defaults to True - picking an existing teacher instead means unticking it,
        # same as the view's own @api.onchange would do when a real value gets picked.
        wizard.teacher_line_ids.create_new = False
        wizard.teacher_line_ids.employee_id = second_teacher.id
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn(second_teacher.name, wizard.overall_summary_html)
        # Not just listed somewhere - the "unresolved teacher e-mail(s) resolved" block's own
        # detail line must say WHICH real teacher the raw e-mail was resolved to.
        self.assertIn('unknown2.import.wizard@example.com resolved to %s' % second_teacher.name, wizard.overall_summary_html)

    def test_summary_group_block_shows_which_group_a_raw_name_was_resolved_to(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'X4',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="TourOverallSummaryGroup Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.group_line_ids.group_id = self.group.id
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn('TourOverallSummaryGroup Group resolved to %s' % self.group.display_name, wizard.overall_summary_html)

    def test_summary_teacher_block_notes_a_create_new_row_as_a_new_pending_teacher(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown3.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers - 'create_new' defaults to True
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn('unknown3.import.wizard@example.com will be created as a new pending teacher', wizard.overall_summary_html)
        # The block's own explanatory note (developer feedback: "que quede claro que significa
        # que son 'pending' y que después se les podrá cambiar el nombre, crear su cuenta, etc.")
        # must actually render alongside the pending teacher, not just the count/identifier.
        self.assertIn('click Generate Google account', wizard.overall_summary_html)

    def test_summary_conflict_block_shows_the_resolution_actually_chosen(self):
        second_teacher = self._second_teacher()
        other_space = self.env['ems.space'].create({
            'code': 'TWIW-SUMMARY-CONFLICT', 'name': 'Test Space Summary Conflict (Import Wizard)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_two_teachers_same_slot(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.internal_conflict_line_ids.right_space_id = other_space.id
        while wizard.state != 'summary':
            wizard.action_continue()

        line = wizard.internal_conflict_line_ids
        self.assertIn(
            '%s vs. %s --&gt; Split session: resolved as Reassign rooms - rooms: %s / %s' % (
                line.left_label, line.right_label, self.space.display_name, other_space.display_name,
            ),
            wizard.overall_summary_html,
        )

    def test_summary_empty_when_only_pending_teachers(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'X3',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn('0 existing teacher(s) affected', wizard.overall_summary_html)
        self.assertIn('Nothing to show here.', wizard.overall_summary_html)

    def test_overall_summary_translates_group_resolution_and_empty_block_into_catalan(self):
        # Code (Python '_()') translations in this Odoo version are read straight from this
        # module's own checked-in 'i18n/ca_ES.po' at runtime (see 'CodeTranslations.
        # get_python_translations' - no database round-trip at all, unlike field/view
        # translations) - a functional check under a real 'lang' context is the only way to
        # actually prove a new detail-line string translates, since there's no DB column to
        # verify via psql the way there is for field_description/arch_db.
        wizard = self.env['ems.working_schedules_import_wizard'].with_context(lang='ca_ES').create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'X6',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="TourCatalanSummaryGroup Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.group_line_ids.group_id = self.group.id
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn("TourCatalanSummaryGroup Group s'ha resolt a %s" % self.group.display_name, wizard.overall_summary_html)
        self.assertIn('Aquí no hi ha res a mostrar.', wizard.overall_summary_html)
        # The downloadable CSV's own header row must translate too - same mechanism, same file.
        content = base64.b64decode(wizard.summary_file).decode('utf-8-sig')
        self.assertIn('Categoria,Detall', content)

    def test_overall_summary_shows_zero_counts_when_nothing_to_resolve(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn('0 unresolved group name(s) resolved', wizard.overall_summary_html)
        self.assertIn('0 pending teacher(s) will be created', wizard.overall_summary_html)
        self.assertIn('0 file conflict(s) resolved', wizard.overall_summary_html)
        self.assertIn('0 existing schedule conflict(s) resolved', wizard.overall_summary_html)
        self.assertIn('1 existing teacher(s) affected', wizard.overall_summary_html)

    def test_overall_summary_reflects_pending_and_resolved_group_counts(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'X4',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="TourOverallSummaryGroup Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.group_line_ids.group_id = self.group.id
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers (resolves the unresolved group name)
        while wizard.state != 'summary':
            wizard.action_continue()

        self.assertIn('1 unresolved group name(s) resolved', wizard.overall_summary_html)
        self.assertIn('1 pending teacher(s) will be created', wizard.overall_summary_html)
        self.assertIn('0 existing teacher(s) affected', wizard.overall_summary_html)

    def test_continue_disabled_true_at_intro_without_attachment(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({})
        self.assertTrue(wizard.continue_disabled)

    def test_continue_disabled_false_at_intro_with_attachment(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        self.assertFalse(wizard.continue_disabled)

    def test_continue_disabled_true_at_groups_with_unresolved_line(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="NOPE Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        self.assertEqual(wizard.state, 'groups')
        self.assertTrue(wizard.continue_disabled)

    def test_continue_disabled_false_at_groups_once_resolved(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="NOPE Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.group_line_ids.group_id = self.group.id
        self.assertFalse(wizard.continue_disabled)

    def test_continue_disabled_true_at_groups_with_unassigned_classroom(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        self.assertEqual(wizard.state, 'groups')
        self.assertTrue(wizard.continue_disabled)

    def test_continue_disabled_false_at_groups_once_classroom_assigned(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.space_line_ids.space_id = self.space.id
        self.assertFalse(wizard.continue_disabled)

    def test_continue_disabled_false_at_groups_with_nothing_to_resolve(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        self.assertFalse(wizard.group_line_ids)
        self.assertFalse(wizard.continue_disabled)

    def test_continue_disabled_false_for_placeholder_states(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers (known e-mail, nothing to resolve either)
        wizard.action_continue()  # teachers -> internal_conflicts (single teacher, no collision possible)
        wizard.action_continue()  # internal_conflicts -> db_conflicts (no existing session to collide with)
        wizard.action_continue()  # db_conflicts -> summary
        self.assertFalse(wizard.continue_disabled)

    def test_continue_disabled_true_at_db_conflicts_with_unresolved_line(self):
        self._import({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self._second_teacher()
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                second_teacher.work_email,
                f'<Subject name="{self.subject.code} {self.subject.name}"/><Students name="{self.single_group.name} Group"/>',
            )),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        self.assertEqual(wizard.state, 'db_conflicts')
        self.assertTrue(wizard.continue_disabled)

    def test_continue_disabled_true_at_teachers_with_unresolved_line(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; force the unresolved case
        self.assertEqual(wizard.state, 'teachers')
        self.assertTrue(wizard.continue_disabled)

    def test_continue_disabled_false_at_teachers_once_resolved(self):
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher Resolved 2 (Import Wizard)',
            'employee_type': 'teacher',
        })
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> subjects (no mismatch in this fixture)
        wizard.action_continue()  # subjects -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; untick it to pick a real teacher
        wizard.teacher_line_ids.employee_id = second_teacher.id
        self.assertFalse(wizard.continue_disabled)

    def test_action_continue_walks_every_state_in_order_with_nothing_to_resolve(self):
        # All 6 steps have real logic now ("Pending teachers" was merged into "Resolve teachers"
        # 2026-08-10) - this just confirms the full STATE_SEQUENCE order end to end for a batch
        # with nothing to resolve at any step (a single, already-known teacher, no '<Students>' at
        # all, so 'groups' has nothing, and no collision is possible at either conflicts screen -
        # that needs at least two different teachers in the batch, or an existing DB session,
        # neither of which exists here).
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        expected_sequence = ['groups', 'subjects', 'teachers', 'internal_conflicts', 'db_conflicts', 'summary']
        for expected_state in expected_sequence:
            wizard.action_continue()
            self.assertEqual(wizard.state, expected_state)

    def test_import_planner_data_writes_from_the_cache_built_at_intro(self):
        # The final step reads 'parsed_entries_json' - built once, at intro - rather than
        # re-parsing 'attachment_ids' from scratch, so this must still work correctly even after
        # the statusbar has moved well past the intro screen.
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups, caches the parsed entries
        for _step in range(5):  # groups -> ... -> summary
            wizard.action_continue()
        self.assertEqual(wizard.state, 'summary')

        wizard.import_planner_data()

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)
