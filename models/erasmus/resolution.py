# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from .application import RANKED_STATES, SCORE_FIELDS, STAFF_SCORE_FIELDS

KINDS = [('admission', "Admission list"), ('provisional', "Provisional resolution"),
         ('definitive', "Definitive resolution"), ('rectification', "Rectification")]
# The resolution that must be published before preparing one of each kind.
PREVIOUS_KIND = {'provisional': 'admission', 'definitive': 'provisional', 'rectification': 'definitive'}
# Kinds published once per call; a correction afterwards is a rectification.
SINGLE_KINDS = ('admission', 'provisional', 'definitive')
# Kinds that decide who goes: their publication sets the applications' result and makes the offers.
FINAL_KINDS = ('definitive', 'rectification')
RESULTS = [('admitted', "Admitted"), ('excluded', "Excluded"), ('selected', "Selected"), ('reserve', "Reserve"),
           ('not_selected', "Not selected")]


def mask_document_id(value):
    """The identity document as published lists show it (art. 14; additional provision 7 of
    Organic Law 3/2018 and the Spanish data protection agency's guidance): only four digits. DNI
    12345678Z -> ***4567**, NIE X1234567L -> ****4567*, any other document (passport) -> its 4th to
    7th characters."""
    value = re.sub(r'[\s.-]', '', value or '').upper()
    if not value:
        return ''
    if re.fullmatch(r'[XYZ]\d{7}[A-Z]', value):
        return '****' + value[4:8] + '*'
    return '***' + value[3:7] + '*' * max(len(value) - 7, 0)


class EmsErasmusResolution(models.Model):
    """Issue #685 - a list the Erasmus+ Commission approves and the Erasmus team publishes:
    admission, provisional, definitive or rectification. Preparing it freezes its lines; once
    published it is never changed (a correction is a new rectification). See
    docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.resolution'
    _description = 'Erasmus+ resolution'
    _inherit = ['ems.base']
    _order = 'call_id, publish_date desc, id desc'
    _rec_names_search = ['call_id.name']  # name is computed in the reader's language, not stored

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='restrict',
                              index=True)
    kind = fields.Selection(string="Kind", selection=KINDS, required=True, tracking=True)
    name = fields.Char(string="Name", compute='_compute_name')
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False,
                             selection=[('draft', "Draft"), ('published', "Published")])
    line_ids = fields.One2many(string="Lines", comodel_name='ems.erasmus.resolution.line',
                               inverse_name='resolution_id', readonly=True)
    prepare_date = fields.Datetime(string="Lines frozen on", readonly=True, copy=False)
    approval_date = fields.Date(string="Approved by the Commission on", tracking=True, copy=False)
    approval_reference = fields.Char(string="Minutes", tracking=True, copy=False,
                                     help="Reference of the Erasmus+ Commission minutes that approve it.")
    notes = fields.Text(string="Notes for applicants",
                        help="Published with the list. A rectification must explain what it corrects.")
    publish_date = fields.Datetime(string="Published on", readonly=True, copy=False)
    published_by_id = fields.Many2one(string="Published by", comodel_name='res.users', readonly=True, copy=False)

    @api.depends('kind', 'call_id.name')
    @api.depends_context('lang')
    def _compute_name(self):
        """Not stored: in the reader's language (the portal, the PDF, the emails)."""
        kinds = self._ems_kind_labels()
        for resolution in self:
            resolution.name = f"{kinds.get(resolution.kind, '')} - {resolution.call_id.name or ''}"

    def write(self, vals):
        if self.filtered(lambda resolution: resolution.state == 'published') \
                and not self.env.context.get('ems_erasmus_publish'):
            raise UserError(_("A published resolution cannot be changed: publish a rectification instead."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda resolution: resolution.state == 'published'):
            raise UserError(_("A published resolution cannot be deleted."))
        return super().unlink()

    def action_prepare(self):
        """Freeze the lines as the applications are now. Can be repeated while it is a draft."""
        Line = self.env['ems.erasmus.resolution.line'].sudo()  # the lines are never edited by hand
        for resolution in self:
            if resolution.state != 'draft':
                raise UserError(_("The resolution is already published."))
            resolution._ems_check_can_prepare()
            values = resolution._ems_line_values()
            resolution.line_ids.sudo().unlink()
            Line.create([{**vals, 'resolution_id': resolution.id} for vals in values])
            resolution.prepare_date = fields.Datetime.now()

    def action_publish(self):
        """Publish on the portal and email every applicant their result. A definitive resolution or
        a rectification also sets each application's result and offers the place to the selected."""
        for resolution in self:
            if resolution.state != 'draft':
                raise UserError(_("The resolution is already published."))
            if not resolution.line_ids:
                raise UserError(_("Prepare the lines first."))
            if not (resolution.approval_date and (resolution.approval_reference or '').strip()):
                raise UserError(_("Record the Commission's approval (date and minutes) before publishing."))
            if resolution.kind == 'rectification' and not (resolution.notes or '').strip():
                raise UserError(_("Explain in the notes what the rectification corrects."))
            resolution._ems_check_can_prepare()
            call = resolution.call_id
            if resolution.kind in FINAL_KINDS and not (
                    call.acceptance_deadline and call.acceptance_deadline > call._ems_now()):
                raise UserError(_("Set a future acceptance deadline on the call before publishing who goes."))
        self.with_context(ems_erasmus_publish=True).write({
            'state': 'published', 'publish_date': fields.Datetime.now(), 'published_by_id': self.env.uid})
        for resolution in self:
            if resolution.kind in FINAL_KINDS:
                resolution._ems_apply_results()
            self.env['ems.erasmus.application']._ems_mail(
                resolution.line_ids, 'ems.email_template_erasmus_resolution_published')

    def _ems_check_can_prepare(self):
        self.ensure_one()
        call = self.call_id
        if call.state != 'closed':
            raise UserError(_("Close the applications of the call first."))
        published = call.resolution_ids.filtered(lambda resolution: resolution.state == 'published') - self
        if self.kind in SINGLE_KINDS and self.kind in published.mapped('kind'):
            raise UserError(_("This call already has a published %s: publish a rectification instead.",
                              self._ems_kind_labels()[self.kind].lower()))
        previous = PREVIOUS_KIND.get(self.kind)
        if previous and previous not in published.mapped('kind'):
            raise UserError(_("Publish the %s first.", self._ems_kind_labels()[previous].lower()))
        if call.audience == 'staff' and self.kind != 'admission' and not sum(call.modality_ids.mapped('places')):
            raise UserError(_("Add the modalities of the call, with their places, before preparing the resolution."))
        applications = call.application_ids
        undecided = applications.filtered(lambda application: application.state in ('submitted', 'subsanation'))
        if undecided:
            raise UserError(_("Admit or exclude every application first: %s",
                              ", ".join(undecided.partner_id.mapped('name'))))
        if self.kind != 'admission':
            pending = applications.filtered(lambda application: application.state in RANKED_STATES and (
                not application.score_complete or application.needs_draw))
            if pending:
                raise UserError(_("Complete the score and resolve the draws of: %s",
                                  ", ".join(pending.partner_id.mapped('name'))))
        missing = self._ems_applications().filtered(
            lambda application: not mask_document_id(application._ems_identity_document()))
        if missing:
            raise UserError(_("Record the identity document of: %s", ", ".join(missing.partner_id.mapped('name'))))

    def _ems_kind_labels(self):
        return dict(self._fields['kind']._description_selection(self.env))

    def _ems_applications(self):
        """The applications the list includes: admitted and excluded for the admission list; for
        the others, also the results already decided (selected, reserve...)."""
        self.ensure_one()
        states = ('admitted', 'excluded') if self.kind == 'admission' else RANKED_STATES + ('excluded',)
        return self.call_id.application_ids.filtered(lambda application: application.state in states)

    def _ems_list_groups(self):
        """The published list's tables, as [(title, lines)]: one per modality in a students' call,
        a single one in a staff call, which ranks everyone together (issue #686)."""
        self.ensure_one()
        if self.call_id.audience == 'staff':
            return [('', self.line_ids)]
        return [(modality.name, self.line_ids.filtered(lambda line: line.modality_id == modality))
                for modality in self.line_ids.modality_id]

    def _ems_line_values(self):
        self.ensure_one()
        values = []
        for application in self._ems_applications().sudo().sorted(
                lambda application: (application.state == 'excluded',
                                     application.audience == 'student' and application.modality_id.sequence,
                                     application.audience == 'student' and application.modality_id.id,
                                     application.rank, application.partner_id.name)):
            vals = {
                'application_id': application.id,
                'modality_id': application.modality_id.id,
                'public_id': mask_document_id(application._ems_identity_document()),
                'sequence': len(values) + 1,
            }
            if application.state == 'excluded':
                vals.update(result='excluded', exclusion_reason=application.exclusion_reason)
            elif self.kind == 'admission':
                vals['result'] = 'admitted'
            else:
                vals.update({name: application[name] for name in SCORE_FIELDS + STAFF_SCORE_FIELDS},
                            rank=application.rank,
                            result=application._ems_ranking_result())
            values.append(vals)
        return values

    def _ems_apply_results(self):
        """Set each application's result, except those that already answered a place offer, and
        offer the place to the selected without one."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: line.result in ('selected', 'reserve', 'not_selected')
                                       and line.application_id.state not in ('accepted', 'renounced'))
        for result, result_lines in lines.grouped('result').items():
            result_lines.application_id._ems_set_state(result)
        selected = lines.filtered(lambda line: line.result == 'selected').application_id.filtered(
            lambda application: not application.offer_ids.filtered(
                lambda offer: offer.state in ('pending', 'accepted')))
        self.env['ems.erasmus.offer']._ems_offer(selected, self.call_id.acceptance_deadline, notify=False)


class EmsErasmusResolutionLine(models.Model):
    """Issue #685 - one applicant in a resolution, frozen when it was prepared. The published
    list identifies them only by the masked identity document (`public_id`), never by name."""
    _name = 'ems.erasmus.resolution.line'
    _description = 'Erasmus+ resolution line'
    _order = 'resolution_id, sequence, id'

    resolution_id = fields.Many2one(string="Resolution", comodel_name='ems.erasmus.resolution', required=True,
                                    ondelete='cascade', index=True)
    kind = fields.Selection(string="Kind", related='resolution_id.kind')
    audience = fields.Selection(string="Applicants", related='resolution_id.call_id.audience')
    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='restrict', index=True)
    partner_id = fields.Many2one(string="Applicant", related='application_id.partner_id', store=True)
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality', ondelete='restrict')
    sequence = fields.Integer(string="Sequence")
    public_id = fields.Char(string="Identity document (published)")
    result = fields.Selection(string="Result", selection=RESULTS, required=True)
    rank = fields.Integer(string="Rank")
    score_a = fields.Float(string="A. Record", digits=(5, 2))
    score_b = fields.Float(string="B. Interview", digits=(5, 2))
    score_c = fields.Float(string="C. Languages", digits=(5, 2))
    score_d = fields.Float(string="D. Fewer opportunities", digits=(5, 2),
                           groups='ems.group_erasmus,ems.group_academic_admin')
    score_e = fields.Float(string="E. First mobility", digits=(5, 2))
    score_f = fields.Float(string="F. Conduct", digits=(5, 2))
    score_total = fields.Float(string="Total score", digits=(5, 2))
    # Issue #686: the staff call's criteria.
    score_plan = fields.Float(string="1. Mobility plan", digits=(4, 2))
    score_last_mobility = fields.Float(string="2. Last mobility", digits=(4, 2))
    score_projects = fields.Float(string="3. Centre projects", digits=(4, 2))
    score_staff_language = fields.Float(string="4. Languages", digits=(4, 2))
    score_seniority = fields.Float(string="5. Seniority", digits=(4, 2))
    score_internationalisation = fields.Float(string="6. Internationalisation", digits=(4, 2))
    exclusion_reason = fields.Text(string="Exclusion reason",
                                   help="Only for the applicant (email and portal), never in the published list.")

    def _ems_format_score(self):
        """The total as the reader's language writes numbers, for the email."""
        self.ensure_one()
        return formatLang(self.env, self.score_total, digits=2)
