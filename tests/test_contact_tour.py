from odoo.tests import tagged, HttpCase

from .common import create_level_study_group, create_role_user, force_user_language_to_english


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
            'name': '0000 Contact Tour Student', 'contact_type': 'student',
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
            'name': '0000 HoS Contact Tour Student', 'contact_type': 'student',
            'student_email': 'hos.contact.tour.student@example.com',
            'level_id': level.id, 'study_id': study.id, 'main_group_id': group.id,
        })
        self.start_tour("/odoo", "ems_contact_head_of_studies_full_access", login=hos_user.login, step_delay=300)
