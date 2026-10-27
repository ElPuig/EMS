# -*- coding: utf-8 -*-
"""Regenerates the screenshots of the academic-history manuals (secretariat / Head of Studies).

Same contract as tests/test_docs_screenshots.py - read its module docstring first: '-standard'
keeps it out of every normal run, the fixtures live in a rolled-back transaction so the shots
show invented people only, and the PNGs land in /tmp/ems_doc_screenshots to be copied into
docs/assets/secretary/ by hand. Run it with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable \
        --test-tags='*/ems:TestDocsScreenshotsAcademicHistory' --stop-after-init -c /etc/odoo/odoo.conf"
"""
import base64

from odoo.tests.common import Form, HttpCase, tagged

from .common import DocsScreenshotMixin, build_academic_record_pdf, build_previous_curriculum_pdf, \
    create_level_study, mock_outgoing_email, create_level_study_group, create_role_employee, create_role_user, \
    next_student_id


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


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsPreviousRecord(DocsScreenshotMixin, HttpCase):
    """The "Add a previous record" wizard (issue #585): the review grid read from an Esfera
    academic record PDF, and the record it creates. The certificate is an invented one - a real
    one carries a real student's name, document number and signatures."""
    allow_end_on_form = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_previous_secretary',
                                         lang='ca_ES', name='Secretaria',
                                         email='secretaria.anterior@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')
        Course = cls.env['ems.course']
        cls.course = Course.search([('start', '=', 2024)], limit=1) \
            or Course.create({'start': 2024, 'end': 2025})
        # The record is a course already over: the current course must come after it.
        if (cls.env.company.current_course_id.start or 0) <= 2024:
            cls.env.company.current_course_id = Course.search([('start', '=', 2025)], limit=1) \
                or Course.create({'start': 2025, 'end': 2026})
        # The study's code ends with the certificate's token ("CFPM DOCP" -> CFGM_DOCP).
        cls.level, cls.study = create_level_study(
            cls, 'DOCP', level={'name': 'Cicles Formatius (Grau Mitjà)'},
            study={'code': 'CFGM_DOCP', 'acronym': 'SMX', 'date': '2024-01-01',
                   'name': 'Sistemes microinformàtics i xarxes'})
        cls._module('D0156', 'MP 0156', 'Anglès professional', 100.0,
                    [('RA1', 'Comprèn informació oral', 40.0),
                     ('RA2', 'Comprèn textos escrits', 30.0),
                     ('RA3', 'Redacta textos senzills', 30.0)])
        cls._module('D0221', 'MP 0221', "Muntatge i manteniment d'equips", 90.0,
                    [('RA1', 'Selecciona els components', 50.0),
                     ('RA2', 'Acobla un equip', 50.0)])
        cls.env['ems.subject'].create({
            'code': 'OPTDOCP', 'acronym': 'MP OPT', 'name': 'Pensament computacional',
            'internal_hours': 99, 'study_ids': [(4, cls.study.id)]})
        cls.student = cls.env['res.partner'].create({
            'name': 'Pau Ferrer Roig', 'contact_type': 'student',
            'student_id': next_student_id()})
        pdf = build_academic_record_pdf(cls.student.student_id, 'DOCP', [(
            '08999999', "Institut de l'Exemple", '2024/2025', [
                ('D0156_DOCP', 'Anglès professional', 'MP', '8', 66),
                ('D0156_DOCP_01RA', 'Comprensió oral', 'RA', 'Assolit-8'),
                ('D0156_DOCP_02RA', 'Comprensió escrita', 'RA', 'Assolit-6'),
                ('D0156_DOCP_03RA', 'Redacció', 'RA', 'Assolit-7'),
                ('D0221_DOCP', "Muntatge i manteniment d'equips", 'MP', 'Pendent de qualificar', 231),
                ('D0221_DOCP_01EM', "Estada a l'empresa", 'EM', 'Pendent'),
                ('D0221_DOCP_01RA', 'Components', 'RA', 'Assolit-6'),
                ('D0221_DOCP_02RA', 'Acoblament', 'RA', 'Assolit-5'),
                ('M_OP_01', 'Introducció a la programació', 'MP_', '8', 66),
                ('M_OP_02', 'Programació de videojocs', 'MP_', '6', 33),
            ])], student_name='Ferrer Roig , Pau')
        cls.certificate = pdf
        attachment = cls.env['ir.attachment'].create({
            'name': 'expedient.pdf', 'datas': base64.b64encode(pdf), 'public': True,
            'mimetype': 'application/pdf'})
        cls.env['ir.model.data'].create({
            'module': 'ems', 'name': 'doc_shot_previous_record_certificate',
            'model': 'ir.attachment', 'res_id': attachment.id})

    @classmethod
    def _module(cls, code, acronym, name, internal_weight, outcomes):
        subject = cls.env['ems.subject'].create({
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(4, cls.study.id)]})
        records = cls.env['ems.outcome'].create([{
            'code': f'{code}_0{index}RA', 'acronym': acronym_ra, 'name': outcome_name,
            'subject_id': subject.id,
        } for index, (acronym_ra, outcome_name, _weight) in enumerate(outcomes, start=1)])
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': subject.id, 'course_id': cls.course.id,
            'internal_ponderation': internal_weight, 'external_ponderation': 100.0 - internal_weight,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id, 'ponderation': weight})
                                     for outcome, (_acronym, _name, weight) in zip(records, outcomes)],
        })

    def test_capture_previous_record_screenshots(self):
        self._capture(
            f'/odoo/action-ems.action_student_kanban/{self.student.id}', '.modal-content',
            'academic-history-previous-record-review.png',
            login='doc_shot_previous_secretary', tour='ems_doc_shot_previous_record', padding=0,
        )
        # The record the review grid creates, as the secretariat would.
        form = Form(self.env['ems.external_record_wizard'].with_user(self.secretary)
                    .with_context(default_student_id=self.student.id),
                    view='ems.view_external_record_wizard_form')
        form.certificate_file = base64.b64encode(self.certificate)
        form.save().action_create()
        record = self.student.year_record_ids
        self._capture(
            f'/odoo/action-ems.action_year_record_list/{record.id}', '.o_form_sheet',
            'academic-history-previous-record.png', login='doc_shot_previous_secretary',
            wait_for=".o_form_sheet div[name='subject_record_ids'] .o_data_row",
        )


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsPreviousCurriculum(DocsScreenshotMixin, HttpCase):
    """The previous curriculum import (issue #672): its review grid, and the record it creates.
    The academic history is an invented one - a real one carries a real student's name, document
    number and signatures."""
    allow_end_on_form = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_curriculum_secretary',
                                         lang='ca_ES', name='Secretaria',
                                         email='secretaria.curriculum@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')
        cls.student = cls.env['res.partner'].create({
            'name': 'Laia Puig Serra', 'contact_type': 'alumni', 'student_id': next_student_id()})
        cls.document = build_previous_curriculum_pdf(cls.student.student_id, [
            ('001', 'MP1. Sistemes informàtics', 198, '6', 'Ord.', [
                ('00101', 'UF1. Instal·lació, configuració i|explotació del sistema informàtic', 71, '7', '1'),
                ('00102', 'UF2. Gestió de la informació i de|recursos en una xarxa', 91, '5', '2'),
                ('00103', 'UF3. Implantació de programari|específic', 36, '6', '1'),
            ]),
            ('002', 'MP2. Bases de dades', 231, '7', 'Ord.', [
                ('00201', 'UF1. Introducció a les bases de|dades', 55, '7', '1'),
                ('00202', 'UF2. Llenguatges SQL: DML i DDL', 77, '8', '1'),
                ('00203', 'UF3. Llenguatge SQL: DCL i|extensió procedimental', 66, '5', '1'),
                ('00204', 'UF4. Bases de dades objecte-|relacionals', 33, '6', '1'),
            ]),
            ('003', 'MP3. Programació', 0, '', '', [
                ('00301', 'UF1. Programació estructurada', 85, '5', '1'),
                ('00302', 'UF2. Disseny modular', 50, 'NP', ''),
            ]),
            ('014', 'MP14. Formació en centres de|treball', 317, 'Ap', 'Ord.', [
                ('01401', 'Formació en centres de treball', 317, 'Ap', '1'),
            ]),
        ], student_name='Puig Serra, Laia', centre=('08999999', "Institut de l'Exemple"),
            curriculum=('CFPS ICX0', "CFPS Desenvolupament d'aplicacions inventades (LOE)"),
            years='De 2019 a 2021')
        attachment = cls.env['ir.attachment'].create({
            'name': 'historial.pdf', 'datas': base64.b64encode(cls.document), 'public': True,
            'mimetype': 'application/pdf'})
        cls.env['ir.model.data'].create({
            'module': 'ems', 'name': 'doc_shot_previous_curriculum_document',
            'model': 'ir.attachment', 'res_id': attachment.id})

    def test_capture_previous_curriculum_screenshots(self):
        self._capture(
            f'/odoo/action-ems.action_student_kanban/{self.student.id}', '.modal-content',
            'academic-history-previous-curriculum-review.png',
            login='doc_shot_curriculum_secretary', tour='ems_doc_shot_previous_curriculum', padding=0,
        )
        form = Form(self.env['ems.previous_curriculum_wizard'].with_user(self.secretary)
                    .with_context(default_student_id=self.student.id))
        form.certificate_file = base64.b64encode(self.document)
        form.save().action_create()
        record = self.student.previous_curriculum_record_ids
        self._capture(
            f'/odoo/action-ems.action_previous_curriculum_record_list/{record.id}', '.o_form_sheet',
            'academic-history-previous-curriculum.png', login='doc_shot_curriculum_secretary',
            wait_for=".o_form_sheet div[name='line_ids'] .o_data_row",
        )


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsTitles(DocsScreenshotMixin, HttpCase):
    """Registering titles (issue #635): the import preview, the student form's Actions entry and
    its wizard. Invented students; the import file is built by the doc-shot tour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_titles_secretary',
                                         lang='ca_ES', name='Secretaria',
                                         email='secretaria.titols@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')
        Course = cls.env['ems.course']
        cls.course = Course.search([('start', '=', 2024)], limit=1) \
            or Course.create({'start': 2024, 'end': 2025})
        # The titles belong to the course before the current one, the wizard's default.
        current = Course.search([('start', '=', 2025)], limit=1) \
            or Course.create({'start': 2025, 'end': 2026})
        cls.env.company.current_course_id = current
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'DOCT', level={'name': 'Batxillerat'},
            study={'code': 'DOCTBTX', 'acronym': 'BTX', 'name': 'Batxillerat'},
            group={'acronym': 'A', 'course': 1})
        # Arnau left without a group, Clara is still studying, Biel was withdrawn, Núria's only
        # request was cancelled; the fifth identifier of the file is nobody in EMS.
        cls.arnau = cls._student('TESTDOC635001', 'Arnau Puig Casals')
        cls._student('TESTDOC635002', 'Clara Vidal Font', main_group_id=cls.group.id)
        cls._student('TESTDOC635003', 'Biel Roca Serra', contact_type='withdrawal', active=False)
        cls._student('TESTDOC635004', 'Núria Pons Mas')

    @classmethod
    def _student(cls, student_id, name, **vals):
        student = cls.env['res.partner'].create(dict({
            'name': name, 'contact_type': 'student', 'student_id': student_id}, **vals))
        cls.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': cls.course.id, 'study_id': cls.study.id,
            'study_name': cls.study.display_name, 'group_name': 'BTX2A'})
        return student

    def test_capture_title_screenshots(self):
        self._capture(
            '/odoo/action-ems.action_title_import_wizard', '.modal-content', 'titols-01-importar.png',
            login='doc_shot_titles_secretary', tour='ems_doc_shot_title_import', padding=0,
        )
        student_url = f'/odoo/action-ems.action_student_kanban/{self.arnau.id}'
        # The form's Actions dropdown is an overlay outside the form, hence the body;
        # beyond_viewport=False because the dropdown closes when Chrome resizes the page.
        self._capture(
            student_url, 'body', 'titols-02-accions.png',
            login='doc_shot_titles_secretary',
            wait_for='.o_form_statusbar .o_ems_actions_toggle',
            click='.o_form_statusbar .o_ems_actions_toggle',
            wait_after=".o_ems_actions_menu button[name='action_title_register_wizard']",
            max_height=420, beyond_viewport=False,
        )
        self._capture(
            student_url, '.modal-content', 'titols-03-registrar.png',
            login='doc_shot_titles_secretary',
            wait_for='.o_form_statusbar .o_ems_actions_toggle',
            click=['.o_form_statusbar .o_ems_actions_toggle',
                   ".o_ems_actions_menu button[name='action_title_register_wizard']"],
            wait_after=['.o_ems_actions_menu', '.modal-content .alert-warning'],
            padding=0,
        )
