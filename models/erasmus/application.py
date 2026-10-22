# -*- coding: utf-8 -*-

import base64
import io
from datetime import timedelta

import xlsxwriter

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

CHECK_STATES = [('pending', "Pending"), ('met', "Met"), ('not_met', "Not met")]
YES_NO = [('yes', "Yes"), ('no', "No")]
# Criterion C (art. 12): the highest language certificate.
LANGUAGE_SCORES = {'none': 0.0, 'b1': 2.5, 'b2': 5.0, 'c1': 7.5, 'c2': 10.0}
# What a Head of Studies who is not in the Erasmus team may write: the check reserved to them.
SANCTION_FIELDS = {'sanction_check', 'sanction_check_note'}
# Values set by hand that keep who set them and when (<field>_user_id, <field>_date).
STAMPED_FIELDS = ('requirements_check', 'sanction_check', 'language_level', 'fewer_opportunities_check',
                  'first_mobility')
# Application states whose data is frozen when the call closes.
SUBMITTED_STATES = ('submitted', 'subsanation', 'admitted', 'excluded')
# Application states that compete in the ranking (issue #685): admitted, and the results after it.
RANKED_STATES = ('admitted', 'selected', 'reserve', 'not_selected', 'accepted', 'renounced')
# The criteria and total a resolution freezes on its lines.
SCORE_FIELDS = ('score_a', 'score_b', 'score_c', 'score_d', 'score_e', 'score_f', 'score_total')
# Issue #685: "Export to spreadsheet". An external tool imports the file as is, so the sheet name and
# the headers are fixed, in Spanish, in this order, and are never translated.
PARTICIPANT_SHEET = 'Participantes'
PARTICIPANT_HEADERS = ('Nombre', 'Apellidos', 'DNI', 'Email', 'Teléfono', 'Dirección', 'Fecha de nacimiento',
                       'Nacionalidad', 'Género', 'Ciclo formativo', 'Curso', 'Titular de la cuenta', 'Banco', 'BIC',
                       'IBAN', 'Tutor legal', 'Email del tutor legal', 'Teléfono del tutor legal')
# Answers of the portal form, editable by the applicant while the call accepts applications.
ANSWER_FIELDS = ('previous_mobility', 'previous_mobility_details', 'availability', 'fewer_opportunities',
                 'image_consent', 'applicant_notes')


class EmsErasmusApplication(models.Model):
    """Issue #683 - a student's application to an Erasmus+ call. Filed from the portal
    (controllers/portal_erasmus.py, with sudo), reviewed by the Erasmus team. The state only moves
    through the actions below. See docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.application'
    _description = 'Erasmus+ application'
    _inherit = ['ems.base']
    _order = 'submit_date desc, id desc'
    _sql_constraints = [
        ('call_partner_unique', 'unique(call_id, partner_id)', "A person can only apply once to each call."),
    ]

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='restrict',
                              index=True)
    partner_id = fields.Many2one(string="Applicant", comodel_name='res.partner', required=True, ondelete='restrict',
                                 index=True)
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality', ondelete='restrict',
                                  domain="[('call_id', '=', call_id)]", tracking=True)
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False, index=True,
                             selection=[
                                 ('draft', "Draft"), ('submitted', "Submitted"), ('subsanation', "Corrections requested"),
                                 ('admitted', "Admitted"), ('excluded', "Excluded"), ('not_submitted', "Not submitted"),
                                 ('selected', "Selected"), ('reserve', "Reserve"), ('not_selected', "Not selected"),
                                 ('accepted', "Place accepted"), ('renounced', "Renounced"),
                             ])
    submit_date = fields.Datetime(string="Submitted on", readonly=True, copy=False)
    is_minor = fields.Boolean(string="Minor", compute='_compute_is_minor')

    previous_mobility = fields.Boolean(string="Previous Erasmus+ mobility")
    previous_mobility_details = fields.Text(string="Previous mobility details")
    availability = fields.Text(string="Availability")
    fewer_opportunities = fields.Boolean(string="Declares fewer opportunities")
    image_consent = fields.Boolean(string="Image consent")
    applicant_notes = fields.Text(string="Applicant's notes")

    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='application_id')

    requirements_check = fields.Selection(string="Requirements", selection=CHECK_STATES, default='pending',
                                          required=True, tracking=True, copy=False)
    requirements_check_note = fields.Text(string="Requirements note", copy=False)
    requirements_check_user_id = fields.Many2one(string="Requirements checked by", comodel_name='res.users',
                                                 readonly=True, copy=False)
    requirements_check_date = fields.Datetime(string="Requirements checked on", readonly=True, copy=False)
    sanction_check = fields.Selection(string="No serious sanction", selection=CHECK_STATES, default='pending',
                                      required=True, tracking=True, copy=False)
    sanction_check_note = fields.Text(string="Sanction check note", copy=False)
    sanction_check_user_id = fields.Many2one(string="Sanction checked by", comodel_name='res.users',
                                             readonly=True, copy=False)
    sanction_check_date = fields.Datetime(string="Sanction checked on", readonly=True, copy=False)
    can_check_sanction = fields.Boolean(string="Can check sanctions", compute='_compute_permissions')
    can_manage = fields.Boolean(string="Can manage", compute='_compute_permissions',
                                help="Erasmus team or administrator: everything but the sanction check.")
    exclusion_reason = fields.Text(string="Exclusion reason", tracking=True, copy=False)

    # --- scoring (issue #684, art. 12 of the call) ---
    scoring_frozen_date = fields.Datetime(string="Scoring data frozen on", readonly=True, copy=False,
                                          help="When the call was closed: the record average and the conduct "
                                               "warnings are the ones EMS had then.")
    grade_line_ids = fields.One2many(string="Modules used for the average", comodel_name='ems.erasmus.application.grade',
                                     inverse_name='application_id', readonly=True)
    grade_average_ems = fields.Float(string="Average from EMS", digits=(4, 2), readonly=True, copy=False)
    grade_average_from_ems = fields.Boolean(string="Average from EMS found", readonly=True, copy=False)
    grade_average = fields.Float(string="Record average", digits=(4, 2), compute='_compute_scores', store=True)
    language_level = fields.Selection(string="Language certificate", tracking=True, copy=False, selection=[
        ('none', "None"), ('b1', "B1"), ('b2', "B2"), ('c1', "C1"), ('c2', "C2")],
        help="The highest official foreign-language certificate the applicant uploaded.")
    language_level_user_id = fields.Many2one(string="Language checked by", comodel_name='res.users',
                                             readonly=True, copy=False)
    language_level_date = fields.Datetime(string="Language checked on", readonly=True, copy=False)
    fewer_opportunities_check = fields.Selection(
        string="Fewer opportunities accredited", selection=YES_NO, tracking=True, copy=False,
        groups='ems.group_erasmus,ems.group_academic_admin')
    fewer_opportunities_check_user_id = fields.Many2one(
        string="Fewer opportunities checked by", comodel_name='res.users', readonly=True, copy=False,
        groups='ems.group_erasmus,ems.group_academic_admin')
    fewer_opportunities_check_date = fields.Datetime(
        string="Fewer opportunities checked on", readonly=True, copy=False,
        groups='ems.group_erasmus,ems.group_academic_admin')
    first_mobility = fields.Selection(string="First mobility", selection=YES_NO, tracking=True, copy=False,
                                      help="GM: no previous Erasmus+ mobility. GS: no previous higher-education one.")
    first_mobility_user_id = fields.Many2one(string="First mobility checked by", comodel_name='res.users',
                                             readonly=True, copy=False)
    first_mobility_date = fields.Datetime(string="First mobility checked on", readonly=True, copy=False)
    strike_ids = fields.Many2many(string="Conduct warnings", comodel_name='ems.strike',
                                  relation='ems_erasmus_application_strike_rel', readonly=True, copy=False)
    strike_count = fields.Integer(string="Number of conduct warnings", readonly=True, copy=False)

    interview_ids = fields.One2many(string="Interviews", comodel_name='ems.erasmus.interview',
                                    inverse_name='application_id', groups='ems.group_erasmus,ems.group_academic_admin')
    interview_date = fields.Datetime(string="Interview date", tracking=True, copy=False)
    interview_place = fields.Char(string="Interview place", tracking=True, copy=False)
    interview_call_date = fields.Datetime(string="Interview call sent on", readonly=True, copy=False)
    single_interview_reason = fields.Text(string="Reason for a single evaluation", tracking=True, copy=False,
                                          help="Only one evaluator could score the interview (annex 4).")
    interview_general = fields.Float(string="Interview, general part", digits=(4, 2),
                                     compute='_compute_interview', store=True)
    interview_english = fields.Float(string="Interview, English part", digits=(4, 2),
                                     compute='_compute_interview', store=True)
    interview_complete = fields.Boolean(string="Interview scored", compute='_compute_interview', store=True)

    score_a = fields.Float(string="A. Record", digits=(5, 2), compute='_compute_scores', store=True)
    score_a_pending = fields.Boolean(string="Record average pending", compute='_compute_scores', store=True)
    score_b = fields.Float(string="B. Interview", digits=(5, 2), compute='_compute_scores', store=True)
    score_c = fields.Float(string="C. Languages", digits=(5, 2), compute='_compute_scores', store=True)
    score_d = fields.Float(string="D. Fewer opportunities", digits=(5, 2), compute='_compute_scores', store=True,
                           groups='ems.group_erasmus,ems.group_academic_admin')
    score_e = fields.Float(string="E. First mobility", digits=(5, 2), compute='_compute_scores', store=True)
    score_f = fields.Float(string="F. Conduct", digits=(5, 2), compute='_compute_scores', store=True)
    score_total = fields.Float(string="Total score", digits=(5, 2), compute='_compute_scores', store=True)
    score_complete = fields.Boolean(string="Score complete", compute='_compute_scores', store=True,
                                    help="Every criterion is in: a pending one never counts as zero.")
    is_eligible = fields.Boolean(string="Eligible", compute='_compute_scores', store=True,
                                 help="Complete score, at least the call's minimum.")
    draw_order = fields.Integer(string="Draw", tracking=True, copy=False,
                                help="Result of the draw between applications tied after every tie-break "
                                     "(lower goes first).")
    rank = fields.Integer(string="Rank", compute='_compute_rank', store=True,
                          help="Position in the modality among the admitted applications. 0 until every one "
                               "of them has a complete score.")
    needs_draw = fields.Boolean(string="Needs a draw", compute='_compute_rank', store=True)

    # --- resolutions, claims and offers (issue #685) ---
    resolution_line_ids = fields.One2many(string="Resolutions", comodel_name='ems.erasmus.resolution.line',
                                          inverse_name='application_id', readonly=True)
    offer_ids = fields.One2many(string="Place offers", comodel_name='ems.erasmus.offer',
                                inverse_name='application_id', readonly=True)
    claim_ids = fields.One2many(string="Claims", comodel_name='ems.erasmus.claim', inverse_name='application_id')

    @api.depends('partner_id.birth_date')
    def _compute_is_minor(self):
        for application in self:
            application.is_minor = not application.partner_id.is_adult

    @api.depends_context('uid')
    def _compute_permissions(self):
        can_check_sanction = self._ems_can_check_sanction()
        can_manage = self._ems_can_manage()
        for application in self:
            application.can_check_sanction = can_check_sanction
            application.can_manage = can_manage

    @api.depends('interview_ids.state', 'interview_ids.general_score', 'interview_ids.english_score',
                 'single_interview_reason')
    def _compute_interview(self):
        """Mean of the submitted interviews; complete with two of them, or one and a reason."""
        for application in self:
            interviews = application.interview_ids
            submitted = interviews.filtered(lambda interview: interview.state == 'submitted')
            count = len(submitted)
            application.interview_complete = bool(submitted) and count == len(interviews) and (
                count >= 2 or bool(application.single_interview_reason))
            application.interview_general = sum(submitted.mapped('general_score')) / count if count else 0.0
            application.interview_english = sum(submitted.mapped('english_score')) / count if count else 0.0

    @api.depends('grade_average_ems', 'grade_average_from_ems', 'scoring_frozen_date',
                 'interview_general', 'interview_english', 'interview_complete', 'language_level',
                 'fewer_opportunities_check', 'first_mobility', 'strike_count', 'call_id.min_score')
    def _compute_scores(self):
        """Art. 12: A + B + C + D + E + F, no floor at zero. A pending criterion leaves it incomplete."""
        for application in self:
            average = application.grade_average_ems
            application.grade_average = average
            application.score_a_pending = not (application.scoring_frozen_date and application.grade_average_from_ems)
            application.score_a = average * 4
            application.score_b = application.interview_general + application.interview_english
            application.score_c = LANGUAGE_SCORES.get(application.language_level, 0.0)
            application.score_d = 10.0 if application.fewer_opportunities_check == 'yes' else 0.0
            application.score_e = 5.0 if application.first_mobility == 'yes' else 0.0
            application.score_f = -min(3 * application.strike_count, 9)
            application.score_total = sum(application[f'score_{criterion}'] for criterion in 'abcdef')
            application.score_complete = not application.score_a_pending and application.interview_complete and all(
                application[name] for name in ('language_level', 'fewer_opportunities_check', 'first_mobility'))
            application.is_eligible = application.score_complete and \
                application.score_total >= application.call_id.min_score

    @api.depends('state', 'modality_id', 'score_total', 'score_complete', 'score_d', 'score_e',
                 'interview_english', 'grade_average', 'draw_order',
                 'call_id.application_ids.state', 'call_id.application_ids.modality_id',
                 'call_id.application_ids.score_total', 'call_id.application_ids.score_complete',
                 'call_id.application_ids.score_d', 'call_id.application_ids.score_e',
                 'call_id.application_ids.interview_english', 'call_id.application_ids.grade_average',
                 'call_id.application_ids.draw_order')
    def _compute_rank(self):
        """Rank among the admitted applications (and their results) of the same modality, by total and art. 12's
        tie-breaks, then the draw. Only once every one of them has a complete score."""
        self.rank = 0
        self.needs_draw = False
        for (call, modality), applications in self.grouped(lambda application: (
                application.call_id, application.modality_id)).items():
            ranked = call.application_ids.filtered(
                lambda application: application.state in RANKED_STATES and application.modality_id == modality)
            if not ranked or not all(ranked.mapped('score_complete')):
                continue
            keys = {application: (-application.score_total, -application.score_d, -application.score_e,
                                  -application.interview_english, -application.grade_average,
                                  application.draw_order)
                    for application in ranked}
            ordered = sorted(keys.values())
            for application in applications & ranked:
                application.rank = ordered.index(keys[application]) + 1
                application.needs_draw = ordered.count(keys[application]) > 1

    def _compute_display_name(self):
        for application in self:
            application.display_name = f"{application.partner_id.name} - {application.call_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        """One document line per document the call asks for."""
        Call = self.env['ems.erasmus.call']
        for vals in vals_list:
            if vals.get('call_id') and 'document_ids' not in vals:
                vals['document_ids'] = [(0, 0, {'call_document_id': document.id})
                                        for document in Call.browse(vals['call_id']).document_ids]
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals and not self.env.context.get('ems_erasmus_state'):
            raise UserError(_("The state of an application only changes through its actions."))
        if not self.env.su:
            touched = set(vals)
            if touched & SANCTION_FIELDS and not self._ems_can_check_sanction():
                raise AccessError(_("Only the Head of Studies or the Director record the serious sanction check."))
            if touched - SANCTION_FIELDS and not self._ems_can_manage():
                raise AccessError(_("Only the Erasmus team changes an application."))
        now = fields.Datetime.now()
        for name in STAMPED_FIELDS:
            if name in vals:
                vals.update({f'{name}_user_id': self.env.uid, f'{name}_date': now})
        return super().write(vals)

    # --- team actions ----------------------------------------------------------------------

    def action_request_subsanation(self):
        """Ask the applicant to correct or complete the documents marked as needing changes or
        missing, and email them the list and the deadline."""
        for application in self:
            application._ems_check_state(('submitted',))
            to_correct = application._ems_documents_to_correct()
            if not to_correct:
                raise UserError(_("Mark which documents need changes before asking for corrections."))
            to_correct.sudo().correction_requested = True
        self._ems_set_state('subsanation')
        self._ems_send('ems.email_template_erasmus_application_subsanation')

    def action_admit(self):
        for application in self:
            application._ems_check_state(('submitted',))
            if application.requirements_check != 'met' or application.sanction_check != 'met':
                raise UserError(_("Both admission checks must be met to admit %s.", application.partner_id.name))
            if application.document_ids.filtered(lambda line: line.is_required and line.review_state != 'valid'):
                raise UserError(_("Every required document of %s must be valid to admit the application.",
                                  application.partner_id.name))
        self._ems_set_state('admitted')

    def action_exclude(self):
        """Also on an admitted application: not attending the interview excludes (art. 11)."""
        for application in self:
            application._ems_check_state(('submitted', 'subsanation', 'admitted'))
            if not (application.exclusion_reason or '').strip():
                raise UserError(_("Write the exclusion reason first."))
        self._ems_set_state('excluded')

    def action_back_to_review(self):
        for application in self:
            application._ems_check_state(('admitted', 'excluded'))
        self._ems_set_state('submitted')

    def action_send_interview_call(self):
        """Email the applicant the interview's date and place, at least 24 hours ahead (art. 11)."""
        limit = self.call_id._ems_now() + timedelta(hours=24)
        for application in self:
            application._ems_check_state(('admitted',))
            if not application.interview_date:
                raise UserError(_("Set the interview date of %s first.", application.partner_id.name))
            if application.interview_date < limit:
                raise UserError(_("The interview call must be sent at least 24 hours before the interview."))
        self._ems_send('ems.email_template_erasmus_interview_call')
        self.sudo().write({'interview_call_date': fields.Datetime.now()})

    def _ems_ranking_result(self):
        """Issue #685: selected within the modality's places, reserve after them, not selected
        below the minimum score."""
        self.ensure_one()
        if not self.is_eligible:
            return 'not_selected'
        return 'selected' if self.rank <= self.modality_id.places else 'reserve'

    def action_export_participants(self):
        """Issue #685: the spreadsheet of the people who accepted a place, served by
        EmsErasmusExportController (it carries personal data: Erasmus team only)."""
        accepted = self._ems_participants()
        return {
            'type': 'ir.actions.act_url',
            'url': f"/ems/erasmus/participants?application_ids={','.join(map(str, accepted.ids))}",
            'target': 'download',
        }

    def _ems_participants(self):
        """The applications in self whose applicant accepted a place, for the Erasmus team only."""
        if not (self.env.su or self.env.user.has_group('ems.group_erasmus')):
            raise AccessError(_("Only the Erasmus team exports the participants."))
        accepted = self.filtered(lambda application: application.state == 'accepted')
        if not accepted:
            raise UserError(_("Nobody has accepted a place yet."))
        return accepted

    def _ems_participants_xlsx(self):
        """The participants as an .xlsx: one row per application, PARTICIPANT_HEADERS' columns."""
        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {'in_memory': True})
        sheet = workbook.add_worksheet(PARTICIPANT_SHEET)
        bold = workbook.add_format({'bold': True})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        sheet.write_row(0, 0, PARTICIPANT_HEADERS, bold)
        for row, application in enumerate(self._ems_participants().sudo().sorted(
                lambda application: application.partner_id.name), start=1):
            values = application._ems_participant_row()
            birth_date = values.pop(6)
            sheet.write_row(row, 0, values[:6])
            if birth_date:
                sheet.write_datetime(row, 6, birth_date, date_format)
            sheet.write_row(row, 7, values[6:])
        sheet.set_column(0, len(PARTICIPANT_HEADERS) - 1, 18)
        workbook.close()
        return stream.getvalue()

    def _ems_participant_row(self):
        """The values of PARTICIPANT_HEADERS for this applicant, the birth date as a datetime.
        The legal guardian columns, only for minors: every family contact, in the same order."""
        self.ensure_one()
        partner = self.partner_id
        group = partner.main_group_id
        bank = partner.bank_ids[:1]
        family = partner._ems_family_contacts() if self.is_minor else self.env['res.partner']
        address = partner._display_address(without_company=True).replace('\n', ', ').strip(', ')
        birth_date = partner.birth_date and fields.Datetime.to_datetime(partner.birth_date)
        return [
            partner.firstname or '', partner.lastname or '', partner.document_id or partner.passport_id or '',
            partner.email or '', partner.phone or partner.mobile or '', address, birth_date,
            partner.citizenship_id.name or '', '', group.study_id.acronym or '', group.course or '',
            bank.acc_holder_name or (bank and partner.name) or '', bank.bank_id.name or '', bank.bank_id.bic or '',
            bank.sanitized_acc_number or '',
            ', '.join(family.mapped('name')), ', '.join(contact.email or '' for contact in family),
            ', '.join(contact.phone or contact.mobile or '' for contact in family),
        ]

    def _ems_freeze_scoring_data(self):
        """Copy the record average (A) and the conduct warnings (F) as EMS has them now: what the
        selection is based on, never recomputed afterwards."""
        Grade = self.env['ems.erasmus.application.grade']
        for application in self.sudo():
            grades = application._ems_grade_values()
            hours = sum(vals['hours'] for vals in grades)
            study = application.partner_id.main_group_id.study_id
            strikes = self.env['ems.strike'].sudo().search([
                ('student_id', '=', application.partner_id.id), ('group_id.study_id', '=', study.id),
                ('date', '<=', application.call_id.date_close)]) if study else self.env['ems.strike']
            application.grade_line_ids.unlink()
            Grade.create([{**vals, 'application_id': application.id} for vals in grades])
            application.write({
                'scoring_frozen_date': fields.Datetime.now(),
                'grade_average_ems': round(sum(vals['grade'] * vals['hours'] for vals in grades) / hours, 2)
                if hours else 0.0,
                'grade_average_from_ems': bool(hours),
                'strike_ids': [(6, 0, strikes.ids)],
                'strike_count': len(strikes),
            })

    def _ems_grade_values(self):
        """The modules of the applicant's current cycle for the record average, as values of
        ems.erasmus.application.grade: one per module, its most recent grade (this course's
        grade lines, then the year records from the latest course). Convalidated and recognised
        modules are left out, and so are modules with nothing evaluated."""
        self.ensure_one()
        partner = self.partner_id
        study = partner.main_group_id.study_id
        if not study:
            return []
        found = {}  # module -> its values, None when it is left out
        lines = self.env['ems.grade_subject_line'].sudo().search([
            ('student_id', '=', partner.id), ('grade_session_id.subject_id.study_ids', 'in', study.ids)])
        course_name = self.call_id.course_id.name or self.env.company.current_course_id.name
        for subject, subject_lines in lines.grouped(lambda line: line.grade_session_id.subject_id).items():
            last = max(subject_lines, key=lambda line: line.grade_session_id.round)
            if last.is_convalidated:
                found[('subject', subject.id)] = None
            elif last.computed_is_scored or last.internal_is_scored:
                grade = last.computed_score if last.computed_is_scored else last.internal_score
                found[('subject', subject.id)] = self._ems_grade_vals(subject, subject.display_name, course_name, grade)
        records = self.env['ems.student.year_record'].sudo().search([
            ('student_id', '=', partner.id), ('study_id', '=', study.id), ('is_provisional', '=', False)])
        for record in records.sorted(lambda record: record.course_id.start, reverse=True):
            for subject_record in record.subject_record_ids:
                key = ('subject', subject_record.subject_id.id) if subject_record.subject_id \
                    else ('name', subject_record.subject_name)
                if key in found:
                    continue
                if subject_record.is_convalidated or subject_record.is_recognized:
                    found[key] = None
                elif subject_record.has_final:
                    grade = subject_record.final_grade
                elif subject_record.is_overridden or subject_record.outcome_record_ids.filtered('final_is_scored'):
                    grade = subject_record.internal_grade
                else:
                    continue
                if key not in found:
                    found[key] = self._ems_grade_vals(subject_record.subject_id, subject_record.subject_name,
                                                      record.course_id.name, grade)
        return [vals for vals in found.values() if vals]

    @api.model
    def _ems_grade_vals(self, subject, subject_name, course_name, grade):
        return {'subject_id': subject.id, 'subject_name': subject_name, 'course_name': course_name,
                'grade': grade, 'hours': subject.total_hours}

    # --- portal ----------------------------------------------------------------------------

    @api.model
    def _ems_portal_get_or_create(self, call, partner):
        """`partner`'s application to `call`, created (as a draft) on the first visit while the
        call accepts applications."""
        application = self.search([('call_id', '=', call.id), ('partner_id', '=', partner.id)])
        if application:
            return application
        modality = call._ems_modality_for(partner)
        if not modality:
            raise UserError(_("You cannot apply to this call."))
        if not call.is_accepting:
            raise UserError(_("This call is not accepting applications."))
        return self.create({'call_id': call.id, 'partner_id': partner.id, 'modality_id': modality.id})

    def _ems_portal_save(self, answers, uploads):
        """Save what the applicant sent from the portal. `answers`: values of ANSWER_FIELDS, only
        while the call accepts applications. `uploads`: {call document id: [(file name, bytes)]},
        also during subsanation, until its deadline, for the documents asked for."""
        self.ensure_one()
        answers = {key: value for key, value in answers.items() if key in ANSWER_FIELDS}
        if answers:
            if not self._ems_portal_editable():
                raise UserError(_("The application can no longer be changed."))
            self.write(answers)
        lines = {line.call_document_id.id: line for line in self.document_ids}
        editable = self._ems_portal_editable()
        correctable = self._ems_portal_correctable()
        for document_id, files in uploads.items():
            line = lines.get(document_id)
            if not files or not line:
                continue
            if not (editable or line in correctable):
                raise UserError(_("The document %s can no longer be changed.", line.name))
            line._ems_add_files(files)

    def _ems_portal_editable(self):
        """The applicant can change answers and every document: before the closing date."""
        self.ensure_one()
        return self.state in ('draft', 'submitted') and self.call_id.is_accepting

    def _ems_subsanation_open(self):
        """Corrections requested and their deadline (if any) not passed yet."""
        self.ensure_one()
        deadline = self.call_id.subsanation_deadline
        return self.state == 'subsanation' and not (deadline and deadline <= self.call_id._ems_now())

    def _ems_portal_correctable(self):
        """The document lines the applicant can still upload to during subsanation: those the
        team asked to correct."""
        self.ensure_one()
        if not self._ems_subsanation_open():
            return self.env['ems.erasmus.application.document']
        return self.document_ids.filtered('correction_requested')

    def action_submit(self):
        """Submit (or submit again) the application: every required document needs a file. Emails
        the applicant a receipt with the files received."""
        for application in self:
            if not (application._ems_portal_editable() or application._ems_subsanation_open()):
                raise UserError(_("The application can no longer be submitted."))
            missing = application.document_ids.filtered(lambda line: line.is_required and not line.attachment_ids)
            if missing:
                raise UserError(_("Upload the required documents first: %s", ", ".join(missing.mapped('name'))))
        self._ems_set_state('submitted')
        self.sudo().write({'submit_date': fields.Datetime.now()})
        self.document_ids.sudo().correction_requested = False
        self._ems_send('ems.email_template_erasmus_application_submitted')

    # --- helpers -----------------------------------------------------------------------------

    def _ems_documents_to_correct(self):
        self.ensure_one()
        return self.document_ids.filtered(
            lambda line: line.review_state == 'needs_change' or (line.is_required and not line.attachment_ids))

    def _ems_check_state(self, states):
        self.ensure_one()
        if self.state not in states:
            raise UserError(_("The application of %s is not in the right state for this action.",
                              self.partner_id.name))

    def _ems_set_state(self, state):
        self.with_context(ems_erasmus_state=True).sudo().write({'state': state})

    def _ems_can_check_sanction(self):
        return self.env.su or self.env.user.has_group('ems.group_head_of_studies')

    def _ems_can_manage(self):
        user = self.env.user
        return self.env.su or user.has_group('ems.group_erasmus') or user.has_group('ems.group_academic_admin')

    def _ems_send(self, xmlid):
        self._ems_mail(self, xmlid)

    @api.model
    def _ems_mail(self, records, xmlid):
        """Email `xmlid` (a template of `records`' model: applications, resolution lines, offers) to
        each applicant's own address; note it in the application's chatter when there is none."""
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return
        for record in records:
            partner = record.partner_id
            if partner.email:
                template.with_context(lang=partner.lang).sudo().send_mail(
                    record.id, force_send=False, email_values={'email_to': partner.email})
            else:
                application = record if record._name == self._name else record.application_id
                application.sudo().chatter(_("No email sent: the applicant has no email address."))

    def _ems_mail_document_list(self, lines):
        """The files of `lines` as an HTML list, for the emails."""
        return self.env['ems.base'].build_html_list([
            Markup("{}: {}").format(line.name, ", ".join(line.attachment_ids.mapped('name')) or "-")
            if line.attachment_ids else line.name
            for line in lines
        ])


class EmsErasmusApplicationDocument(models.Model):
    """The files an applicant uploaded for one document of the call, with the team's review.
    Every upload is kept: a new file never replaces the earlier ones."""
    _name = 'ems.erasmus.application.document'
    _description = 'Erasmus+ application document'
    _order = 'application_id, sequence, id'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    call_document_id = fields.Many2one(string="Call document", comodel_name='ems.erasmus.call.document',
                                       required=True, ondelete='restrict')
    name = fields.Char(string="Document", related='call_document_id.name')
    sequence = fields.Integer(string="Sequence", related='call_document_id.sequence', store=True)
    confidential = fields.Boolean(string="Confidential", related='call_document_id.confidential', store=True)
    is_required = fields.Boolean(string="Required", compute='_compute_is_required')
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_application_document_attachment_rel')
    review_state = fields.Selection(string="Review", required=True, default='pending', selection=[
        ('pending', "Pending review"), ('valid', "Valid"), ('needs_change', "Needs changes")])
    review_comment = fields.Char(string="Comment for the applicant")
    correction_requested = fields.Boolean(string="Correction requested", readonly=True, copy=False,
                                          help="Asked to the applicant in the current corrections request.")

    @api.depends('call_document_id.requirement', 'application_id.is_minor')
    def _compute_is_required(self):
        for line in self:
            requirement = line.call_document_id.requirement
            line.is_required = requirement == 'required' or (requirement == 'minor' and line.application_id.is_minor)

    def action_mark_valid(self):
        self.write({'review_state': 'valid'})

    def action_mark_needs_change(self):
        self.write({'review_state': 'needs_change'})

    def _ems_add_files(self, files):
        """Attach `files` ([(name, bytes)]) to this line and put it back to review."""
        self.ensure_one()
        attachments = self.env['ir.attachment'].sudo().create([{
            'name': name,
            'datas': base64.b64encode(content),
            'res_model': self._name,
            'res_id': self.id,
        } for name, content in files])
        self.sudo().write({'attachment_ids': [(4, attachment.id) for attachment in attachments],
                           'review_state': 'pending'})
