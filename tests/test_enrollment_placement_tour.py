from odoo.tests import tagged, HttpCase

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestEnrollmentPlacementTour(HttpCase):
    """Browser coverage for the per-subject destination-placement fix (D20):
    confirming an individual repeater's enrollment - not the course transition
    wizard's own Apply, deliberately never tour-tested (see course_transition_tour.js)
    - must land a subject pending from an earlier course in that course's own group."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'EPT', level={'name': 'Enrollment Placement Tour Level'}, study={
            'code': 'EPT001', 'acronym': 'EPT', 'name': 'Enrollment Placement Tour Study',
        })
        # A partially-transitioned study: an individual confirmation places the student
        # right away instead of waiting for the (never tour-tested) wizard bulk pass -
        # see sale.order._ems_placement_is_individual().
        cls.study.transition_state = 'transitioned'
        cls.course = cls.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or cls.env['ems.course'].create({'start': 2097, 'end': 2098, 'is_enrollment_default': True})
        cls.g1a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.g2a = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        template1 = cls.env['sale.order.template'].create({
            'name': 'EPT Template C1', 'ems_study_id': cls.study.id, 'study_year': 1})
        template2 = cls.env['sale.order.template'].create({
            'name': 'EPT Template C2', 'ems_study_id': cls.study.id, 'study_year': 2})
        cls.pending_subject = cls.env['ems.subject'].create({
            'code': 'EPTSUB1', 'acronym': 'EPTS1', 'name': 'Pending Subject Tour',
            'study_ids': [(6, 0, [cls.study.id])]})
        template1.sale_order_template_line_ids = [
            (0, 0, {'product_id': cls.pending_subject.product_id.id})]
        cls.tutorship = cls.env['ems.subject'].create({
            'code': 'EPTTUT2', 'acronym': 'EPTTUT2', 'name': 'Tutorship Tour C2',
            'is_tutorship': True, 'study_ids': [(6, 0, [cls.study.id])]})
        template2.sale_order_template_line_ids = [
            (0, 0, {'product_id': cls.tutorship.product_id.id})]
        cls.student = cls.env['res.partner'].create({
            'name': 'Enrollment Placement Tour Student', 'contact_type': 'student',
            'main_group_id': cls.g2a.id})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': cls.study.id,
            'ems_course_id': cls.course.id, 'shift': 'morning', 'ems_group_id': cls.g2a.id})
        cls.order.order_line = [
            (0, 0, {'product_id': cls.tutorship.product_id.id}),
            (0, 0, {'product_id': cls.pending_subject.product_id.id}),
        ]

    def test_pending_subject_lands_in_its_own_course_group_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To watch this tour in a real browser during development:
        #   self.start_tour("/odoo", "enrollment_placement_pending_subject", login="admin", watch=True)
        self.start_tour("/odoo", "enrollment_placement_pending_subject", login="admin")
        enrollment = self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.pending_subject.id)])
        self.assertEqual(enrollment.group_id, self.g1a)
        tutorship_enrollment = self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.tutorship.id)])
        self.assertEqual(tutorship_enrollment.group_id, self.g2a)
