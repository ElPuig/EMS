# -*- coding: utf-8 -*-

import re
from collections import Counter

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .records import safe_name

# The automatic diffusion actions: one per Erasmus+ email EMS sends to whoever can apply to a call.
ANNOUNCEMENTS = ('ems.email_template_erasmus_call_open', 'ems.email_template_erasmus_call_reminder')
CHANNELS = [
    ('ems_email', "Email from EMS"), ('email', "Other email"), ('session', "Information session"),
    ('event', "Event"), ('web', "Website"), ('social', "Social media"), ('press', "Press"), ('other', "Other"),
]
# The Mobilitat FP network's Drive folders, one per objective of its annual report.
NETWORK_FOLDERS = {'management': '1-gestio', 'documentation': '2-documentacio', 'mobilities': '3-mobilitats',
                   'diffusion': '4-difusio'}
COURSE_NAME = re.compile(r'^\d{4}-\d{4}$')
# The Mobilitat FP network's objective 4: at least this many diffusion actions a school year.
DIFFUSION_TARGET = 10


class EmsErasmusQualityHistory(models.Model):
    """The Erasmus+ indicators of a course before EMS kept them, typed in by the coordination from
    its own records (a manual load, with its source), so the evolution starts from the beginning.
    A course EMS has data of uses EMS's figures instead. See docs/en/developers/erasmus/quality.md."""
    _name = 'ems.erasmus.quality.history'
    _description = 'Erasmus+ indicators of an earlier course (manual load)'
    _order = 'course_name desc'
    _sql_constraints = [
        ('course_unique', 'unique(course_name)', "There is already a manual load for this course."),
    ]

    course_name = fields.Char(string="Course", required=True, help="As EMS names the courses, e.g. 2022-2023.")
    student_applicants = fields.Integer(string="Student applicants")
    student_target = fields.Integer(string="Target students", help="Every student who could apply that course.")
    staff_applicants = fields.Integer(string="Staff applicants", help="Empty or 0: no data.")
    staff_target = fields.Integer(string="Target staff", help="Empty or 0: no data.")
    satisfaction = fields.Float(string="Satisfaction (average)", digits=(4, 2),
                                help="On a scale from 0 or 1 to 10; convert other scales first (e.g. 0-4 x 2.5).")
    satisfaction_count = fields.Integer(string="Answers (n)")
    source = fields.Char(string="Source", required=True,
                         help="Where the figures come from and how they were counted.")

    @api.constrains('course_name')
    def _check_course_name(self):
        for history in self:
            if not COURSE_NAME.match(history.course_name or ''):
                raise ValidationError(_("Write the course as EMS names it, e.g. 2022-2023."))

    @api.constrains('satisfaction')
    def _check_satisfaction(self):
        for history in self:
            if not 0 <= history.satisfaction <= 10:
                raise ValidationError(_("The satisfaction goes from 0 to 10."))

    def _compute_display_name(self):
        for history in self:
            history.display_name = history.course_name


class EmsErasmusDiffusion(models.Model):
    """An Erasmus+ diffusion action (objective 4 of the Mobilitat FP network: at least 10 a year).
    EMS records its own emails to whoever can apply to a call by itself; the team adds the rest by
    hand (information sessions, ErasmusDays, the website, social media). The audience is always
    generic ("Students of CFGS"), never a name."""
    _name = 'ems.erasmus.diffusion'
    _description = 'Erasmus+ diffusion action'
    _inherit = ['ems.attachment_link_mixin']
    _order = 'date desc, id desc'

    date = fields.Date(string="Date", required=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    name = fields.Char(string="Action", required=True)
    channel = fields.Selection(string="Channel", selection=CHANNELS, required=True, default='session')
    audience = fields.Char(string="Audience", help="Generic, never names: e.g. students of CFGS, FP teachers.")
    recipient_count = fields.Integer(string="People reached")
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', required=True, index=True,
                                default=lambda self: self.env.company.current_course_id)
    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', ondelete='set null')
    attachment_ids = fields.Many2many(string="Evidence", comodel_name='ir.attachment',
                                      help="A capture of the post, the poster, the sign-in sheet... without "
                                           "personal data.")
    is_automatic = fields.Boolean(string="Recorded by EMS", readonly=True)


class EmsErasmusCall(models.Model):
    _inherit = 'ems.erasmus.call'

    def _ems_announce(self, partners, xmlid):
        """Every email EMS sends to whoever can apply is a diffusion action, recorded with a
        generic audience in the centre's language."""
        count = super()._ems_announce(partners, xmlid)
        if count and xmlid in ANNOUNCEMENTS:
            centre = self.with_context(lang=self.env.company.ems_lang or self.env.lang)
            self.env['ems.erasmus.diffusion'].sudo().create(centre._ems_diffusion_values(xmlid, count))
        return count

    def _ems_diffusion_values(self, xmlid, count):
        """In the language of `self`'s context (the centre's)."""
        self.ensure_one()
        label = (_("Notice of the open call") if xmlid == 'ems.email_template_erasmus_call_open'
                 else _("Reminder before the call closes"))
        levels = ", ".join(self.modality_ids.level_ids.mapped('acronym'))
        return {
            'date': self.env['ems.datetime_utils'].get_local_today(), 'channel': 'ems_email',
            'name': f"{label}: {self.name}",
            'audience': _("FP teachers") if self.audience == 'staff' else _("Students of %s", levels),
            'recipient_count': count, 'course_id': (self.course_id or self.env.company.current_course_id).id,
            'call_id': self.id, 'is_automatic': True,
        }


class EmsErasmusQualityPanel(models.TransientModel):
    _inherit = 'ems.erasmus.quality.panel'

    def _compute_display_name(self):
        self.display_name = _("Quality indicators")

    @api.model
    def action_open_panel(self):
        """The menu opens a panel already created, so that its title is its name and not "New"
        (review 2026-11-05)."""
        self._ems_check_access()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_quality_panel')
        # Issue #793 (12.1): on the current course, what is looked at almost every time (and the
        # Mobilitat FP evidence then visible); emptying it shows every course.
        return dict(action, res_id=self.create({'course_id': self.env.company.current_course_id.id}).id)

    def action_print_report(self):
        self._ems_check_access()
        self.ensure_one()
        return self.env.ref('ems.action_report_erasmus_quality').report_action(self)

    def action_network_export(self):
        """The evidence of the Mobilitat FP network's report for the panel's course, as a ZIP."""
        self._ems_check_access()
        self.ensure_one()
        if not self.course_id:
            raise UserError(_("Choose the course first."))
        export = self.env['ems.erasmus.export'].create({'scope': 'network', 'course_id': self.course_id.id})
        return export.action_generate()

    def _ems_report_values(self):
        """What the PDF shows: the figures of the panel, the improvement actions of the surveys of
        the selection, the filters, the criteria and the generation date. No name of any participant."""
        self.ensure_one()
        data = self._ems_data()
        actions = data['surveys'].sudo().improvement_action_id
        filters = [(self._fields[name].get_description(self.env)['string'], self[name].display_name)
                   for name in ('course_id', 'call_id', 'project_id', 'study_id', 'host_partner_id') if self[name]]
        if self.participant_type:
            filters.append((_("Participant type"), dict(self._fields['participant_type']._description_selection(
                self.env))[self.participant_type]))
        state_labels = dict(self.env['ems.quality.action']._fields['state']._description_selection(self.env))
        return {
            'indicators': [self._ems_indicator_row(row) for row in data['indicators']],
            'by_type': data['by_type'], 'by_host': data['by_host'], 'funnel': data['funnel'],
            'evolution': data['evolution'], 'filters': filters, 'headers': self._ems_headers(),
            'actions': [(action.code or '', action.name, state_labels.get(action.state, ''),
                         action.deadline_date and str(action.deadline_date) or '') for action in actions],
            'date': self.env['ems.datetime_utils'].get_local_datetime().strftime('%d/%m/%Y %H:%M'),
        }

    def _ems_data(self):
        """Issue #793 (12.11): the diffusion actions of the course against the Mobilitat FP network's
        target, one more row of the indicators. Only with a course: the target is per school year."""
        data = super()._ems_data()
        count = self.course_id and self.env['ems.erasmus.diffusion'].sudo().search_count(
            [('course_id', '=', self.course_id.id)])
        data['indicators'].append({
            'name': _("Diffusion actions"), 'value': count if self.course_id else None, 'unit': '',
            'target': DIFFUSION_TARGET, 'at_least': True, 'count': True, 'n': '-',
            'help': _("Diffusion actions of the course (the call notices EMS sends, and those the team adds): the "
                      "Mobilitat FP network asks for at least %s a year. Choose a course to see them.",
                      DIFFUSION_TARGET)})
        return data

    def _ems_calls(self, course=True):
        """A project narrows the calls to those with mobilities charged to it."""
        calls = super()._ems_calls(course)
        if self.project_id:
            calls &= self.env['ems.erasmus.mobility'].sudo().search([('project_id', '=', self.project_id.id)]).call_id
        return calls

    def _ems_evolution(self, memo=None):
        """EMS's own figures for every course it has data of, and the manual load for the earlier
        ones (marked as such), oldest first."""
        rows = super()._ems_evolution(memo)
        known = {row[0] for row in rows}
        for history in self.env['ems.erasmus.quality.history'].sudo().search([]):
            if history.course_name in known:
                continue
            student = 100.0 * history.student_applicants / history.student_target if history.student_target else None
            staff = 100.0 * history.staff_applicants / history.staff_target if history.staff_target else None
            rows.append([_("%s (manual load)", history.course_name), self._ems_number(student, '%'),
                         self._ems_number(staff, '%'), self._ems_number(history.satisfaction or None),
                         history.satisfaction_count])
        return sorted(rows, key=lambda row: str(row[0]))


class EmsErasmusExport(models.Model):
    _inherit = 'ems.erasmus.export'

    scope = fields.Selection(selection_add=[('network', "Mobilitat FP evidence")], ondelete={'network': 'cascade'})
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', readonly=True, ondelete='restrict')

    def _ems_check_request(self):
        super()._ems_check_request()
        if self.scope == 'network' and not self.course_id:
            raise UserError(_("Choose the course whose evidence to export."))

    def _ems_root_name(self):
        if self.scope == 'network':
            return safe_name(f"Mobilitat FP - {self.sudo().course_id.name}")
        return super()._ems_root_name()

    def _ems_missing_count(self):
        return 0 if self.scope == 'network' else super()._ems_missing_count()

    def _ems_entries(self):
        if self.scope == 'network':
            return self._ems_network_entries()
        entries = super()._ems_entries()
        if self.scope == 'project':
            entries.append(self._ems_quality_report_entry(
                {'project_id': self.project_id.id}, '05_Informe_final_i_auditoria', '05_Informe_final_i_auditoria'))
        return entries

    def _ems_quality_report_entry(self, filters, folder, category):
        """The quality report (PDF) of the panel with `filters`, as an entry of the ZIP."""
        panel = self.env['ems.erasmus.quality.panel'].sudo().create(filters)
        pdf, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf('ems.action_report_erasmus_quality',
                                                                            panel.ids)
        name = _("Quality report")
        return {'path': f"{folder}/{safe_name(name)}.pdf", 'content': pdf, 'category': category,
                'document': name, 'status': _("Complete")}

    def _ems_network_entries(self):
        """The evidence of the Mobilitat FP network's report for one course, by the folders of its
        Drive. Only totals and generic audiences: no personal data, as the network asks."""
        course = self.sudo().course_id
        calls = self.env['ems.erasmus.call'].sudo().search([('course_id', '=', course.id), ('state', '!=', 'draft')])
        management, documentation = NETWORK_FOLDERS['management'], NETWORK_FOLDERS['documentation']
        mobilities_folder, diffusion = NETWORK_FOLDERS['mobilities'], NETWORK_FOLDERS['diffusion']
        entries = []
        # 1. Management: the Erasmus+ team's meetings, minuted in the Quality app.
        workgroup = self.env.company.erasmus_workgroup_id
        if workgroup:
            minutes = self.env['ems.minute'].sudo().search([('workgroup_id', '=', workgroup.id),
                                                            ('course_id', '=', course.id)], order='start_datetime')
            entries.append(self._ems_csv_entry(
                f"{management}/{safe_name(_('Erasmus+ team meetings'))}.csv", management, _("Meetings"),
                [_("Date"), _("Code"), _("Title")],
                [[minute.start_datetime and self._ems_local(minute.start_datetime) or '', minute.code or '',
                  minute.name or ''] for minute in minutes]))
        else:
            # Review 2026-11-05: the folder used to be missing with no word on why.
            note = _("The Erasmus+ team's meetings are listed here once the setting \"Erasmus+ team meetings\" "
                     "(EMS settings) says which workgroup's minutes they are.")
            entries.append({'path': f"{management}/{safe_name(_('Read me'))}.txt", 'content': note.encode(),
                            'category': management, 'document': _("Meetings"), 'status': _("Missing")})
        # 2. Documentation: the calls published and their calendar, the lists (totals only) and the
        # records complete.
        entries.append(self._ems_csv_entry(
            f"{documentation}/{safe_name(_('Calls'))}.csv", documentation, _("Calls"),
            [_("Call"), _("Applicants"), _("Applications open"), _("Applications close"), _("Claims deadline"),
             _("Acceptance deadline"), _("Notice sent on")],
            [[call.name, dict(call._fields['audience']._description_selection(self.env))[call.audience]]
             + [call[name] and self._ems_local(call[name]) or '' for name in
                ('date_open', 'date_close', 'claims_deadline', 'acceptance_deadline', 'announce_date')]
             for call in calls]))
        for call in calls:
            attachments = self._ems_field_attachments(call, 'rules_document').get(call.id) or self.env['ir.attachment']
            for entry in self._ems_files(f"{documentation}/{safe_name(call.name)}", attachments, versions=False,
                                         names={attachment.id: call.rules_filename for attachment in attachments}):
                entries.append({**entry, 'category': documentation, 'document': call.name, 'status': _("Complete")})
        result_labels = dict(self.env['ems.erasmus.resolution.line']._fields['result']._description_selection(self.env))
        kind_labels = dict(self.env['ems.erasmus.resolution']._fields['kind']._description_selection(self.env))
        rows = []
        for resolution in calls.resolution_ids.filtered(lambda resolution: resolution.state == 'published'):
            counts = Counter(resolution.line_ids.mapped('result'))
            rows.append([resolution.call_id.name, kind_labels.get(resolution.kind, ''),
                         self._ems_local(resolution.publish_date), len(resolution.line_ids),
                         ", ".join(f"{result_labels.get(result, result)}: {count}"
                                   for result, count in sorted(counts.items()) if result)])
        entries.append(self._ems_csv_entry(
            f"{documentation}/{safe_name(_('Published lists'))}.csv", documentation, _("Published lists"),
            [_("Call"), _("List"), _("Published on"), _("Applications"), _("Results")], rows))
        mobilities = calls.mobility_ids.filtered(lambda mobility: mobility.state in ('preparing', 'done'))
        groups = self.env['ems.erasmus.group.mobility'].sudo().search([
            ('course_id', '=', course.id), ('state', 'not in', ('draft', 'cancelled'))])
        participants = groups.participant_ids.filtered(lambda participant: participant.state == 'active')
        complete = len(mobilities.filtered(lambda mobility: not mobility.record_missing)) + len(
            participants.filtered(lambda participant: not participant.record_missing))
        total = len(mobilities) + len(participants)
        entries.append(self._ems_csv_entry(
            f"{documentation}/{safe_name(_('Complete documentation'))}.csv", documentation,
            _("Complete documentation"), [_("Participants"), _("With every required document"), _("Percentage")],
            [[total, complete, f"{100.0 * complete / total:.1f} %".replace('.', ',') if total else '-']]))
        # 3. Mobilities: the quality report of the course (interest, participants, satisfaction).
        entries.append(self._ems_quality_report_entry({'course_id': course.id}, mobilities_folder, mobilities_folder))
        # 4. Diffusion: every action of the course, with its evidence.
        actions = self.env['ems.erasmus.diffusion'].sudo().search([('course_id', '=', course.id)], order='date, id')
        channel_labels = dict(self.env['ems.erasmus.diffusion']._fields['channel']._description_selection(self.env))
        entries.append(self._ems_csv_entry(
            f"{diffusion}/{safe_name(_('Diffusion actions'))}.csv", diffusion, _("Diffusion actions"),
            [_("Date"), _("Action"), _("Channel"), _("Audience"), _("People reached")],
            [[action.date.strftime('%d/%m/%Y'), action.name, channel_labels.get(action.channel, ''), action.audience or '',
              action.recipient_count or ''] for action in actions]))
        for action in actions.filtered('attachment_ids'):
            folder = f"{diffusion}/{safe_name(f'{action.date} {action.name}')}"
            for entry in self._ems_files(folder, action.attachment_ids, versions=False):
                entries.append({**entry, 'category': diffusion, 'document': action.name, 'status': _("Complete")})
        return entries


class ResCompany(models.Model):
    _inherit = 'res.company'

    erasmus_workgroup_id = fields.Many2one(
        string="Erasmus+ team workgroup", comodel_name='ems.workgroup',
        help="The workgroup whose minutes in the Quality app are the Erasmus+ team's meetings, for the "
             "Mobilitat FP evidence.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    erasmus_workgroup_id = fields.Many2one(related='company_id.erasmus_workgroup_id', readonly=False)

