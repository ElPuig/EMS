import base64

from dateutil.relativedelta import relativedelta

from odoo.addons.ems.models.curriculum.level import CARD_PALETTE
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user,
    draw_invented_centre_stamp, draw_invented_student_photo, next_student_id,
)


class TestStudentCard(TransactionCase):
    """The student card PDF (issue #524): who may print it, which students end up on the sheet and
    what each card shows, including whether the student may leave the centre (of age, or the
    family accepted the 'Leave the Centre' authorization)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_card_tutor', name='TSC Tutor')
        tutor = create_role_employee(cls, cls.tutor_user)
        other_tutor = create_role_employee(cls, create_role_user(
            cls, 'tutor', 'test_card_other_tutor', name='TSC Other Tutor'))
        create_head_of_studies_branch(cls, 'TSC', tutor)
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TSC', study={'acronym': 'TSCX'}, group={'tutor_id': tutor.id, 'course': 3})
        __, __, cls.other_group = create_level_study_group(cls, 'TSCO', group={'tutor_id': other_tutor.id})
        cls.own_b, cls.own_a, cls.foreign = cls.env['res.partner'].create([{
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': grp.id,
        } for name, grp in (
            ('TSC Bravo Student', cls.group), ('TSC Alpha Student', cls.group), ('TSC Foreign Student', cls.other_group),
        )])
        cls.applicant = cls.env['res.partner'].create({
            'name': 'TSC Applicant', 'contact_type': 'applicant', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })
        cls.secretary = create_role_user(cls, 'secretary', 'test_card_secretary')

    def _render(self, students):
        html, __ = self.env['ir.actions.report']._render_qweb_html('ems.report_student_card', students.ids)
        return html.decode()

    # --- Level colour ---------------------------------------------------------------------------

    def test_official_level_gets_its_palette_colour(self):
        self.assertEqual(self.env.ref('ems.level_eso').card_color, 'blue')

    def test_other_level_gets_grey_and_keeps_an_edited_colour(self):
        self.assertEqual(self.level.card_color, 'grey')
        self.level.card_color = 'cyan'
        self.level.name = 'TSC Renamed Level'
        self.assertEqual(self.level.card_color, 'cyan')

    # --- Who may print --------------------------------------------------------------------------

    def test_tutor_only_on_own_students(self):
        self.assertTrue(self.own_a.with_user(self.tutor_user).can_print_student_card)
        self.assertFalse(self.foreign.with_user(self.tutor_user).can_print_student_card)
        self.assertTrue(self.group.with_user(self.tutor_user).can_print_student_cards)
        self.assertFalse(self.other_group.with_user(self.tutor_user).can_print_student_cards)

    def test_secretary_on_every_student(self):
        self.assertTrue(self.foreign.with_user(self.secretary).can_print_student_card)
        self.assertTrue(self.other_group.with_user(self.secretary).can_print_student_cards)

    def test_plain_teacher_on_no_student(self):
        teacher = create_role_user(self, 'teacher', 'test_card_teacher')
        self.assertFalse(self.own_a.with_user(teacher).can_print_student_card)
        self.assertFalse(self.group.with_user(teacher).can_print_student_cards)

    def test_only_enrolled_students_get_a_card(self):
        self.assertFalse(self.applicant.with_user(self.secretary).can_print_student_card)

    # --- What gets printed ----------------------------------------------------------------------

    def test_selection_keeps_own_students_sorted_by_name(self):
        students = (self.own_b | self.foreign | self.own_a | self.applicant).with_user(self.tutor_user)
        action = students.action_print_student_card()
        self.assertEqual(action['report_name'], 'ems.report_student_card')
        self.assertEqual(action['context']['active_ids'], [self.own_a.id, self.own_b.id])

    def test_nothing_printable_raises(self):
        with self.assertRaises(UserError):
            self.foreign.with_user(self.tutor_user).action_print_student_card()

    def test_group_prints_its_main_students(self):
        action = self.group.with_user(self.tutor_user).action_print_student_cards()
        self.assertEqual(action['context']['active_ids'], [self.own_a.id, self.own_b.id])
        with self.assertRaises(UserError):
            self.other_group.with_user(self.tutor_user).action_print_student_cards()

    # --- What a card shows ----------------------------------------------------------------------

    def test_card_content(self):
        self.own_a.write({'document_id': '12345678Z', 'birth_date': '2010-05-04'})
        self.foreign.write({'passport_id': 'XY1234567'})
        html = self._render(self.own_a | self.foreign)
        for expected in ('TSC Alpha Student', '12345678Z', 'XY1234567', self.own_a.student_id,
                         'TSC', 'TSCO', CARD_PALETTE[self.level.card_color],
                         self.env.company.current_course_id.name or '', 'class="o_ems_card_barcode"'):
            self.assertIn(expected, html)

    def test_study_acronym_and_framed_course(self):
        # The study's acronym, never its full name, and only when it adds something to the level's.
        html = self._render(self.own_a)
        self.assertIn('<div class="o_ems_card_study">TSCX</div>', html)
        self.assertNotIn('Test TSC Study', html)
        self.assertIn('<div class="o_ems_card_course_number">3</div>', html)
        self.assertNotIn('class="o_ems_card_study"', self._render(self.foreign))

    def test_stamp_box_or_uploaded_stamp(self):
        self.env.company.ems_card_stamp = False
        self.assertIn('class="o_ems_card_stamp_empty"', self._render(self.own_a))
        self.env.company.ems_card_stamp = base64.b64encode(draw_invented_centre_stamp())
        html = self._render(self.own_a)
        self.assertNotIn('class="o_ems_card_stamp_empty"', html)
        self.assertIn('class="o_ems_card_stamp_image"', html)

    def test_photo_or_silhouette(self):
        self.assertIn('class="o_ems_card_no_photo"', self._render(self.own_a))
        self.own_a.image_1920 = base64.b64encode(draw_invented_student_photo())
        html = self._render(self.own_a)
        self.assertNotIn('class="o_ems_card_no_photo"', html)
        # Inside a fixed frame, scaled to fit it: wkhtmltopdf ignores object-fit and would stretch it.
        self.assertIn('<div class="o_ems_card_photo_frame">', html)

    def test_every_card_has_its_back(self):
        # Fronts and backs alternate sheet by sheet; an odd last row puts its back on the right.
        html = self._render(self.own_a | self.own_b | self.foreign)
        self.assertEqual(html.count('class="o_ems_card"'), 3)
        self.assertEqual(html.count('class="o_ems_card o_ems_card_back"'), 3)
        self.assertEqual(html.count('class="o_ems_card_blank"'), 1)
        self.assertIn('departament_educacio.png', html)

    def test_printed_in_the_centre_language(self):
        # Whoever prints it, in whatever language they work: the card speaks Catalan.
        self.env['res.lang']._activate_lang('ca_ES')
        html = self.env['ir.actions.report'].with_context(lang='es_ES')._render_qweb_html(
            'ems.report_student_card', self.own_a.ids)[0].decode()
        self.assertIn('lang="ca-ES"', html)
        self.assertIn('Aquest carnet és personal i intransferible', html)

    def test_student_without_main_group(self):
        # No level to show: the card still prints, with a grey band.
        self.own_a.main_group_id = False
        html = self._render(self.own_a)
        self.assertIn('TSC Alpha Student', html)
        self.assertIn(f"background: {CARD_PALETTE['grey']}", html)

    # --- May the student leave the centre -------------------------------------------------------

    def _with_leave_authorization(self, student, status):
        """The student's enrollment for the course in force, with a 'Leave the Centre' answer."""
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.env.company.current_course_id.id, 'shift': 'morning'})
        order.state = 'sale'
        template = self.env['ems.authorization.template'].create({
            'name': 'TSC Leave', 'auth_type': 'leave', 'legal_text': '<p>Text</p>'})
        self.env['ems.authorization'].create({
            'enrollment_id': order.id, 'template_id': template.id, 'status': status})

    def _birth_date(self, years):
        return self.env['ems.datetime_utils'].get_local_today() - relativedelta(years=years)

    def test_minor_without_authorization_may_not_leave(self):
        self.own_a.birth_date = self._birth_date(15)
        self.assertFalse(self.own_a.can_leave_centre)
        self.assertIn('o_ems_card_exit o_ems_card_exit_no"', self._render(self.own_a))

    def test_adult_may_leave_without_authorization(self):
        self.own_a.birth_date = self._birth_date(18)
        self.assertTrue(self.own_a.can_leave_centre)
        self.assertIn('o_ems_card_exit o_ems_card_exit_yes"', self._render(self.own_a))

    def test_minor_may_leave_only_with_the_authorization_accepted(self):
        self.own_a.birth_date = self._birth_date(15)
        self.own_b.birth_date = self._birth_date(15)
        self._with_leave_authorization(self.own_a, 'yes')
        self._with_leave_authorization(self.own_b, 'no')
        self.assertTrue(self.own_a.auth_leave)
        self.assertTrue(self.own_a.can_leave_centre)
        self.assertFalse(self.own_b.auth_leave)
        self.assertFalse(self.own_b.can_leave_centre)
