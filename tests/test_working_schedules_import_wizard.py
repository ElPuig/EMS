import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWorkingSchedulesImportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Wizard Teacher (Import Wizard)',
            'employee_type': 'teacher',
            'work_email': 'test.wizard.teacher.import.wizard@example.com',
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
