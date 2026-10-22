from odoo.tests import tagged, HttpCase

from .common import create_level_study, create_role_user, force_user_language_to_english, next_student_id


@tagged('post_install', '-at_install')
class TestGroupTour(HttpCase):

    def test_group_form_tabs_and_reinforcement_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin")

    def test_group_reactivate_archived_duplicate_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # Reinforcement groups (plain Name, no Many2one selection) keep this tour free of the
        # level->study->tutor selection fragility already noted in the tour above - only the
        # create()/write() duplicate-name-vs-archived-group behaviour is under test here, not
        # 'main' group creation itself (already covered by that other tour and test_group.py).
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archived Reinforcement Reactivate',
        }).active = False
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archived Reinforcement Cancel',
        }).active = False
        self.start_tour("/odoo", "ems_group_reactivate_archived_duplicate", login="admin")

    def test_group_archive_confirmation_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # Reinforcement groups again, for the same low-fragility reason as above - a plain Name
        # and a subject enrollment (the real, only mechanism for reinforcement membership since
        # reinforcement_student_ids was removed - see group.md), no Many2one selection needed
        # to set the scene up beyond that.
        subject = self.env['ems.subject'].create({
            'code': 'TOURARCH', 'acronym': 'TARC', 'name': 'Tour Archive Confirm Subject',
        })
        student_accept = self.env['res.partner'].create({
            'name': 'Tour Archive Confirm Student Accept', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        accept_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archive Confirm Accept',
        })
        self.env['ems.enrollment'].create({
            'student_id': student_accept.id, 'group_id': accept_group.id, 'subject_id': subject.id,
        })
        student_decline = self.env['res.partner'].create({
            'name': 'Tour Archive Confirm Student Decline', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        decline_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archive Confirm Decline',
        })
        self.env['ems.enrollment'].create({
            'student_id': student_decline.id, 'group_id': decline_group.id, 'subject_id': subject.id,
        })
        self.start_tour("/odoo", "ems_group_archive_confirmation", login="admin")


@tagged('post_install', '-at_install')
class TestGroupFillParentGroupsTour(HttpCase):
    """A reinforcement group's main groups filled from its enrolled students, as the Department
    Chief: the least-privileged role that can edit a group."""

    def test_group_fill_parent_groups_tour(self):
        chief = create_role_user(self, 'department_chief', 'test_tour_fill_parents_chief')
        level, study = create_level_study(self, 'TFPG', level={'name': 'Tour Fill Parents Level'})
        main_groups = self.env['ems.group'].create([
            {'course': 2, 'acronym': acronym, 'level_id': level.id, 'study_id': study.id} for acronym in ('X', 'Y')])
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'Tour Fill Parents'})
        subject = self.env['ems.subject'].create({'code': 'TFPG001', 'acronym': 'TFPG', 'name': 'Tour Fill Parents Subject'})
        for main_group in main_groups:
            student = self.env['res.partner'].create({
                'name': f'Tour Fill Parents Student {main_group.acronym}', 'contact_type': 'student',
                'student_id': next_student_id(), 'main_group_id': main_group.id})
            self.env['ems.enrollment'].create({'student_id': student.id, 'group_id': group.id, 'subject_id': subject.id})

        self.start_tour("/odoo", "ems_group_fill_parent_groups", login=chief.login)

        self.assertEqual(group.parent_group_ids, main_groups)


@tagged('post_install', '-at_install')
class TestGroupJoinsWithTour(HttpCase):
    """Issue #676: the Department Chief (the least-privileged role that can edit a group) says on
    one half of a split group which group is its other half. That half had another tutor: the form
    asks, and the chief keeps it (issue #688). The delegate, chosen among the other half's students,
    reaches the other half too (it had none); a new tutor reaches it when the chief replicates it."""

    def test_group_joins_with_tour(self):
        chief = create_role_user(self, 'department_chief', 'test_tour_joins_with_chief')
        level, study = create_level_study(self, 'TJWG', level={'name': 'Tour Joins With Level'})
        tutor, other_tutor, new_tutor = self.env['hr.employee'].create([
            {'name': f'Tour Joins With Tutor {n}', 'employee_type': 'teacher'} for n in (1, 2, 3)])
        half_a, half_b = self.env['ems.group'].create([
            {'course': 1, 'acronym': acronym, 'level_id': level.id, 'study_id': study.id, 'tutor_id': tutor_id}
            for acronym, tutor_id in (('A', tutor.id), ('B', other_tutor.id))])
        student = self.env['res.partner'].create({
            'name': 'Tour Joins With Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': half_b.id})

        self.start_tour("/odoo", "ems_group_joins_with", login=chief.login)

        self.assertEqual((half_a.joinable_group_ids, half_b.joinable_group_ids), (half_b, half_a))
        for half in half_a | half_b:
            self.assertEqual((half.tutor_id, half.delegate_id), (new_tutor, student), half.name)
