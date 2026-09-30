from odoo.tests.common import TransactionCase

from .common import create_role_user


class TestArchiveEntry(TransactionCase):
    """The web client offers Archive/Unarchive whenever a model's `active` field isn't readonly
    in fields_get(). A plain teacher's write access to contacts and employees is either missing
    or narrowed by record rules to a tutor's own students/families (and archiving a student is a
    withdrawal, secretary/Head of Studies/admin only), so for them `active` is reported readonly
    and the entry is never offered (EmsBase.fields_get_active_readonly_for_teachers)."""

    def _active_readonly(self, model, user):
        return self.env[model].with_user(user).fields_get(['active'], ['readonly'])['active']['readonly']

    def test_teaching_roles_get_no_archive_entry(self):
        for role in ('teacher', 'tutor', 'orientation', 'coexistence'):
            user = create_role_user(self, role, f'test_archive_entry_{role}')
            for model in ('res.partner', 'hr.employee'):
                self.assertTrue(self._active_readonly(model, user), (role, model))

    def test_roles_that_can_archive_keep_the_entry(self):
        for role in ('secretary', 'head_of_studies', 'academic_admin'):
            user = create_role_user(self, role, f'test_archive_entry_{role}')
            for model in ('res.partner', 'hr.employee'):
                self.assertFalse(self._active_readonly(model, user), (role, model))

    def test_tac_archives_employees_but_not_contacts(self):
        # TAC implies hr.group_hr_user (write on employees), but writes contacts only as a teacher.
        tac = create_role_user(self, 'tac', 'test_archive_entry_tac')
        self.assertTrue(self._active_readonly('res.partner', tac))
        self.assertFalse(self._active_readonly('hr.employee', tac))

    def test_other_attributes_untouched(self):
        # Only a readonly already being asked for is overridden: fields_get() without it, or
        # without `active`, comes back as Odoo builds it.
        teacher = create_role_user(self, 'teacher', 'test_archive_entry_attrs')
        partners = self.env['res.partner'].with_user(teacher)
        self.assertNotIn('readonly', partners.fields_get(['active'], ['string'])['active'])
        self.assertNotIn('active', partners.fields_get(['name'], ['readonly']))
