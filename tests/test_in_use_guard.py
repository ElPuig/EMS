# -*- coding: utf-8 -*-
from datetime import date
from types import SimpleNamespace

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_role_user


class TestInUseGuard(TransactionCase):
    """Issue #868 (part of #52): the academic catalog is archived, never deleted, once in use;
    a record nobody points at yet (e.g. created by mistake) can still be deleted."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level = cls.env['ems.level'].create({'acronym': 'TIUG', 'name': 'In-use guard level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TIUG01', 'acronym': 'TIUGS', 'name': 'In-use guard study',
            'date': date(2020, 1, 1), 'level_id': cls.level.id})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TIUG01', 'acronym': 'TIUGM', 'name': 'In-use guard subject',
            'study_ids': [(6, 0, cls.study.ids)]})
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'TIUG01_RA1', 'acronym': 'RA1', 'name': 'Outcome', 'subject_id': cls.subject.id})
        cls.course = cls.env['ems.course'].create({'start': 2091, 'end': 2092})

    def test_unused_records_can_be_deleted(self):
        space_type = self.env['ems.space_type'].create({'name': 'Unused type'})
        level = self.env['ems.level'].create({'acronym': 'TIUX', 'name': 'Unused level'})
        workgroup = self.env['ems.workgroup'].create({'name': 'Unused workgroup'})
        for record in (space_type, level, workgroup):
            record.unlink()
            self.assertFalse(record.exists())

    def test_a_record_in_use_cannot_be_deleted_and_names_who_uses_it(self):
        with self.assertRaises(UserError) as error:
            self.level.unlink()
        self.assertIn('Archive it instead', str(error.exception))
        self.assertIn(self.env['ir.model']._get('ems.study').name.split(':')[0], str(error.exception))
        self.assertTrue(self.level.exists())
        with self.assertRaises(UserError) as error:
            self.level.with_context(lang='ca_ES').unlink()
        self.assertIn("Arxiva el registre en lloc d'eliminar-lo", str(error.exception))

    def test_superuser_is_refused_too(self):
        # A subject cascades to its enrolments and teaching assignments: never deleted while in use,
        # not even by code running as superuser.
        with self.assertRaises(UserError):
            self.subject.sudo().unlink()

    def test_an_archived_referencing_record_still_counts(self):
        self.study.action_archive()
        with self.assertRaises(UserError):
            self.level.unlink()

    def test_a_course_is_guarded_without_being_archivable(self):
        self.assertNotIn('active', self.env['ems.course']._fields)
        self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.course.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome.id, 'ponderation': 100})]})
        with self.assertRaises(UserError):
            self.course.unlink()
        with self.assertRaises(UserError):
            self.outcome.unlink()  # used by the planning's weight line
        unused = self.env['ems.course'].create({'start': 2093, 'end': 2094})
        unused.unlink()
        self.assertFalse(unused.exists())

    def test_outcomes_contents_and_criteria_are_guarded_without_being_archivable(self):
        # They only make sense inside their subject: a typo is fixed in place, a new curriculum
        # archives the whole study and its subjects.
        for model in ('ems.outcome', 'ems.content', 'ems.criteria'):
            self.assertNotIn('active', self.env[model]._fields)
        unused = self.env['ems.outcome'].create({
            'code': 'TIUG01_RA2', 'acronym': 'RA2', 'name': 'Unused', 'subject_id': self.subject.id})
        unused.unlink()
        self.assertFalse(unused.exists())
        self.env['ems.criteria'].create({
            'code': 'TIUG01_RA1_CA1', 'acronym': 'CA1', 'name': 'Criterion', 'outcome_id': self.outcome.id})
        with self.assertRaises(UserError) as error:
            self.outcome.unlink()
        self.assertNotIn('Archive it instead', str(error.exception))

    def test_own_lines_and_records_deleted_together_are_no_use(self):
        # A planning nobody graded with yet is deleted with its weight lines.
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.course.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome.id, 'ponderation': 100})]})
        planning.unlink()
        self.assertFalse(planning.exists())
        # A content deleted together with its composite child.
        parent = self.env['ems.content'].create({
            'code': 'TIUG01_C1', 'acronym': 'C1', 'name': 'Parent', 'subject_id': self.subject.id})
        child = self.env['ems.content'].create({
            'code': 'TIUG01_C1A', 'acronym': 'C1A', 'name': 'Child', 'content_id': parent.id})
        with self.assertRaises(UserError):
            parent.unlink()
        (parent | child).unlink()
        self.assertFalse((parent | child).exists())

    def test_archive_is_only_offered_to_who_can_write(self):
        # The web client offers Archive whenever `active` isn't readonly, without checking the
        # user's write access: a role that only reads (a teacher on subjects, spaces or plannings)
        # would get the entry and then an error.
        teacher = create_role_user(self, 'teacher', 'tiug_teacher')
        hos = create_role_user(self, 'head_of_studies', 'tiug_hos')
        admin = create_role_user(self, 'academic_admin', 'tiug_admin')
        for model in ('ems.level', 'ems.study', 'ems.subject', 'ems.planning', 'ems.space',
                      'ems.space_type', 'ems.role', 'ems.workgroup'):
            self.assertTrue(self.env[model].with_user(teacher).fields_get(['active'])['active']['readonly'], model)
            self.assertFalse(self.env[model].with_user(admin).fields_get(['active'])['active']['readonly'], model)
        # Heads of Studies edit plannings, so they may archive them, but not subjects.
        self.assertFalse(self.env['ems.planning'].with_user(hos).fields_get(['active'])['active']['readonly'])
        self.assertTrue(self.env['ems.subject'].with_user(hos).fields_get(['active'])['active']['readonly'])

    def test_archived_records_leave_searches_and_selectors(self):
        self.subject.action_archive()
        self.assertFalse(self.env['ems.subject'].search([('id', '=', self.subject.id)]))
        self.assertNotIn(self.subject, self.study.subject_ids)
        self.subject.action_unarchive()
        self.assertIn(self.subject, self.study.subject_ids)

    def test_a_convalidated_subject_reads_its_archived_planning(self):
        # The academic record of a convalidated subject reads the study's plan weights, which may
        # have been archived since (the other past-course lookups are tested in their own areas).
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.course.id,
            'internal_ponderation': 70.0, 'external_ponderation': 30.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome.id, 'ponderation': 100})]})
        planning.action_archive()
        line = SimpleNamespace(subject_id=self.subject, convalidation_id=SimpleNamespace(name=False),
                               _ems_resolved_grade=lambda: 5)
        vals = self.env['ems.student.year_record.subject']._convalidated_vals(line, self.study)
        self.assertEqual((vals['internal_weight'], vals['external_weight']), (70.0, 30.0))
