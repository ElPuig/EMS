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
        # 'file' (not 'attachment_id') is what create() reads — it's a non-stored related field
        # ('attachment_id.datas'), only populated by the UI's own onchange, not by ORM create() vals.
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

    def test_import_with_teacher_id_skips_email_lookup(self):
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file('nonexistent@example.com Nobody'),
            'teacher_id': self.teacher.id,
        })

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)

    def test_import_without_teacher_id_matches_by_email(self):
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })

        self.assertTrue(self.teacher.resource_calendar_id.attendance_ids)

    def test_import_without_teacher_id_unknown_email_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'file': self._xml_file('unknown.import.wizard@example.com Someone'),
            })

    def test_import_placeholder_code_creates_pending_teacher(self):
        # A code with no '@' (e.g. "X1") isn't a real e-mail typo: the external planner uses it for a
        # not-yet-staffed post, so a pending-identification teacher is created instead of raising. The
        # raw XML 'name' attribute for this kind of row is just the code itself, with no discardable
        # label after it (unlike a real teacher's "<email> <display name>" row) — see
        # test_import_placeholder_full_name_kept_whole below for the case where that identifier is a
        # multi-word real name instead of a short code.
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'X1',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
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
            'file': self._xml_file('X2'),
        })
        teacher = self.env['hr.employee'].search([('schedule_import_code', '=', 'X2')])

        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file('X2'),
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
            'file': self._xml_file('Fulanito Menganito'),
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
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<Subject name="G Guard"/>',
            ),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertEqual(attendance.non_teaching, self.env.ref('ems.non_teaching_g'))
        self.assertFalse(attendance.subject_id)

    def test_import_real_subject_sent_as_subject_node_with_students(self):
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
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
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>'
                f'<Students name="{self.single_group.name} Group"/>',
            ),
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
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.reinforcement_group.name}"/>',
            ),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertEqual(attendance.group_ids, self.reinforcement_group)

    def test_import_single_group_without_trailing_a_falls_back(self):
        # The external planner names a level's only group "TWIW2" (no trailing letter), while EMS
        # always stores it as "TWIW2A" even when it's the only group of that level/course.
        self.assertEqual(self.single_group.name, 'TWIW2A')

        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TWIW2 Group"/>',
            ),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.group_ids, self.single_group)

    def test_import_bare_study_acronym_resolves_single_course_single_group(self):
        # The external planner names a study with only one course and one group by its bare acronym
        # ("TDEV"), with neither the course number nor the trailing letter EMS always stores ("TDEV1A").
        self.assertEqual(self.bare_acronym_group.name, 'TDEV1A')

        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TDEV Group"/>',
            ),
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
                'file': self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    '<Students name="TDEV Group"/>',
                ),
            })

    def test_import_group_still_not_found_after_fallback_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'file': self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    '<Students name="NOPE Group"/>',
                ),
            })

    def test_import_last_period_of_day_inherits_previous_period_duration(self):
        # Real-world bug: the last period of the day was always clamped to the fixed company
        # setting (schedule_import_last_entry_time, 21:00), instead of keeping the same 1h duration
        # as the rest of the day. 19:20-20:20 (1h) is followed by a period starting at 20:20, which
        # should now end at 21:20, not the company's fixed 21:00.
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hours(
                'test.wizard.teacher.import.wizard@example.com Someone',
                ['19:20', '20:20'],
            ),
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
            'file': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertEqual(attendance.hour_to, self.env.company.schedule_import_last_entry_time)

    def test_import_scoped_multiple_teachers_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.working_schedules_import_wizard'].create({
                'file': self._xml_file_multiple_teachers(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    'test.wizard.teacher2.import.wizard@example.com Someone Else',
                ),
                'teacher_id': self.teacher.id,
            })

    def test_onchange_file_scoped_multiple_teachers_sets_blocking_error(self):
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file_multiple_teachers(
                'test.wizard.teacher.import.wizard@example.com Someone',
                'test.wizard.teacher2.import.wizard@example.com Someone Else',
            ),
        })

        wizard._onchange_file()

        self.assertTrue(wizard.blocking_error_message)
        self.assertFalse(wizard.email_mismatch_warning)
        self.assertFalse(wizard.ready_to_import)

    def test_onchange_file_scoped_email_mismatch_sets_warning_not_blocking(self):
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file('nonexistent@example.com Nobody'),
        })

        wizard._onchange_file()

        self.assertTrue(wizard.email_mismatch_warning)
        self.assertFalse(wizard.blocking_error_message)
        self.assertTrue(wizard.ready_to_import)

    def test_onchange_file_scoped_matching_email_no_warning(self):
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })

        wizard._onchange_file()

        self.assertFalse(wizard.email_mismatch_warning)
        self.assertFalse(wizard.blocking_error_message)
        self.assertTrue(wizard.ready_to_import)

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

    def test_ready_to_import_false_before_onchange_file_runs(self):
        # Regression guard for the race the developer found manually: attaching a file makes
        # 'attachment_ids'/'file' truthy immediately, but the onchange that actually validates the
        # content is a separate RPC that finishes slightly later - if the Import button were gated
        # on the ABSENCE of a blocking field (the old design), it would render enabled during that
        # whole gap, since those fields simply hadn't been computed yet. Gating on this field
        # instead (only ever set True by a successful onchange) closes the gap: before the onchange
        # runs, it must still read as its Python default (False), same as a brand new record.
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })

        self.assertFalse(wizard.ready_to_import)

        wizard._onchange_file()

        self.assertTrue(wizard.ready_to_import)

    def test_ready_to_import_false_before_onchange_attachment_ids_runs(self):
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

    def test_import_archives_external_conflict_from_teacher_not_in_this_file(self):
        # Real-world bug: a teacher simply absent from the file being (re)imported can still hold a
        # stale schedule line in a room the new import now also wants at an overlapping time. The
        # import must not raise — that stale, colliding line gets archived (not the whole template).
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
            'teacher_id': self.teacher.id,
        })
        old_line = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ]).attendance_schedule_ids

        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 4 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher4.import.wizard@example.com',
        })
        # 'self.teacher' is NOT part of this second import — only 'second_teacher' is.
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher4.import.wizard@example.com Someone Else',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
            'teacher_id': second_teacher.id,
        })

        self.assertFalse(old_line.active)
        new_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', second_teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertTrue(new_template.attendance_schedule_ids)

    def test_onchange_file_scoped_sets_external_conflicts_html(self):
        # Different subject (not co-teaching — same subject+group by different teachers is a legitimate
        # setup, see ems.attendance_schedule.is_co_teaching_with): a genuine, unrelated room conflict.
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 5 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher5.import.wizard@example.com',
        })
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher5.import.wizard@example.com Someone',
                f'<Subject name="{self.other_subject.code} {self.other_subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
            'teacher_id': second_teacher.id,
        })

        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })
        wizard._onchange_file()

        self.assertTrue(wizard.external_conflicts_html)
        self.assertIn('Test Wizard Teacher 5', wizard.external_conflicts_html)

    def test_onchange_file_scoped_co_teaching_not_flagged_as_conflict(self):
        # Same subject+group as an existing external teacher's schedule — a legitimate co-teaching
        # setup, must NOT be flagged as something that would get archived.
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 6 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher6.import.wizard@example.com',
        })
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher6.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
            'teacher_id': second_teacher.id,
        })

        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })
        wizard._onchange_file()

        self.assertFalse(wizard.external_conflicts_html)

    def test_import_co_teaching_merges_into_one_shared_template(self):
        # Real-world case (Gabriel Manrubia / David Tomás): two teachers importing the exact same
        # subject+group+time+room must end up sharing a SINGLE ems.attendance_template (and therefore a
        # single, jointly-visible attendance session) rather than one template each.
        second_teacher = self.env['hr.employee'].create({
            'name': 'Test Wizard Teacher 7 (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher7.import.wizard@example.com',
        })
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher7.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
            'teacher_id': second_teacher.id,
        })
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
            'teacher_id': self.teacher.id,
        })

        templates = self.env['ems.attendance_template'].search([
            ('subject_id', '=', self.subject.id),
            ('group_ids', 'in', self.group.id),
        ])
        self.assertEqual(len(templates), 1)
        self.assertEqual(set(templates.teacher_ids.ids), {self.teacher.id, second_teacher.id})

    def test_onchange_file_overrided_teachers_html_lists_teacher(self):
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
            'teacher_id': self.teacher.id,
        })

        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file('test.wizard.teacher.import.wizard@example.com Someone'),
        })
        wizard._onchange_file()

        self.assertTrue(wizard.overrided_teachers_html)
        self.assertIn('<li>', wizard.overrided_teachers_html)
        self.assertIn(self.teacher.display_name, wizard.overrided_teachers_html)

    def test_import_group_without_space_raises_clear_error(self):
        # ems.group.space_id is optional, but ems.attendance_template.space_id (taken from the
        # group) is required — without this check, Odoo's generic "mandatory field is not set" error
        # would surface instead of naming which group is missing a classroom.
        with self.assertRaises(ValidationError) as capture:
            self.env['ems.working_schedules_import_wizard'].create({
                'file': self._xml_file_with_hour_node(
                    'test.wizard.teacher.import.wizard@example.com Someone',
                    f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                    f'<Students name="{self.spaceless_group.name} Group"/>',
                ),
                'teacher_id': self.teacher.id,
            })

        self.assertIn(self.spaceless_group.name, str(capture.exception))

    def test_onchange_file_scoped_sets_blocking_error_for_group_without_space(self):
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                f'<Students name="{self.spaceless_group.name} Group"/>',
            ),
        })

        wizard._onchange_file()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn(self.spaceless_group.name, wizard.blocking_issues_html)
        self.assertFalse(wizard.ready_to_import)

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

    def test_onchange_file_scoped_unknown_group_does_not_raise(self):
        # Real-world bug: an unresolvable group name raised ValidationError from deep inside
        # _parse_schedule_entries, escaping the onchange uncaught - Odoo showed it as a generic
        # error modal instead of the graceful red blocking_issues_html banner every other
        # validation problem here uses (unknown e-mail, missing space...).
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                f'<Subject name="{self.subject.code} {self.subject.name}"/>'
                '<Students name="TWIWNOTAREALGROUP Group"/>',
            ),
        })

        wizard._onchange_file()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn('TWIWNOTAREALGROUP', wizard.blocking_issues_html)
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

    def test_onchange_file_scoped_unknown_subject_code_does_not_raise(self):
        # Same bug class as the unknown-group case above, one raise site earlier in
        # _parse_schedule_entries (subject code lookup instead of group lookup).
        wizard = self.env['ems.working_schedules_import_wizard'].new({
            'teacher_id': self.teacher.id,
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<Subject name="ZZZZ Unknown subject"/>'
                f'<Students name="{self.group.name} Group"/>',
            ),
        })

        wizard._onchange_file()

        self.assertTrue(wizard.blocking_issues_html)
        self.assertIn('ZZZZ', wizard.blocking_issues_html)
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
        self.assertFalse(wizard.ready_to_import)
