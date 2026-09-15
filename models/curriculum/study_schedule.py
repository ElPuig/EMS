# -*- coding: utf-8 -*-

import base64

from odoo import api, fields, models
from odoo.tools.pdf import merge_pdf

from ..shared.schedule_report_mixin import PUBLIC_SCHEDULE_ROUTE


class EmsStudySchedule(models.Model):
    """Issue #453 follow-up - one public PDF per study with every active group's schedule, see
    docs/en/developers/contacts/group_schedule.md's "Study schedule link"."""
    _inherit = 'ems.study'

    public_schedule_slug = fields.Char(string="Public schedule slug", compute="_compute_public_schedule_slug",
        store=True, index=True)
    public_schedule_url = fields.Char(string="Public schedule link", compute="_compute_public_schedule_url")

    @api.depends('acronym')
    def _compute_public_schedule_slug(self):
        for study in self:
            study.public_schedule_slug = self.env['ir.http']._slugify(study.acronym) if study.acronym else False

    # Not stored, and read on every form load: whether the study has any active group right now is
    # what decides if the link is worth showing (without one, it can only be a 404).
    @api.depends('public_schedule_slug')
    def _compute_public_schedule_url(self):
        studies_with_groups = self._get_public_schedule_groups().study_id
        for study in self:
            study.public_schedule_url = \
                f"{study.get_base_url()}{PUBLIC_SCHEDULE_ROUTE}/study/{study.public_schedule_slug}.pdf" \
                if study.public_schedule_slug and study._origin in studies_with_groups else False

    def _get_public_schedule_groups(self):
        """These studies' active groups, in the order their pages appear in the study PDF. sudo: the
        public route has no user, and the link's visibility shouldn't depend on who opens the form."""
        return self.env['ems.group'].sudo().search([('study_id', 'in', self._origin.ids)], order='course, name')

    def _get_public_schedule_pdf(self):
        """Merges the groups' own pre-rendered public PDFs, so nothing is rendered here: the study
        PDF follows every group's regeneration, and whichever groups the study has each year, with
        no stored file or trigger of its own. A group whose first PDF isn't rendered yet is left
        out. Returns False when no group has one."""
        groups = self._get_public_schedule_groups().filtered('public_schedule_pdf')
        return merge_pdf([base64.b64decode(group.public_schedule_pdf) for group in groups]) if groups else False
