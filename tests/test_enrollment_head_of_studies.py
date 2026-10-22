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

    # Configuration > Enrollment's menus: TestAuthorizationMenus.
    MENUS = ('ems.menu_ems_enrollments', 'ems.menu_ems_applicants', 'ems.menu_students_no_destination')

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
        secretary = create_role_user(self, 'secretary', 'test_secretary_preinscription_list')
        view = 'ems.view_applicant_list'
        hos_flags = self._root_flags(self.head_of_studies, 'res.partner', 'list', view)
        self.assertFalse(hos_flags['create'] or hos_flags['delete'])
        secretary_flags = self._root_flags(secretary, 'res.partner', 'list', view)
        self.assertTrue(secretary_flags['create'] and secretary_flags['delete'])

    def _root_flags(self, user, model, view_type, view_xmlid=None):
        view_id = self.env.ref(view_xmlid).id if view_xmlid else False
        arch = self.env[model].with_user(user).get_views([(view_id, view_type)])['views'][view_type]['arch']
        root = etree.fromstring(arch)
        return {attr: root.get(attr) not in ('0', 'false', 'False') for attr in ('create', 'edit', 'delete')}

    def test_enrollments_are_read_only_except_for_the_secretary(self):
        secretary = create_role_user(self, 'secretary', 'test_secretary_enrollments_new')
        read_only = {'create': False, 'edit': False, 'delete': False}
        for view_type in ('list', 'kanban', 'form'):
            with self.subTest(view_type=view_type):
                view_xmlid = f'ems.view_ems_enrollments_{view_type}'
                self.assertEqual(self._root_flags(self.head_of_studies, 'sale.order', view_type, view_xmlid), read_only)
                self.assertTrue(self._root_flags(secretary, 'sale.order', view_type, view_xmlid)['create'])
                # The native Sales views are left alone.
                self.assertTrue(self._root_flags(self.head_of_studies, 'sale.order', view_type)['create'])

    def test_academic_admin_keeps_editing_the_read_only_screens(self):
        """The academic admin sits above the Director, who reads these screens only: they keep
        New, Edit and Delete there with that role alone (no secretary group)."""
        admin = create_role_user(self, 'academic_admin', 'test_admin_enrollment_screens')
        full = {'create': True, 'edit': True, 'delete': True}
        for model, view_type, view_xmlid in (
                ('sale.order', 'list', 'ems.view_ems_enrollments_list'),
                ('sale.order', 'form', 'ems.view_ems_enrollments_form'),
                ('res.partner', 'list', 'ems.view_applicant_list'),
                ('res.partner', 'form', 'ems.view_enrollment_contact_form')):
            with self.subTest(view=view_xmlid):
                self.assertEqual(self._root_flags(admin, model, view_type, view_xmlid), full)

    def test_contact_form_from_enrollment_screens_is_read_only_for_head_of_studies(self):
        secretary = create_role_user(self, 'secretary', 'test_secretary_enrollment_contact')
        form = 'ems.view_enrollment_contact_form'
        self.assertEqual(self._root_flags(self.head_of_studies, 'res.partner', 'form', form),
                         {'create': False, 'edit': False, 'delete': False})
        self.assertEqual(self._root_flags(secretary, 'res.partner', 'form', form),
                         {'create': True, 'edit': True, 'delete': True})
        # The contact form everywhere else keeps the Heads of Studies' contact rights.
        self.assertTrue(self._root_flags(self.head_of_studies, 'res.partner', 'form')['edit'])
        for action in ('ems.action_ems_applicants', 'ems.action_students_no_destination'):
            with self.subTest(action=action):
                self.assertIn((self.env.ref(form).id, 'form'), self.env.ref(action).views)

    def test_nobody_deletes_contacts_from_students_without_destination(self):
        secretary = create_role_user(self, 'secretary', 'test_secretary_no_destination_delete')
        self.assertFalse(self._root_flags(secretary, 'res.partner', 'list', 'ems.view_student_list_no_destination')['delete'])

    def test_enrollment_items_follow_the_acl(self):
        secretary = create_role_user(self, 'secretary', 'test_secretary_enrollment_items')
        for view_type, view_xmlid in (('list', 'ems.view_ems_enrollment_items_tree'),
                                      ('form', 'ems.view_ems_enrollment_items_form')):
            with self.subTest(view_type=view_type):
                self.assertFalse(self._root_flags(self.head_of_studies, 'product.template', view_type, view_xmlid)['create'])
                self.assertTrue(self._root_flags(secretary, 'product.template', view_type, view_xmlid)['create'])
        self.assertFalse(self._root_flags(self.head_of_studies, 'product.template', 'form', 'ems.view_ems_enrollment_items_form')['edit'])

    def test_task_assignment_editable_by_the_academic_admin(self):
        admin = create_role_user(self, 'academic_admin', 'test_admin_task_assignment')
        ems_type = self.env['mail.activity.type'].search([('ems_task_assignment', '=', True)], limit=1)
        ems_type.with_user(admin).write({'summary': 'Edited by the academic admin'})
        other_type = self.env['mail.activity.type'].search([('ems_task_assignment', '=', False)], limit=1)
        with self.assertRaises(AccessError):
            other_type.with_user(admin).write({'summary': 'Not EMS'})


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
