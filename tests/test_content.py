from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestContent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Content)',
            'login': 'test_teacher_for_content',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Content)',
            'login': 'test_secretary_for_content',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_subject = cls.env['ems.subject'].create({
            'code': 'TST_CONT_SUBJ',
            'acronym': 'TCTS',
            'name': 'Test Subject for Content',
        })
        cls.test_content = cls.env['ems.content'].create({
            'code': 'TST_CONT_SUBJ_C1',
            'acronym': 'C1',
            'name': 'Test Content',
            'subject_id': cls.test_subject.id,
        })

    def test_create_valid_root(self):
        content = self.env['ems.content'].create({
            'code': 'T01',
            'acronym': 'T01A',
            'name': 'Test 01',
            'subject_id': self.test_subject.id,
        })
        self.assertTrue(content.id)
        self.assertEqual(content.subject_id, self.test_subject)
        self.assertEqual(content.level, 1)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.content'].create({
                'acronym': 'T02',
                'name': 'No Code',
                'subject_id': self.test_subject.id,
            })

    def test_code_must_be_unique_per_subject(self):
        with self.assertRaises(Exception):
            self.env['ems.content'].create({
                'code': 'TST_CONT_SUBJ_C1',
                'acronym': 'DUP',
                'name': 'Duplicate Code',
                'subject_id': self.test_subject.id,
            })

    def test_display_name_computed(self):
        content = self.env['ems.content'].create({
            'code': 'T03',
            'acronym': 'T03A',
            'name': 'Test Display',
            'subject_id': self.test_subject.id,
        })
        self.assertEqual(content.display_name, 'T03A: Test Display')

    def test_nested_composite_derives_subject_and_level(self):
        child = self.env['ems.content'].create({
            'code': 'TST_CONT_SUBJ_C1_A',
            'acronym': 'C1A',
            'name': 'Test Child',
            'content_id': self.test_content.id,
        })
        self.assertEqual(child.subject_id, self.test_subject)
        self.assertEqual(child.level, 2)
        self.assertIn(child, self.test_content.content_ids)

    def test_nested_composite_code_must_start_with_parent_code(self):
        with self.assertRaises(ValidationError):
            self.env['ems.content'].create({
                'code': 'WRONG_PREFIX',
                'acronym': 'WPX',
                'name': 'Bad Prefix',
                'content_id': self.test_content.id,
            })

    def test_root_content_code_not_checked_against_subject(self):
        # Root items (no content_id) are exempt from the code-prefix check — only nested
        # composites must start with their direct parent's code.
        content = self.env['ems.content'].create({
            'code': 'ANY_CODE_WORKS',
            'acronym': 'ACW',
            'name': 'No Prefix Required',
            'subject_id': self.test_subject.id,
        })
        self.assertTrue(content.id)

    def test_grandchild_level_increments(self):
        child = self.env['ems.content'].create({
            'code': 'TST_CONT_SUBJ_C1_B',
            'acronym': 'C1B',
            'name': 'Child',
            'content_id': self.test_content.id,
        })
        grandchild = self.env['ems.content'].create({
            'code': 'TST_CONT_SUBJ_C1_B_1',
            'acronym': 'C1B1',
            'name': 'Grandchild',
            'content_id': child.id,
        })
        self.assertEqual(grandchild.level, 3)
        self.assertEqual(grandchild.subject_id, self.test_subject)

    def test_admin_can_create(self):
        content = self.env['ems.content'].create({
            'code': 'T04',
            'acronym': 'T04A',
            'name': 'Admin Test',
            'subject_id': self.test_subject.id,
        })
        self.assertTrue(content.id)

    def test_admin_can_write(self):
        content = self.env['ems.content'].create({
            'code': 'T05',
            'acronym': 'T05A',
            'name': 'Before Write',
            'subject_id': self.test_subject.id,
        })
        content.write({'name': 'After Write'})
        self.assertEqual(content.name, 'After Write')

    def test_admin_can_unlink(self):
        content = self.env['ems.content'].create({
            'code': 'T06',
            'acronym': 'T06A',
            'name': 'To Delete',
            'subject_id': self.test_subject.id,
        })
        content_id = content.id
        content.unlink()
        self.assertFalse(self.env['ems.content'].search([('id', '=', content_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.content'].with_user(self.teacher_user).create({
                'code': 'T07',
                'acronym': 'T07A',
                'name': 'Teacher Attempt',
                'subject_id': self.test_subject.id,
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_content.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_content.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        content = self.test_content.with_user(self.teacher_user)
        self.assertEqual(content.name, 'Test Content')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.content'].with_user(self.secretary_user).create({
                'code': 'T08',
                'acronym': 'T08A',
                'name': 'Secretary Attempt',
                'subject_id': self.test_subject.id,
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_content.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_content.with_user(self.secretary_user).unlink()
