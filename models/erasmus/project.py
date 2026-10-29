# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date

from .call import PROJECTS
from .records import PARTICIPANT_CATEGORIES, PROJECT_CATEGORIES
from .workflow import check_kept

# SEPIE: keep the documents 3 years after the final payment of the grant, 5 when it is above 60,000 € (issue #697).
LARGE_PROJECT = 60000


class EmsErasmusProject(models.Model):
    """Issue #687 - an Erasmus+ project the centre runs (its grant agreement), to which the Erasmus
    coordination assigns each mobility: CFGM on a KA121-VET project, CFGS on a KA131-HED one.
    Several of each kind can be active at once (one per call year). Its documents are organised in
    five categories and exported as one ZIP with its mobilities' records (ems.erasmus.export); see
    docs/en/developers/erasmus/records.md."""
    _name = 'ems.erasmus.project'
    _description = 'Erasmus+ project'
    _inherit = ['ems.base']
    _order = 'active desc, kind, name desc'

    name = fields.Char(string="Agreement number", required=True, help="e.g. 2026-1-ES01-KA121-VET-000123456")
    kind = fields.Selection(string="Kind", selection=PROJECTS, required=True)
    date_start = fields.Date(string="Start")
    date_end = fields.Date(string="End")
    active = fields.Boolean(string="Active", default=True)
    mobility_ids = fields.One2many(string="Mobilities", comodel_name='ems.erasmus.mobility', inverse_name='project_id')
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency',
                                  default=lambda self: self.env.company.currency_id)
    budget = fields.Monetary(string="Grant awarded", help="The project's grant: above 60,000 € its documents are kept "
                                                          "5 years after its final payment, otherwise 3.")
    final_payment_date = fields.Date(string="Final payment received on",
                                     help="When SEPIE paid the balance of the grant: the keeping period counts from it.")
    keep_until = fields.Date(string="Keep the documents until", compute='_compute_keep_until', store=True,
                             help="SEPIE: 3 years after the final payment of the grant, 5 when the grant is above "
                                  "60,000 €. Empty until the final payment and the grant are known. Nothing is ever "
                                  "deleted automatically.")
    retention_hold = fields.Boolean(string="Keep while an audit or request is pending",
                                    help="An audit, a check or a SEPIE request is still open: keep every document "
                                         "even after the date above.")
    retention_note = fields.Char(string="Pending audit or request")
    retention_notice_date = fields.Date(
        string="Coordination told on", readonly=True, copy=False,
        help="When EMS told the Erasmus coordination that the keeping period was over (once per project, unless "
             "the date changes). Nothing is deleted: the coordination decides what to do.")
    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.project.document',
                                   inverse_name='project_id')
    invoice_ids = fields.One2many(string="Invoices", comodel_name='ems.erasmus.invoice', inverse_name='project_id')
    payment_ids = fields.One2many(string="Grant payments", comodel_name='ems.erasmus.payment',
                                  inverse_name='project_id')
    export_ids = fields.One2many(string="Exports", comodel_name='ems.erasmus.export', inverse_name='project_id')
    record_count = fields.Integer(string="Participants' records", compute='_compute_record_counts')
    record_complete_count = fields.Integer(string="Complete records", compute='_compute_record_counts')
    record_missing_count = fields.Integer(string="Documents missing", compute='_compute_record_counts',
                                          help="Required documents not complete yet in the participants' records.")

    @api.depends('final_payment_date', 'budget')
    def _compute_keep_until(self):
        for project in self:
            years = 5 if project.budget > LARGE_PROJECT else 3
            project.keep_until = project.final_payment_date and project.budget and \
                project.final_payment_date + relativedelta(years=years)

    @api.depends('mobility_ids.state', 'mobility_ids.record_missing')
    def _compute_record_counts(self):
        for project in self:
            mobilities = self.env['ems.erasmus.export']._ems_project_mobilities(project)
            project.record_count = len(mobilities)
            project.record_complete_count = len(mobilities.filtered(lambda mobility: not mobility.record_missing))
            project.record_missing_count = sum(mobilities.mapped('record_missing'))

    @api.depends('name', 'kind')
    def _compute_display_name(self):
        kinds = dict(self._fields['kind'].selection)
        for project in self:
            project.display_name = f"{project.name} ({kinds.get(project.kind, '')})" if project.kind else project.name

    def write(self, vals):
        """A new keeping date (the final payment or the grant corrected) is told again when it comes."""
        if {'final_payment_date', 'budget'} & set(vals):
            vals = {**vals, 'retention_notice_date': False}
        return super().write(vals)

    def action_export(self):
        self.ensure_one()
        return self.env['ems.erasmus.export']._ems_open_wizard(project_id=self.id)

    @api.model
    def _cron_retention_notice(self):
        """Audit D-12, daily: a task for the Erasmus coordination on each project whose documents are
        past their keeping date and not held for an audit, once. Nothing is ever deleted automatically."""
        today = self.env['ems.datetime_utils'].get_local_today()
        projects = self.sudo().with_context(active_test=False).search([
            ('keep_until', '<', today), ('retention_hold', '=', False), ('retention_notice_date', '=', False)])
        if not projects:
            return
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        coordinators = self.env['ems.erasmus.group.mobility']._ems_coordinators()
        for project in projects:
            summary = _("Erasmus+: the documents of %(project)s were to be kept until %(date)s. Decide what to keep "
                        "and what to delete (EMS deletes nothing)", project=project.name,
                        date=format_date(self.env, project.keep_until))
            for user in coordinators:
                project.activity_schedule(activity_type_id=activity_type.id, user_id=user.id, summary=summary)
        projects.write({'retention_notice_date': today})


class EmsErasmusProjectDocument(models.Model):
    """Issue #697 - files of a project that no other EMS record holds (the project application,
    the grant agreement, budget follow-up, exceptional costs, dissemination, the final report...),
    in one of the project's categories. Linked to some participants, it is part of their records
    too (shared, never copied): e.g. a document common to several mobilities, or one about a single
    participant that is not in the call's documents."""
    _name = 'ems.erasmus.project.document'
    _description = 'Erasmus+ project document'
    _order = 'category, date desc, id desc'

    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', required=True,
                                 ondelete='restrict', index=True)
    category = fields.Selection(string="Category", selection=PROJECT_CATEGORIES, required=True, default='01_Projecte')
    name = fields.Char(string="Name", required=True)
    date = fields.Date(string="Date", default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_project_document_attachment_rel')
    mobility_ids = fields.Many2many(string="Participants", comodel_name='ems.erasmus.mobility',
                                    relation='ems_erasmus_project_document_mobility_rel',
                                    column1='ems_erasmus_project_document_id', column2='ems_erasmus_mobility_id',
                                    domain="[('project_id', '=', project_id)]",
                                    help="Optional: the participants it is about. It appears in their records.")
    participant_category = fields.Selection(
        string="Category in the records", selection=PARTICIPANT_CATEGORIES, default='03_Durant_la_mobilitat',
        help="Where it appears in the records of the participants it is about.")
    confidential = fields.Boolean(string="Confidential",
                                  help="Health, inclusion or bank data: only the Erasmus team sees it, and it only "
                                       "leaves EMS in an audit export.")
    notes = fields.Text(string="Notes")

    @api.constrains('project_id', 'mobility_ids')
    def _check_mobilities(self):
        for document in self:
            if document.mobility_ids.project_id - document.project_id:
                raise ValidationError(_("A project's document is only about participants of that project."))

    def unlink(self):
        """Audit D-2: a document with files is evidence of the project, as a participant's document is."""
        check_kept(self, self.filtered('attachment_ids'))
        return super().unlink()
