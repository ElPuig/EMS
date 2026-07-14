import base64

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


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
        cls.level = cls.env['ems.level'].create({'acronym': 'TWIW', 'name': 'Test Level (Import Wizard)'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TWIW001',
            'acronym': 'TWIW',
            'name': 'Test Study (Import Wizard)',
            'date': fields.Date.today(),
            'deprecated': False,
            'level_id': cls.level.id,
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

    def _xml_file(self, teacher_name_attr):
        # Minimal file the parser accepts: one teacher node -> one day -> one hour -> a NonTeaching
        # entry ('G'/Guard already exists in non_teaching_selection, so no subject/group lookup needed).
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
        # must still be recognized as non-teaching (via non_teaching_selection), not looked up as a
        # real ems.subject.
        self.env['ems.working_schedules_import_wizard'].create({
            'file': self._xml_file_with_hour_node(
                'test.wizard.teacher.import.wizard@example.com Someone',
                '<Subject name="G Guard"/>',
            ),
        })

        attendance = self.teacher.resource_calendar_id.attendance_ids
        self.assertTrue(attendance)
        self.assertEqual(attendance.non_teaching, 'G')
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
