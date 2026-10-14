import base64
import io

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import (
    create_level_study_group,
    create_role_user,
    mock_outgoing_email,
    next_student_id,
)

# The header of Esfera's list of title requests, as secretariat exports it.
ESFERA_HEADER = ("Accions;Codi del centre;Nom del centre;Tipus de sol·licitud;Identificador de l'alumne/a;"
                 "Document;Nom;Primer cognom;Segon cognom;Ensenyament;Títol;Data;Curs;"
                 "Estat de la sol·licitud;Descarrega")


class TestTitleRegistration(TransactionCase):
    """Issue #635: a title registered in the academic history carries over to the student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Leaving the centre revokes the portal and schedules the Google suspension notice.
        mock_outgoing_email(cls)
        Course = cls.env['ems.course']
        cls.title_course = Course.create({'start': 2090, 'end': 2091})
        cls.current_course = Course.create({'start': 2091, 'end': 2092})
        cls.env.company.current_course_id = cls.current_course
        cls.next_course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2092, 'end': 2093, 'is_enrollment_default': True})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TTL', level={'name': 'Title Level'}, study={
            'code': 'TTL001', 'acronym': 'TTLS', 'name': 'Title Study',
        })
        cls.secretary = create_role_user(cls, 'secretary', 'test_title_secretary')

    def _student(self, name, with_group=False, **vals):
        """A student of the title course, with its academic record of that course."""
        student = self.env['res.partner'].create(dict({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group.id if with_group else False,
        }, **vals))
        record = self.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': self.title_course.id,
            'study_id': self.study.id, 'group_name': 'TTL4A',
        })
        return student, record

    def _wizard(self, content, file_name='titols.csv', user=None):
        wizard = self.env['ems.title_import_wizard'].with_user(user or self.env.user).create({
            'file': base64.b64encode(content), 'file_name': file_name,
            'course_id': self.title_course.id,
        })
        wizard.action_preview()
        return wizard

    def _outcomes(self, wizard):
        return {line.student_identifier: line.outcome for line in wizard.line_ids}

    def _esfera_csv(self, rows):
        """rows: (identifier, course, status)."""
        lines = [ESFERA_HEADER] + [
            f";8028047;Centre;Primera expedició de títol;{identifier};DNI - 00000000T;Nom;Cognom;Cognom;"
            f"ESO LOE;Títol de graduat;18/6/2091;{course};{status};"
            for identifier, course, status in rows]
        return "\r\n".join(lines).encode('cp1252')

    # --- effects of the title on the student ---------------------------------

    def test_title_on_student_without_group_leaves_as_graduate(self):
        student, record = self._student('Title No Group')
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id})
        order.action_quotation_sent()
        record.write({'title_obtained': True})
        self.assertTrue(student.has_graduated)
        self.assertEqual(student.contact_type, 'alumni')
        self.assertFalse(student.active)
        self.assertEqual(student.exit_type, 'graduation')
        self.assertEqual(student.exit_course_id, self.title_course)
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(record.exit_type, 'graduation')
        self.assertEqual(record.academic_result, 'full')

    def test_title_on_student_in_group_only_marks(self):
        student, record = self._student('Title In Group', with_group=True)
        record.write({'title_obtained': True})
        self.assertTrue(student.has_graduated)
        self.assertEqual(student.contact_type, 'student')
        self.assertTrue(student.active)
        self.assertEqual(student.main_group_id, self.group)
        self.assertFalse(student.exit_type)

    def test_title_on_withdrawal_becomes_alumni(self):
        student, record = self._student('Title Withdrawal')
        student.write({'contact_type': 'withdrawal', 'exit_type': 'withdrawal',
                       'exit_course_id': self.current_course.id, 'active': False})
        record.write({'title_obtained': True})
        self.assertEqual(student.contact_type, 'alumni')
        # The withdrawal it left with is kept.
        self.assertEqual(student.exit_type, 'withdrawal')
        self.assertEqual(student.exit_course_id, self.current_course)

    def test_untick_title_keeps_graduated(self):
        student, record = self._student('Title Untick', with_group=True)
        record.write({'title_obtained': True})
        record.write({'title_obtained': False})
        self.assertTrue(student.has_graduated)

    def test_generator_title_has_no_effects(self):
        # The transition writes the title of a graduate it is already processing itself.
        student, record = self._student('Title Generated')
        record.with_context(ems_skip_title_effects=True).write({'title_obtained': True})
        self.assertEqual(student.contact_type, 'student')
        self.assertFalse(student.has_graduated)

    # --- import --------------------------------------------------------------

    def test_import_esfera_csv(self):
        graduate, graduate_record = self._student('Import Graduate')
        studying, studying_record = self._student('Import Studying', with_group=True)
        reissued, _record = self._student('Import Reissued')
        cancelled, _record = self._student('Import Cancelled')
        titled, titled_record = self._student('Import Titled', with_group=True)
        titled_record.write({'title_obtained': True})
        no_record = self.env['res.partner'].create({
            'name': 'Import No Record', 'contact_type': 'student', 'student_id': next_student_id()})
        other_course, _record = self._student('Import Other Course')
        course = self.title_course.name
        wizard = self._wizard(self._esfera_csv([
            (graduate.student_id, course, 'Registrada'),
            (studying.student_id, course, 'Alta'),
            (reissued.student_id, course, "Sol·licitud anul·lada"),
            (reissued.student_id, course, 'Registrada MECD'),
            (cancelled.student_id, course, "Sol·licitud anul·lada"),
            (titled.student_id, course, 'Registrada'),
            (no_record.student_id, course, 'Registrada'),
            ('TESTMISSING', course, 'Registrada'),
            (other_course.student_id, self.current_course.name, 'Registrada'),
        ]), user=self.secretary)
        self.assertEqual(self._outcomes(wizard), {
            graduate.student_id: 'graduate',
            studying.student_id: 'title',
            reissued.student_id: 'graduate',
            cancelled.student_id: 'cancelled',
            titled.student_id: 'already',
            no_record.student_id: 'no_record',
            'TESTMISSING': 'not_found',
            other_course.student_id: 'other_course',
        })
        self.assertEqual(wizard.apply_count, 3)
        wizard.action_apply()
        self.assertTrue(graduate_record.title_obtained)
        self.assertEqual(graduate.contact_type, 'alumni')
        self.assertFalse(graduate.active)
        self.assertTrue(studying_record.title_obtained)
        self.assertEqual(studying.contact_type, 'student')
        self.assertEqual(reissued.contact_type, 'alumni')
        self.assertFalse(cancelled.has_graduated)
        self.assertEqual(other_course.contact_type, 'student')

    def test_import_identifier_column_only(self):
        student, record = self._student('Import Minimal')
        wizard = self._wizard(f"IDALU\n{student.student_id}\n".encode())
        self.assertEqual(self._outcomes(wizard), {student.student_id: 'graduate'})
        wizard.action_apply()
        self.assertTrue(record.title_obtained)

    def test_import_xlsx_with_numeric_identifier(self):
        import openpyxl
        _student, record = self._student('Import Xlsx', student_id='99999999999635')
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['Nom', "Identificador de l'alumne/a", 'Curs'])
        sheet.append(['Import Xlsx', 99999999999635, self.title_course.name])
        buffer = io.BytesIO()
        workbook.save(buffer)
        wizard = self._wizard(buffer.getvalue(), file_name='titols.xlsx')
        self.assertEqual(self._outcomes(wizard), {'99999999999635': 'graduate'})
        self.assertEqual(wizard.line_ids.record_id, record)

    def test_import_without_identifier_column(self):
        with self.assertRaises(UserError):
            self._wizard(b"Nom;Curs\nSomeone;2090-2091\n")

    # --- from the student form -----------------------------------------------

    def test_register_title_from_student_form(self):
        student, record = self._student('Form Graduate')
        action = student.with_user(self.secretary).action_title_register_wizard()
        wizard = self.env['ems.title_register_wizard'].with_user(self.secretary).with_context(
            action['context']).create({})
        self.assertEqual(wizard.course_id, self.title_course)
        self.assertEqual(wizard.record_id, record)
        self.assertEqual(wizard.effect, 'graduate')
        wizard.action_apply()
        self.assertTrue(record.title_obtained)
        self.assertEqual(student.contact_type, 'alumni')
        self.assertFalse(student.active)

    def test_register_title_without_pending_course(self):
        student, record = self._student('Form Titled', with_group=True)
        record.write({'title_obtained': True})
        with self.assertRaises(UserError):
            self.env['ems.title_register_wizard'].with_context(
                default_student_id=student.id).create({})
