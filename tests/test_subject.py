from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSubject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Subject)',
            'login': 'test_teacher_for_subject',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Subject)',
            'login': 'test_secretary_for_subject',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_subject = cls.env['ems.subject'].create({
            'code': 'TST_SUBJ_001',
            'acronym': 'TSSJ',
            'name': 'Test Subject',
        })

    def test_create_valid(self):
        subject = self.env['ems.subject'].create({
            'code': 'T01',
            'acronym': 'T01A',
            'name': 'Test 01',
        })
        self.assertTrue(subject.id)
        self.assertEqual(subject.code, 'T01')
        self.assertEqual(subject.acronym, 'T01A')
        self.assertEqual(subject.name, 'Test 01')

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.subject'].create({'acronym': 'T02', 'name': 'No Code'})

    def test_create_missing_acronym(self):
        with self.assertRaises(Exception):
            self.env['ems.subject'].create({'code': 'T03', 'name': 'No Acronym'})

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.subject'].create({'code': 'T04', 'acronym': 'T04A'})

    def test_code_must_be_unique(self):
        self.env['ems.subject'].create({'code': 'UNIQ001', 'acronym': 'UQA', 'name': 'First'})
        with self.assertRaises(Exception):
            self.env['ems.subject'].create({'code': 'UNIQ001', 'acronym': 'UQB', 'name': 'Second'})

    def test_code_can_repeat_across_disjoint_studies(self):
        # The same official code can mean two genuinely different subjects when each belongs to
        # its own curriculum (e.g. MP 3003 has different learning outcomes and hours in a CFGB
        # and in a PFI) - a plain global unique(code) would force a fake suffix on one of them.
        study_a = self.env['ems.study'].create({
            'code': 'DUPSTA', 'acronym': 'DSA', 'name': 'Dup Study A', 'date': '2024-09-01',
        })
        study_b = self.env['ems.study'].create({
            'code': 'DUPSTB', 'acronym': 'DSB', 'name': 'Dup Study B', 'date': '2024-09-01',
        })
        self.env['ems.subject'].create({
            'code': 'DUP001', 'acronym': 'DA', 'name': 'First', 'study_ids': [(6, 0, [study_a.id])],
        })
        second = self.env['ems.subject'].create({
            'code': 'DUP001', 'acronym': 'DB', 'name': 'Second', 'study_ids': [(6, 0, [study_b.id])],
        })
        self.assertTrue(second.id)

    def test_code_blocked_when_studies_overlap(self):
        study = self.env['ems.study'].create({
            'code': 'DUPSTC', 'acronym': 'DSC', 'name': 'Dup Study C', 'date': '2024-09-01',
        })
        self.env['ems.subject'].create({
            'code': 'DUP002', 'acronym': 'DC', 'name': 'First', 'study_ids': [(6, 0, [study.id])],
        })
        with self.assertRaises(Exception):
            self.env['ems.subject'].create({
                'code': 'DUP002', 'acronym': 'DD', 'name': 'Second', 'study_ids': [(6, 0, [study.id])],
            })

    def test_code_blocked_when_other_subject_has_no_study(self):
        study = self.env['ems.study'].create({
            'code': 'DUPSTD', 'acronym': 'DSD', 'name': 'Dup Study D', 'date': '2024-09-01',
        })
        self.env['ems.subject'].create({'code': 'DUP003', 'acronym': 'DE', 'name': 'Unscoped'})
        with self.assertRaises(Exception):
            self.env['ems.subject'].create({
                'code': 'DUP003', 'acronym': 'DF', 'name': 'Scoped', 'study_ids': [(6, 0, [study.id])],
            })

    def test_code_conflict_message_translates_to_catalan(self):
        # Code ('_()') translations in this Odoo version are read straight from this module's
        # own checked-in i18n/ca_ES.po at runtime, with no DB column to verify via psql - a
        # functional check under a real 'lang' context is the only way to actually prove this
        # message (moved from an SQL constraint to a Python-raised _() call) still translates.
        study = self.env['ems.study'].with_context(lang='ca_ES').create({
            'code': 'DUPSTG', 'acronym': 'DSG', 'name': 'Dup Study G', 'date': '2024-09-01',
        })
        self.env['ems.subject'].with_context(lang='ca_ES').create({
            'code': 'DUP005', 'acronym': 'DI', 'name': 'First', 'study_ids': [(6, 0, [study.id])],
        })
        with self.assertRaises(Exception) as capture:
            self.env['ems.subject'].with_context(lang='ca_ES').create({
                'code': 'DUP005', 'acronym': 'DJ', 'name': 'Second', 'study_ids': [(6, 0, [study.id])],
            })
        self.assertIn('codi duplicat', str(capture.exception))

    def test_code_conflict_detected_from_study_side(self):
        # 'ems.study.subject_ids' is the same many2many relation viewed from the other side (the
        # 'Subjects' tab on the study's own form) - editing it there must re-validate the subject's
        # constraint just as reliably as editing 'study_ids' from the subject's own form.
        study_e = self.env['ems.study'].create({
            'code': 'DUPSTE', 'acronym': 'DSE', 'name': 'Dup Study E', 'date': '2024-09-01',
        })
        study_f = self.env['ems.study'].create({
            'code': 'DUPSTF', 'acronym': 'DSF', 'name': 'Dup Study F', 'date': '2024-09-01',
        })
        self.env['ems.subject'].create({
            'code': 'DUP004', 'acronym': 'DG', 'name': 'First', 'study_ids': [(6, 0, [study_e.id])],
        })
        second = self.env['ems.subject'].create({
            'code': 'DUP004', 'acronym': 'DH', 'name': 'Second', 'study_ids': [(6, 0, [study_f.id])],
        })
        with self.assertRaises(Exception):
            study_e.write({'subject_ids': [(4, second.id)]})

    def test_display_name_computed(self):
        subject = self.env['ems.subject'].create({
            'code': 'T05',
            'acronym': 'T05A',
            'name': 'Test Display',
        })
        self.assertEqual(subject.display_name, 'T05A: Test Display')

    def test_total_hours_computed(self):
        subject = self.env['ems.subject'].create({
            'code': 'T06',
            'acronym': 'T06A',
            'name': 'Test Hours',
            'internal_hours': 60,
            'external_hours': 40,
        })
        self.assertEqual(subject.total_hours, 100)
        subject.internal_hours = 70
        self.assertEqual(subject.total_hours, 110)

    def test_product_auto_created_on_create(self):
        subject = self.env['ems.subject'].create({
            'code': 'T07',
            'acronym': 'T07A',
            'name': 'Test Product Sync',
        })
        self.assertTrue(subject.product_id)
        self.assertEqual(subject.product_id.name, 'Test Product Sync')
        self.assertEqual(subject.product_id.default_code, 'T07')

    def test_product_is_tutoria_flag(self):
        subject = self.env['ems.subject'].create({
            'code': 'T1_TUTORIA',
            'acronym': 'TUT',
            'name': 'Tutoria Slot',
        })
        self.assertTrue(subject.product_id.ems_is_tutoria)

    def test_product_synced_on_write(self):
        subject = self.env['ems.subject'].create({
            'code': 'T08',
            'acronym': 'T08A',
            'name': 'Before Rename',
        })
        subject.write({'name': 'After Rename', 'code': 'T08B'})
        self.assertEqual(subject.product_id.name, 'After Rename')
        self.assertEqual(subject.product_id.default_code, 'T08B')

    def test_product_self_heals_if_missing(self):
        subject = self.env['ems.subject'].create({
            'code': 'T09',
            'acronym': 'T09A',
            'name': 'Self Heal Test',
        })
        subject.product_id.unlink()
        self.assertFalse(subject.product_id)
        subject.write({'notes': 'trigger write'})
        self.assertTrue(subject.product_id)

    def test_admin_can_create(self):
        subject = self.env['ems.subject'].create({
            'code': 'T10',
            'acronym': 'T10A',
            'name': 'Admin Test',
        })
        self.assertTrue(subject.id)

    def test_admin_can_write(self):
        subject = self.env['ems.subject'].create({
            'code': 'T11',
            'acronym': 'T11A',
            'name': 'Before Write',
        })
        subject.write({'name': 'After Write'})
        self.assertEqual(subject.name, 'After Write')

    def test_admin_can_unlink(self):
        subject = self.env['ems.subject'].create({
            'code': 'T12',
            'acronym': 'T12A',
            'name': 'To Delete',
        })
        subject_id = subject.id
        subject.unlink()
        self.assertFalse(self.env['ems.subject'].search([('id', '=', subject_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.subject'].with_user(self.teacher_user).create({
                'code': 'T13',
                'acronym': 'T13A',
                'name': 'Teacher Attempt',
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_subject.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_subject.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        subject = self.test_subject.with_user(self.teacher_user)
        self.assertEqual(subject.name, 'Test Subject')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.subject'].with_user(self.secretary_user).create({
                'code': 'T14',
                'acronym': 'T14A',
                'name': 'Secretary Attempt',
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_subject.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_subject.with_user(self.secretary_user).unlink()
