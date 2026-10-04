from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestContent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
