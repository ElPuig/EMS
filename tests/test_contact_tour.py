from odoo.tests import tagged, HttpCase

from .common import (
    create_level_study_group, create_role_employee, create_role_user, force_user_language_to_english,
    next_student_id,
)


@tagged('post_install', '-at_install')
class TestContactTour(HttpCase):

    def test_contact_tabs_and_relation_wizard_tour(self):
        # The tour asserts on literal English tab names (e.g. "Student data", "Studies") for
        # the real 'admin' login, which only works if admin's own language is en_US - not
        # guaranteed on every dev box. See CLAUDE.md's "Tour tests and language" convention.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        level, study, group = create_level_study_group(self, 'TCNT')
        self.env['ems.subject'].create({
            'code': 'TCNT001', 'acronym': 'TCNT', 'name': 'Test Subject (Contact Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Test Reinforcement Group (Contact Tour)',
        })
        # "0000 " prefix: res.partner's _order is "name", so this seeded student sorts
        # first on the list's very first page among the ~1000+ real students already in
        # this DB (see test_withdrawal_tour.py for the same pattern).
        self.env['res.partner'].create({
            'name': '0000 Contact Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'contact.tour.student@example.com',
            'level_id': level.id, 'study_id': study.id, 'main_group_id': group.id,
        })
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_contact_tabs_and_relation_wizard", login="admin", watch=True)
        self.start_tour("/odoo", "ems_contact_tabs_and_relation_wizard", login="admin", step_delay=300)

    def test_contact_head_of_studies_full_access_tour(self):
        # Issue #448: the reported bug was specifically that a Head/Deputy Head of Studies (not
        # the student's own tutor) saw the personal-data block hidden and hit an AccessError
        # adding/removing a family contact - a plain TransactionCase can prove the permission
        # wiring (tests/test_student_data_reader.py, tests/test_contact_relation_wizard.py), but
        # only a real browser run proves the view actually renders the now-visible block and the
        # button/wizard/inline-unlink genuinely work end to end. Deliberately not the student's
        # tutor, least-privileged role per CLAUDE.md's Development workflow, and a dedicated tour
        # rather than reusing the admin one above: this fix does not extend write access to
        # enrollments/grades/attendance, so the admin tour's Studies-tab step would fail for the
        # wrong reason (out of scope) rather than the one this test is actually about.
        hos_user = create_role_user(self, 'head_of_studies', 'test_hos_contact_tour', name='HoS Contact Tour')
        level, study, group = create_level_study_group(self, 'TCNH')
        self.env['res.partner'].create({
            'name': '0000 HoS Contact Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'hos.contact.tour.student@example.com',
            'level_id': level.id, 'study_id': study.id, 'main_group_id': group.id,
        })
        self.start_tour("/odoo", "ems_contact_head_of_studies_full_access", login=hos_user.login, step_delay=300)

    def test_new_student_requires_student_id_tour(self):
        # Issue #460: the student data block marks the Student ID (IDALU) required while the
        # student is new, and the student saves once it is filled in. Logged in as secretary,
        # the least-privileged role that registers students.
        secretary = create_role_user(self, 'secretary', 'test_secretary_student_id_tour', name='Secretary IDALU Tour')
        self.start_tour("/odoo", "ems_contact_new_student_requires_student_id", login=secretary.login)

    def test_contact_tutor_deletes_family_contact_tour(self):
        # Issue #470: a tutor hit an AccessError deleting a family contact of their own student
        # from the Contacts & Addresses tab. Logged in as that tutor - the only role the bug
        # affected (secretary and Head of Studies already held the Contact Creation group).
        tutor_user = create_role_user(self, 'tutor', 'test_tutor_contact_tour', name='Tutor Contact Tour')
        tutor = create_role_employee(self, tutor_user)
        __, __, group = create_level_study_group(self, 'TCNF', group={'tutor_id': tutor.id})
        student = self.env['res.partner'].create({
            'name': '0000 Tutor Contact Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        family = self.env['res.partner'].create({'name': 'Tutor Tour Mother', 'contact_type': 'family'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id,
        })

        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_contact_tutor_deletes_family_contact",
                        login=tutor_user.login)

        self.assertFalse(family.exists(), "the family contact was left orphaned, so it is removed too")
