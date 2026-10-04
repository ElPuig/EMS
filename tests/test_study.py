from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_user


class TestStudy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Study)',
            'login': 'test_teacher_for_study',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Study)',
            'login': 'test_secretary_for_study',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_level, cls.test_study = create_level_study(cls, 'TSTL', level={'name': 'Test Level for Study'}, study={
            'code': 'TST_STUDY_001', 'acronym': 'TSST', 'name': 'Test Study', 'date': date(2024, 9, 1),
        })

    def test_create_valid(self):
        study = self.env['ems.study'].create({
            'code': 'T01',
            'acronym': 'T01A',
            'name': 'Test 01',
            'date': date(2024, 9, 1),
        })
        self.assertTrue(study.id)
        self.assertEqual(study.code, 'T01')
        self.assertEqual(study.acronym, 'T01A')
        self.assertEqual(study.name, 'Test 01')

    def test_deprecated_defaults_to_false(self):
        study = self.env['ems.study'].create({
            'code': 'T01D',
            'acronym': 'T01D',
            'name': 'Test Default Deprecated',
            'date': date(2024, 9, 1),
        })
        self.assertFalse(study.deprecated)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'acronym': 'T02',
                'name': 'No Code',
                'date': date(2024, 9, 1),
            })

    def test_create_missing_acronym(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'T03',
                'name': 'No Acronym',
                'date': date(2024, 9, 1),
            })

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'T04',
                'acronym': 'T04A',
                'date': date(2024, 9, 1),
            })

    def test_create_missing_date(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'T05',
                'acronym': 'T05A',
                'name': 'No Date',
            })

    def test_code_must_be_unique(self):
        self.env['ems.study'].create({
            'code': 'UNIQ001',
            'acronym': 'UQA',
            'name': 'First',
            'date': date(2024, 9, 1),
        })
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'UNIQ001',
                'acronym': 'UQB',
                'name': 'Second',
                'date': date(2024, 9, 1),
            })

    def test_display_name_computed(self):
        study = self.env['ems.study'].create({
            'code': 'T06',
            'acronym': 'T06A',
            'name': 'Test Display',
            'date': date(2024, 9, 1),
        })
        self.assertEqual(study.display_name, 'T06A (2024): Test Display')

    def test_level_relation(self):
        self.assertIn(self.test_study, self.test_level.study_ids)

    def test_uses_enrollment_flow_false_by_default(self):
        self.assertFalse(self.test_study.uses_enrollment_flow)

    def test_uses_enrollment_flow_true_with_active_template(self):
        self.env['sale.order.template'].create({
            'name': 'Test Template for Study',
            'ems_study_id': self.test_study.id,
        })
        self.assertTrue(self.test_study.uses_enrollment_flow)

    def test_uses_enrollment_flow_search(self):
        study_without_flow = self.env['ems.study'].create({
            'code': 'T07',
            'acronym': 'T07A',
            'name': 'Without Flow',
            'date': date(2024, 9, 1),
        })
        self.env['sale.order.template'].create({
            'name': 'Test Template for Search',
            'ems_study_id': self.test_study.id,
        })
        with_flow = self.env['ems.study'].search([('uses_enrollment_flow', '=', True)])
        without_flow = self.env['ems.study'].search([('uses_enrollment_flow', '=', False)])
        self.assertIn(self.test_study, with_flow)
        self.assertNotIn(study_without_flow, with_flow)
        self.assertIn(study_without_flow, without_flow)
        self.assertNotIn(self.test_study, without_flow)

    def test_admin_can_create(self):
        study = self.env['ems.study'].create({
            'code': 'T08',
            'acronym': 'T08A',
            'name': 'Admin Test',
            'date': date(2024, 9, 1),
        })
        self.assertTrue(study.id)

    def test_admin_can_write(self):
        study = self.env['ems.study'].create({
            'code': 'T09',
            'acronym': 'T09A',
            'name': 'Before Write',
            'date': date(2024, 9, 1),
        })
        study.write({'name': 'After Write'})
        self.assertEqual(study.name, 'After Write')

    def test_admin_can_unlink(self):
        study = self.env['ems.study'].create({
            'code': 'T10',
            'acronym': 'T10A',
            'name': 'To Delete',
            'date': date(2024, 9, 1),
        })
        study_id = study.id
        study.unlink()
        self.assertFalse(self.env['ems.study'].search([('id', '=', study_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.study'].with_user(self.teacher_user).create({
                'code': 'T11',
                'acronym': 'T11A',
                'name': 'Teacher Attempt',
                'date': date(2024, 9, 1),
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        study = self.test_study.with_user(self.teacher_user)
        self.assertEqual(study.name, 'Test Study')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.study'].with_user(self.secretary_user).create({
                'code': 'T12',
                'acronym': 'T12A',
                'name': 'Secretary Attempt',
                'date': date(2024, 9, 1),
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.secretary_user).unlink()

    def _attachment_command(self, name):
        return (0, 0, {'name': name, 'raw': b'curriculum', 'res_model': 'ems.study'})

    def test_teacher_reads_attachment_uploaded_by_someone_else(self):
        """Regression (#553): the form's attachments list creates each file without a res_id,
        and Odoo only lets the uploader (or a system admin) read an unlinked attachment, so a
        teacher saw an empty 'Attached files' tab on every study."""
        self.test_study.write({'attachment_ids': [self._attachment_command('curriculum.pdf')]})
        teacher_user = create_role_user(self, 'teacher', 'test_teacher_study_attachment')
        self.env.invalidate_all()

        names = self.test_study.with_user(teacher_user).attachment_ids.mapped('name')
        self.assertEqual(names, ['curriculum.pdf'])

    def test_attachment_created_with_study_is_linked(self):
        study = self.env['ems.study'].create({
            'code': 'T13', 'acronym': 'T13A', 'name': 'Study With Attachment', 'date': date(2024, 9, 1),
            'attachment_ids': [self._attachment_command('curriculum.pdf')],
        })
        self.assertEqual(study.attachment_ids.res_id, study.id)
        self.assertEqual(study.attachment_ids.res_model, 'ems.study')

    def test_official_curriculum_attachments_linked_on_data_load(self):
        """The official curricula ship in data/cat/attachments/ and are attached to each study
        by data/cat/ems.study.csv, whose reload (noupdate=False) links them."""
        attachments = self.env.ref('ems.study_cfgs_icb0_dam_2024').attachment_ids
        self.assertTrue(attachments)
        self.assertTrue(all(attachments.mapped('res_id')))

    def test_removed_attachment_is_deleted(self):
        """Removing a file from a study deletes it: the form's upload widget has no list of
        existing files to pick from, so a detached file could never be reattached."""
        self.test_study.write({'attachment_ids': [self._attachment_command('curriculum.pdf')]})
        attachment = self.test_study.attachment_ids

        self.test_study.write({'attachment_ids': [(3, attachment.id)]})
        self.assertFalse(attachment.exists())

    def test_removed_attachment_still_used_by_another_study_is_kept(self):
        self.test_study.write({'attachment_ids': [self._attachment_command('shared.pdf')]})
        attachment = self.test_study.attachment_ids
        other = self.env['ems.study'].create({
            'code': 'T14', 'acronym': 'T14A', 'name': 'Study Sharing A File', 'date': date(2024, 9, 1),
            'attachment_ids': [(4, attachment.id)],
        })

        self.test_study.write({'attachment_ids': [(3, attachment.id)]})
        self.assertTrue(attachment.exists())
        self.assertEqual(other.attachment_ids, attachment)
