from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCourse(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Course)',
            'login': 'test_teacher_for_course',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Course)',
            'login': 'test_secretary_for_course',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        # is_current/is_enrollment_default are unipersonal and already assigned in the
        # working database's seed data; clear them so the tests are self-contained.
        cls.env['ems.course'].sudo().search([]).write({
            'is_current': False, 'is_enrollment_default': False,
        })
        cls.test_course = cls.env['ems.course'].create({'start': 1900, 'end': 1901})

    def test_create_valid(self):
        course = self.env['ems.course'].create({'start': 1910, 'end': 1911})
        self.assertTrue(course.id)
        self.assertEqual(course.start, 1910)
        self.assertEqual(course.end, 1911)

    def test_name_computed(self):
        course = self.env['ems.course'].create({'start': 1920, 'end': 1921})
        self.assertEqual(course.name, '1920-1921')

    def test_name_must_be_unique(self):
        self.env['ems.course'].create({'start': 1930, 'end': 1931})
        with self.assertRaises(Exception):
            self.env['ems.course'].create({'start': 1930, 'end': 1931})

    def test_only_one_current_allowed(self):
        self.env['ems.course'].create({'start': 1940, 'end': 1941, 'is_current': True})
        with self.assertRaises(ValidationError):
            self.env['ems.course'].create({'start': 1941, 'end': 1942, 'is_current': True})

    def test_only_one_enrollment_default_allowed(self):
        self.env['ems.course'].create({'start': 1950, 'end': 1951, 'is_enrollment_default': True})
        with self.assertRaises(ValidationError):
            self.env['ems.course'].create({'start': 1951, 'end': 1952, 'is_enrollment_default': True})

    def test_rewriting_current_true_on_same_record_does_not_self_conflict(self):
        course = self.env['ems.course'].create({'start': 1960, 'end': 1961, 'is_current': True})
        course.write({'is_current': True})  # the uniqueness search excludes the record's own id
        self.assertTrue(course.is_current)

    def test_company_current_course_id_syncs_is_current(self):
        course_a = self.env['ems.course'].create({'start': 1970, 'end': 1971})
        course_b = self.env['ems.course'].create({'start': 1971, 'end': 1972})

        self.env.company.current_course_id = course_a.id
        self.assertTrue(course_a.is_current)
        self.assertFalse(course_b.is_current)

        self.env.company.current_course_id = course_b.id
        self.assertFalse(course_a.is_current)
        self.assertTrue(course_b.is_current)

    def test_admin_can_create(self):
        course = self.env['ems.course'].create({'start': 1980, 'end': 1981})
        self.assertTrue(course.id)

    def test_admin_can_write(self):
        course = self.env['ems.course'].create({'start': 1990, 'end': 1991})
        course.write({'start': 1991, 'end': 1992})
        self.assertEqual(course.name, '1991-1992')

    def test_admin_can_unlink(self):
        course = self.env['ems.course'].create({'start': 2000, 'end': 2001})
        course_id = course.id
        course.unlink()
        self.assertFalse(self.env['ems.course'].search([('id', '=', course_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.course'].with_user(self.teacher_user).create({'start': 2010, 'end': 2011})

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_course.with_user(self.teacher_user).write({'start': 1901})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_course.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        course = self.test_course.with_user(self.teacher_user)
        self.assertEqual(course.name, '1900-1901')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.course'].with_user(self.secretary_user).create({'start': 2020, 'end': 2021})

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_course.with_user(self.secretary_user).write({'start': 1901})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_course.with_user(self.secretary_user).unlink()

    # --- seeding the enrollment default -------------------------------------
    # is_enrollment_default is not a column of data/custom/ems.course.csv (it is live
    # state the centre moves when it opens the next campaign, and a synced column would
    # revert that move on every upgrade), so post_init_hook and the 18.0.0.22.0
    # post-migrate seed it through this helper instead.

    def test_seed_marks_the_course_after_the_current_one(self):
        self.test_course.is_current = True
        following = self.env['ems.course'].create({'start': 1901, 'end': 1902})
        seeded = self.env['ems.course']._ems_seed_enrollment_default()
        self.assertEqual(seeded, following)
        self.assertTrue(following.is_enrollment_default)

    def test_seed_leaves_an_already_flagged_course_alone(self):
        """The guard that makes it safe to re-run: whoever moved the flag on to the next
        campaign must not have it moved back by an upgrade."""
        chosen = self.env['ems.course'].create({'start': 1950, 'end': 1951,
                                                'is_enrollment_default': True})
        self.test_course.is_current = True
        self.env['ems.course'].create({'start': 1901, 'end': 1902})
        self.assertFalse(self.env['ems.course']._ems_seed_enrollment_default())
        self.assertTrue(chosen.is_enrollment_default)

    def test_seed_falls_back_to_the_earliest_course_without_a_current_one(self):
        earliest = self.env['ems.course'].search([], order='start asc', limit=1)
        self.assertEqual(self.env['ems.course']._ems_seed_enrollment_default(), earliest)

    def test_seed_leaves_exactly_one_course_flagged(self):
        self.test_course.is_current = True
        self.env['ems.course'].create({'start': 1901, 'end': 1902})
        self.env['ems.course']._ems_seed_enrollment_default()
        self.assertEqual(
            self.env['ems.course'].search_count([('is_enrollment_default', '=', True)]), 1)
