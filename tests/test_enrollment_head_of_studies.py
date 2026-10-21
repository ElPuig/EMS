from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, create_role_user, next_student_id


def create_enrollment_outside_any_chain(cls, prefix):
    """A draft enrollment of a student whose group has no tutor, so no Head of Studies' chain of
    command reaches it, and a pre-enrolled applicant. Sets cls.student, cls.order, cls.applicant."""
    __, __, group = create_level_study_group(cls, prefix)
    Partner = cls.env['res.partner']
    cls.student = Partner.create({
        'name': f'0000 {prefix} Enrollment Student', 'contact_type': 'student',
        'student_id': next_student_id(), 'main_group_id': group.id,
    })
    course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1) \
        or cls.env['ems.course'].search([], limit=1)
    cls.order = cls.env['sale.order'].create({
        'partner_id': cls.student.id, 'ems_study_id': group.study_id.id, 'ems_course_id': course.id,
    })
    cls.applicant = Partner.create({
        'name': f'0000 {prefix} Applicant', 'contact_type': 'applicant', 'student_id': next_student_id(),
        'study_id': group.study_id.id, 'preinscription_shift': 'morning',
    })


class TestEnrollmentHeadOfStudiesAccess(TransactionCase):
    """Issue #654: Head of Studies/Deputy Head of Studies and the Director read the whole of
    Academic management > Enrollment and its Configuration section, centre-wide and read only."""

    MENUS = ('ems.menu_ems_enrollments', 'ems.menu_ems_applicants', 'ems.menu_students_no_destination',
             'ems.menu_ems_configuration_enrollment', 'ems.menu_ems_enrollment_items',
             'ems.menu_ems_enrollment_templates', 'ems.menu_ems_task_assignment')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_enrollment_outside_any_chain(cls, 'HSE')
        cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_hos_enrollment_access')

    def test_head_of_studies_reads_any_enrollment(self):
        Order = self.env['sale.order'].with_user(self.head_of_studies)
        self.assertEqual(Order.search([('id', '=', self.order.id)]), self.order)
        self.assertEqual(self.order.with_user(self.head_of_studies).partner_id, self.student)
        self.assertEqual(
            self.env['sale.order.line'].with_user(self.head_of_studies).search([('order_id', '=', self.order.id)]),
            self.order.order_line)

    def test_head_of_studies_cannot_change_an_enrollment_outside_their_chain(self):
        with self.assertRaises(AccessError):
            self.order.with_user(self.head_of_studies).write({'note': 'changed'})
        with self.assertRaises(AccessError):
            self.order.with_user(self.head_of_studies).unlink()

    def test_head_of_studies_reads_applicants(self):
        Partner = self.env['res.partner'].with_user(self.head_of_studies)
        self.assertEqual(Partner.search([('id', '=', self.applicant.id)]), self.applicant)

    def test_head_of_studies_cannot_change_the_enrollment_set_up(self):
        template = self.env['sale.order.template'].search([], limit=1) \
            or self.env['sale.order.template'].create({'name': 'HSE Template'})
        item = self.env['product.template'].search([('sale_ok', '=', True), ('type', '=', 'service')], limit=1)
        task_type = self.env['mail.activity.type'].search([('ems_task_assignment', '=', True)], limit=1)
        for record in (template, item, task_type):
            with self.subTest(model=record._name), self.assertRaises(AccessError):
                record.with_user(self.head_of_studies).write({'name': 'changed'})

    def test_menus_for_head_of_studies_not_department_chief(self):
        Menu = self.env['ir.ui.menu']
        hos_visible = Menu.with_user(self.head_of_studies)._visible_menu_ids()
        chief_visible = Menu.with_user(
            create_role_user(self, 'department_chief', 'test_chief_enrollment_access'))._visible_menu_ids()
        for xmlid in self.MENUS:
            with self.subTest(menu=xmlid):
                self.assertIn(self.env.ref(xmlid).id, hos_visible)
                self.assertNotIn(self.env.ref(xmlid).id, chief_visible)

    def test_preinscription_list_offers_create_and_delete_only_to_the_secretary(self):
        view = self.env.ref('ems.view_applicant_list')
        secretary = create_role_user(self, 'secretary', 'test_secretary_preinscription_list')

        def list_root(user):
            arch = self.env['res.partner'].with_user(user).get_views([(view.id, 'list')])['views']['list']['arch']
            return etree.fromstring(arch)

        hos_list = list_root(self.head_of_studies)
        self.assertEqual((hos_list.get('create'), hos_list.get('delete')), ('0', '0'))
        secretary_list = list_root(secretary)
        self.assertNotIn(secretary_list.get('create'), ('0', 'false', 'False'))
        self.assertNotIn(secretary_list.get('delete'), ('0', 'false', 'False'))


class TestConvalidationReasonsHeadOfStudies(TransactionCase):
    """Issue #654: Head of Studies/Deputy Head of Studies and the Director maintain the
    convalidation reasons they pick from, and archive rather than delete them."""

    def test_head_of_studies_creates_edits_and_archives_reasons(self):
        head_of_studies = create_role_user(self, 'head_of_studies', 'test_hos_convalidation_reasons')
        for model in ('ems.convalidation.info_reason', 'ems.convalidation.rejection_reason'):
            with self.subTest(model=model):
                reason = self.env[model].with_user(head_of_studies).create({'name': f'HSR {model}'})
                reason.write({'name': f'HSR {model} renamed'})
                reason.action_archive()
                self.assertFalse(reason.active)
                with self.assertRaises(AccessError):
                    reason.unlink()

    def test_enrollments_offer_new_only_to_the_secretary(self):
        secretary = create_role_user(self, 'secretary', 'test_secretary_enrollments_new')

        def root_create(user, view_type, view_xmlid=None):
            view_id = self.env.ref(view_xmlid).id if view_xmlid else False
            arch = self.env['sale.order'].with_user(user).get_views([(view_id, view_type)])['views'][view_type]['arch']
            return etree.fromstring(arch).get('create')

        for view_type in ('list', 'kanban', 'form'):
            with self.subTest(view_type=view_type):
                view_xmlid = f'ems.view_ems_enrollments_{view_type}'
                self.assertEqual(root_create(self.head_of_studies, view_type, view_xmlid), '0')
                self.assertNotEqual(root_create(secretary, view_type, view_xmlid), '0')
                # The native Sales views are left alone.
                self.assertNotEqual(root_create(self.head_of_studies, view_type), '0')
