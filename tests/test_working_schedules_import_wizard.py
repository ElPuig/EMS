import base64
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
        while wizard.state != 'override_info':
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
        self._import({
            'attachment_ids': [(6, 0, [self.env['ir.attachment'].create({
                'name': 'planner_shared_room_swapped.xml', 'datas': base64.b64encode(xml_swapped.encode()),
            }).id])],
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
        while wizard.state != 'override_info':
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
        while wizard.state != 'override_info':
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
        # would surface instead of naming which group is missing a classroom. Deferred to the final
        # Import step since 2026-08-05 - not something the intro screen checks any more.
        with self.assertRaises(ValidationError) as capture:
            self._import({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    f'<Students name="{self.spaceless_group.name} Group"/>',
                )),
            })

        self.assertIn(self.spaceless_group.name, str(capture.exception))

    def test_continue_from_intro_unknown_group_defers_to_groups_step(self):
        # Updated 2026-08-05: an unresolvable group no longer blocks the intro screen - it's
        # deferred to the 'groups' step instead (see 'plans/working_schedule_import_redesign.md's
        # step 2). Unlike an unknown e-mail (deferred all the way to Import) or a missing classroom,
        # this one still needed '_parse_schedule_entries' itself to keep producing entries for the
        # node instead of raising - see 'pending_group_names'.
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
        wizard.action_continue()  # groups -> teachers, substitutes the pick

        self.assertEqual(wizard.state, 'teachers')
        self.assertNotIn('pending_group_names', wizard.parsed_entries_json)

        while wizard.state != 'override_info':
            wizard.action_continue()
        wizard.import_planner_data()

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.group)

    def test_continue_from_groups_builds_teacher_line_for_unresolved_email(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups (no Students, nothing to resolve there)
        wizard.action_continue()  # groups -> teachers

        self.assertEqual(wizard.state, 'teachers')
        self.assertEqual(
            wizard.teacher_line_ids.mapped('raw_identifier'), ['unknown.import.wizard@example.com']
        )
        self.assertFalse(wizard.teacher_line_ids.employee_id)

    def test_continue_from_groups_dedups_same_unresolved_email_across_teachers(self):
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
        wizard.action_continue()  # groups -> teachers

        self.assertEqual(
            wizard.teacher_line_ids.mapped('raw_identifier'), ['unknown.import.wizard@example.com']
        )

    def test_continue_from_groups_does_not_list_a_pending_identification_code(self):
        # A code with no '@' isn't a problem for THIS screen - it's expected input, handled
        # automatically at the final Import step (creates a pending-identification teacher).
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file('X1')),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> teachers

        self.assertFalse(wizard.teacher_line_ids)

    def test_continue_from_teachers_raises_when_a_line_has_no_teacher_picked(self):
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('unknown.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; untick it to pick a real teacher
        wizard.teacher_line_ids.employee_id = second_teacher.id
        wizard.action_continue()  # teachers -> internal_conflicts, substitutes the pick

        self.assertEqual(wizard.state, 'internal_conflicts')

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
        wizard.teacher_line_ids.create_new = True

        while wizard.state != 'override_info':
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
        first_wizard.action_continue()  # groups -> teachers
        first_wizard.teacher_line_ids.create_new = True
        while first_wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts, builds the conflict line

        self.assertEqual(wizard.state, 'internal_conflicts')
        self.assertEqual(len(wizard.internal_conflict_line_ids), 1)
        line = wizard.internal_conflict_line_ids
        self.assertEqual(line.kind, 'co_teaching_eligible')
        self.assertEqual(line.resolution, 'co_teaching')
        self.assertFalse(wizard.continue_disabled)

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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (default resolution: reassign_rooms)
        wizard.internal_conflict_line_ids.resolution = 'prevail_left'

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.internal_conflict_line_ids.right_space_id = other_space.id
        self.assertFalse(wizard.continue_disabled)

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts (default resolution: co_teaching)

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.resolution = 'prevail_right'

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.right_space_id = other_space.id

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers
        wizard.action_continue()  # teachers -> internal_conflicts
        wizard.action_continue()  # internal_conflicts -> db_conflicts
        wizard.external_conflict_line_ids.right_space_id = other_space.id

        while wizard.state != 'override_info':
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
        wizard.action_continue()  # groups -> teachers (known e-mail, nothing to resolve either)
        wizard.action_continue()  # teachers -> internal_conflicts (single teacher, no collision possible)
        wizard.action_continue()  # internal_conflicts -> db_conflicts (no existing session to collide with)
        wizard.action_continue()  # db_conflicts -> pending_info (still a placeholder)
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
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
        wizard.action_continue()  # groups -> teachers
        wizard.teacher_line_ids.create_new = False  # 'create_new' defaults True; untick it to pick a real teacher
        wizard.teacher_line_ids.employee_id = second_teacher.id
        self.assertFalse(wizard.continue_disabled)

    def test_action_continue_placeholder_steps_advance_one_state_at_a_time(self):
        # Steps 'pending_info' and 'override_info'... wait, 'override_info' has real Import logic
        # too (see 'import_planner_data') - only 'pending_info' has no real logic yet (see
        # plans/working_schedule_import_redesign.md) - 'action_continue' just advances the
        # statusbar for it. 'intro', 'groups', 'teachers', 'internal_conflicts' and 'db_conflicts'
        # are the five real steps built so far (this file's XML has a single, already-known
        # teacher with no '<Students>' at all, so there's nothing to resolve at 'groups' and no
        # possible collision at either conflicts screen - a collision needs at least two different
        # teachers in the batch, or an existing DB session, neither of which exists here).
        wizard = self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })
        wizard.action_continue()  # intro -> groups
        wizard.action_continue()  # groups -> teachers (nothing to resolve)
        wizard.action_continue()  # teachers -> internal_conflicts (nothing to resolve)
        wizard.action_continue()  # internal_conflicts -> db_conflicts (nothing to resolve)

        expected_sequence = ['pending_info', 'override_info']
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
        for _step in range(5):  # groups -> ... -> override_info
            wizard.action_continue()
        self.assertEqual(wizard.state, 'override_info')

        wizard.import_planner_data()

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)
