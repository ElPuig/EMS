# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


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

    def test_archived_records_leave_searches_and_selectors(self):
        self.subject.action_archive()
        self.assertFalse(self.env['ems.subject'].search([('id', '=', self.subject.id)]))
        self.assertNotIn(self.subject, self.study.subject_ids)
        self.subject.action_unarchive()
        self.assertIn(self.subject, self.study.subject_ids)

    def test_a_past_course_planning_is_found_once_archived(self):
        # External records and grade corrections read the planning of the course they belong to,
        # which may have been archived since.
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.course.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome.id, 'ponderation': 100})]})
        planning.action_archive()
        wizard = self.env['ems.external_record_wizard'].new({'study_id': self.study.id})
        self.assertEqual(wizard._planning(self.subject, self.course), planning)
