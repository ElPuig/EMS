# -*- coding: utf-8 -*-
"""Regenerates the screenshots of the academic-history manuals (secretariat / Head of Studies).

Same contract as tests/test_docs_screenshots.py - read its module docstring first: '-standard'
keeps it out of every normal run, the fixtures live in a rolled-back transaction so the shots
show invented people only, and the PNGs land in /tmp/ems_doc_screenshots to be copied into
docs/assets/secretary/ by hand. Run it with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable \
        --test-tags='*/ems:TestDocsScreenshotsAcademicHistory' --stop-after-init -c /etc/odoo/odoo.conf"
"""
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_level_study_group, \
    create_role_employee, create_role_user, next_student_id


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsAcademicHistory(DocsScreenshotMixin, HttpCase):
    # The grade review shot is taken on a filled-in, unsaved wizard - that is the state being
    # photographed (same switch as TestDocsScreenshots).
    allow_end_on_form = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Catalan, like every other manual screenshot of this centre.
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_history_secretary',
                                         lang='ca_ES', name='Secretaria',
                                         email='secretaria.historic@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')

        # A real past course, so the shot reads like the case this exists for: a file closed
        # last year, reviewed now. Reused when the database already has it.
        Course = cls.env['ems.course']
        cls.course = Course.search([('start', '=', 2024)], limit=1) \
            or Course.create({'start': 2024, 'end': 2025})
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'DOCH',
            level={'name': 'Cicles Formatius (Grau Mitjà)'},
            # The study's own year is part of its name on screen, so it matches the course.
            study={'code': 'DOCHSMX', 'acronym': 'SMX', 'date': '2024-01-01',
                   'name': 'Sistemes microinformàtics i xarxes'},
        )
        # Invented student and modules - nothing from this box's real data.
        cls.student = cls.env['res.partner'].create({
            'name': 'Mireia Solà Ventura', 'contact_type': 'student',
            'student_id': next_student_id()})
        cls.year_record = cls.env['ems.student.year_record'].create({
            'student_id': cls.student.id, 'course_id': cls.course.id,
            'study_id': cls.study.id, 'study_name': cls.study.display_name,
            # The denormalised names are what the screen shows, so they carry the realistic
            # wording rather than the fixture's own collision-proof codes.
            'level_name': 'CFGM: Cicles Formatius (Grau Mitjà)', 'group_name': 'SMX1C',
            'tutor_name': 'Laia Prats Coll', 'shift': 'afternoon',
            'attendance_rate': 96.5, 'academic_result': 'partial',
            'subject_record_ids': [
                (0, 0, cls._subject_vals('MP 0156: Anglès professional', 'failed', 4,
                                         [('RA1: Comprèn informació oral', 40.0, 6),
                                          ('RA2: Comprèn textos escrits', 30.0, 4),
                                          ('RA3: Redacta textos senzills', 30.0, 4)])),
                (0, 0, cls._subject_vals('MP 0221: Muntatge i manteniment d\'equips', 'passed', 7,
                                         [('RA1: Munta equips microinformàtics', 100.0, 7)])),
                (0, 0, cls._subject_vals('MP 0225: Xarxes locals', 'passed', 6,
                                         [('RA1: Instal·la xarxes locals', 100.0, 6)])),
            ]})

    @classmethod
    def _subject_vals(cls, name, state, grade, outcomes):
        return {
            'subject_name': name, 'state': state,
            'internal_weight': 100.0, 'external_weight': 0.0,
            'internal_grade': grade, 'final_grade': grade, 'has_final': True,
            'outcome_record_ids': [
                (0, 0, {'outcome_name': outcome, 'weight': weight,
                        'final_score': score, 'final_is_scored': True})
                for outcome, weight, score in outcomes],
        }

    def test_capture_academic_history_screenshots(self):
        record_url = '/odoo/action-ems.action_year_record_list/%d' % self.year_record.id
        self._capture(
            record_url, '.o_form_sheet', 'academic-history-record.png',
            login='doc_shot_history_secretary',
            wait_for=".o_form_sheet div[name='subject_record_ids'] .o_data_row",
        )
        self._capture(
            record_url, '.modal-content', 'academic-history-grade-review.png',
            login='doc_shot_history_secretary',
            tour='ems_doc_shot_grade_review',
            # No padding: the dialog's own edges are the crop, or the shot bleeds a sliver of
            # the page behind it in through the backdrop.
            padding=0,
        )
