import base64

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
        cls.bare_acronym_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.bare_acronym_study.id,
            'space_id': cls.space.id,
        })

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
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)

    def test_import_unknown_email_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'attachment_ids': self._attachment_ids(
                    self._xml_file('unknown.import.wizard@example.com Someone'),
                ),
            })

    def test_import_placeholder_code_creates_pending_teacher(self):
        # A code with no '@' (e.g. "X1") isn't a real e-mail typo: the external planner uses it for a
        # not-yet-staffed post, so a pending-identification teacher is created instead of raising. The
        # raw XML 'name' attribute for this kind of row is just the code itself, with no discardable
        # label after it (unlike a real teacher's "<email> <display name>" row) — see
        # test_import_placeholder_full_name_kept_whole below for the case where that identifier is a
        # multi-word real name instead of a short code.
        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file('X2')),
        })
        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'X2')])

        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
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
            self.env['ems.working_schedules_import_wizard'].create({})

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

        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': [(6, 0, [attachment_1.id, attachment_2.id])],
        })

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)
        self.assertTrue(second_teacher.resource_calendar_id.attendance_ids)

    def test_import_non_teaching_hour_sent_as_subject_node_without_students(self):
        # The external planner app now sends non-teaching hours as a 'Subject' node too, whose only
        # observable difference from a real subject is the missing 'Students' sibling. The code ('G')
        # must still be recognized as non-teaching (via ems.non_teaching_type), not looked up as a
        # real ems.subject.
        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
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

        self.env['ems.working_schedules_import_wizard'].create({
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

        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TDEV Group"/>',
            )),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.bare_acronym_group)

    def test_import_bare_study_acronym_with_several_groups_raises(self):
        # If the study actually has more than one group, a bare acronym is genuinely ambiguous — the
        # importer must not guess which one the planner meant, and should raise like any other mismatch.
        self.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': self.level.id, 'study_id': self.bare_acronym_study.id,
            'space_id': self.space.id,
        })

        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    '<Students name="TDEV Group"/>',
                )),
            })

    def test_import_group_still_not_found_after_fallback_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.hour_to, self.env.company.schedule_import_last_entry_time)

    def test_onchange_attachment_ids_unknown_email_sets_blocking_error(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_unknown.xml',
            'datas': self._xml_file('unknown.import.wizard@example.com Someone'),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn('unknown.import.wizard@example.com', wizard.blocking_issues_html)
        self.assertIn('planner_unknown.xml', wizard.blocking_issues_html)
        self.assertFalse(wizard.info_html)
        self.assertFalse(wizard.ready_to_import)

    def test_onchange_attachment_ids_placeholder_code_sets_info_html_not_blocking(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_pending.xml',
            'datas': self._xml_file('X3'),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertFalse(wizard.blocking_issues_html)
        self.assertTrue(wizard.info_html)
        self.assertIn('X3', wizard.info_html)
        self.assertTrue(wizard.ready_to_import)

    def test_onchange_attachment_ids_placeholder_full_name_kept_whole_in_info_html(self):
        # Same bug as test_import_placeholder_full_name_kept_whole, checked at the onchange-preview
        # level: the blue banner must list the teacher's full name, not just its first word.
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_pending_name.xml',
            'datas': self._xml_file('Fulanito Menganito'),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.info_html)
        self.assertIn('Fulanito Menganito', wizard.info_html)
        self.assertTrue(wizard.ready_to_import)

    def test_onchange_attachment_ids_placeholder_code_unresolved_group_sets_blocking_error(self):
        # Reported 2026-08-01: a not-yet-identified (pending-code) teacher's schedule content was
        # never actually parsed at onchange-preview time (only its code was noted as "pending"), so
        # an unresolvable group acronym in that same row silently passed the preview and only blew up
        # as an uncaught ValidationError when actually clicking Import (create()) - a generic error
        # popup instead of the wizard's own red "blocking issues" banner. The onchange must now catch
        # this here too, just like it already does for a known teacher's unresolved group.
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_pending_bad_group.xml',
            'datas': self._xml_file_with_hour_node(
                'X4',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="NOPE Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn("Group with acronym 'NOPE Group' not found", wizard.blocking_issues_html)
        self.assertIn('X4', wizard.info_html)
        self.assertFalse(wizard.ready_to_import)

    def test_onchange_attachment_ids_known_email_no_blocking_error(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_known.xml',
            'datas': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertFalse(wizard.blocking_issues_html)
        self.assertTrue(wizard.ready_to_import)

    def test_ready_to_import_false_before_onchange_attachment_ids_runs(self):
        # Regression guard for the race the developer found manually: attaching a file makes
        # 'attachment_ids' truthy immediately, but the onchange that actually validates the content is
        # a separate RPC that finishes slightly later - if the Import button were gated on the ABSENCE
        # of a blocking field (the old design), it would render enabled during that whole gap, since
        # those fields simply hadn't been computed yet. Gating on this field instead (only ever set
        # True by a successful onchange) closes the gap: before the onchange runs, it must still read
        # as its Python default (False), same as a brand new record.
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_known.xml',
            'datas': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        self.assertFalse(wizard.ready_to_import)

        wizard._onchange_attachment_ids()

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
        self.env['ems.working_schedules_import_wizard'].create({
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
        self.env['ems.working_schedules_import_wizard'].create({
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

    def test_import_raises_on_space_conflict_from_teacher_not_in_this_file(self):
        # A teacher simply absent from the file being (re)imported can still hold an active schedule
        # line in a room the new import now also wants at an overlapping time, for a DIFFERENT
        # subject/group - a genuine double-booking, not co-teaching. Per the simplified batch importer
        # (2026-08-01 redesign): a fresh import never writes on top of already-populated data for its
        # own scope, so this is always a real problem to fix, never something to silently archive.
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 4 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher4.import.wizard@example.com',
        })
        # 'self.teacher' is NOT part of this second import — only 'second_teacher' is, teaching a
        # DIFFERENT subject in the SAME group/room/time.
        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher4.import.wizard@example.com Someone Else',
                    f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                    f'<Students name="{self.group.name} Group"/>',
                )),
            })

    def test_import_raises_on_space_conflict_when_new_teacher_is_pending_code(self):
        # Same shape as the test above, but the NEW side is a pending-identification teacher (no
        # e-mail, no pre-existing hr.employee) instead of an already-existing one.
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })

        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'PENDINGCONFLICT',
                    f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                    f'<Students name="{self.group.name} Group"/>',
                )),
            })

    def test_onchange_attachment_ids_space_conflict_sets_blocking_error(self):
        # Same scenario as the create()-level test above, checked at the onchange-preview level, so
        # the admin sees the room conflict named in the wizard before ever clicking Import.
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 5 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher5.import.wizard@example.com',
        })

        attachment = self.env['ir.attachment'].create({
            'name': 'planner_space_conflict.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher5.import.wizard@example.com Someone Else',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })
        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn(self.teacher.display_name, wizard.blocking_issues_html)
        self.assertFalse(wizard.ready_to_import)
        del second_teacher  # only needed to own the conflicting session created above

    def test_onchange_attachment_ids_co_teaching_sets_non_blocking_banner(self):
        # Same subject+group as an existing external teacher's schedule — legitimate co-teaching, must
        # NOT block the import, just surface a confirmation banner.
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 6 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher6.import.wizard@example.com',
        })

        attachment = self.env['ir.attachment'].create({
            'name': 'planner_co_teaching.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher6.import.wizard@example.com Someone Else',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })
        wizard._onchange_attachment_ids()

        self.assertFalse(wizard.blocking_issues_html)
        self.assertTrue(wizard.co_teaching_html)
        self.assertIn(self.teacher.display_name, wizard.co_teaching_html)
        self.assertTrue(wizard.ready_to_import)
        del second_teacher  # only needed to own the pre-existing session created above

    def test_import_co_teaching_merges_into_one_shared_template(self):
        # Real-world case (two teachers importing the exact same subject+group+time+room): must end
        # up sharing a SINGLE ems.attendance_template (and therefore a single, jointly-visible
        # attendance session) rather than one template each.
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 7 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher7.import.wizard@example.com',
        })
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                'test.wizard.teacher7.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            )),
        })
        self.env['ems.working_schedules_import_wizard'].create({
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

    def test_onchange_attachment_ids_overrided_teachers_html_lists_teacher(self):
        self.env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': self._attachment_ids(
                self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            ),
        })

        attachment = self.env['ir.attachment'].create({
            'name': 'planner_reimport.xml',
            'datas': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })
        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.overrided_teachers_html)
        self.assertIn('<li>', wizard.overrided_teachers_html)
        self.assertIn(self.teacher.display_name, wizard.overrided_teachers_html)

    def test_import_group_without_space_raises_clear_error(self):
        # ems.group.space_id is optional, but ems.attendance_template.space_id (taken from the
        # group) is required — without this check, Odoo's generic "mandatory field is not set" error
        # would surface instead of naming which group is missing a classroom.
        with self.assertRaises(ValidationError) as capture:
            self.env['ems.working_schedules_import_wizard'].create({
                'attachment_ids': self._attachment_ids(self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    f'<Students name="{self.spaceless_group.name} Group"/>',
                )),
            })

        self.assertIn(self.spaceless_group.name, str(capture.exception))

    def test_onchange_attachment_ids_sets_blocking_error_for_group_without_space(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_no_space.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn(self.spaceless_group.name, wizard.blocking_issues_html)
        self.assertFalse(wizard.ready_to_import)

    def test_onchange_attachment_ids_unknown_group_does_not_raise(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_unknown_group.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TWIWNOTAREALGROUP Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn('TWIWNOTAREALGROUP', wizard.blocking_issues_html)
        self.assertFalse(wizard.ready_to_import)

    def test_onchange_attachment_ids_unknown_subject_code_does_not_raise(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'planner_unknown_subject.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<Subject name="ZZZZ Unknown subject"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn('ZZZZ', wizard.blocking_issues_html)
        self.assertFalse(wizard.ready_to_import)

    def test_onchange_attachment_ids_combines_multiple_blocking_issues_into_one_list(self):
        # Several distinct problems across different files must render as separate bullet points
        # in the same banner, not get silently dropped/overwritten by whichever ran last.
        attachment_unknown = self.env['ir.attachment'].create({
            'name': 'planner_unknown.xml',
            'datas': self._xml_file('unknown.import.wizard@example.com Someone'),
        })
        attachment_no_space = self.env['ir.attachment'].create({
            'name': 'planner_no_space.xml',
            'datas': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            ),
        })
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'attachment_ids': [(6, 0, [attachment_unknown.id, attachment_no_space.id])],
        })

        wizard._onchange_attachment_ids()

        self.assertIn('unknown.import.wizard@example.com', wizard.blocking_issues_html)
        self.assertIn(self.spaceless_group.name, wizard.blocking_issues_html)
        self.assertEqual(wizard.blocking_issues_html.count('<li>'), 2)
