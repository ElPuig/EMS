# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmsSubject(models.Model):
    _name = "ems.subject"
    _description = "Subject: The main item for a student's subject."
    _rec_names_search = ['name', 'acronym']
    _order = "code asc"

    code = fields.Char(string="Code", required=True)
    acronym = fields.Char(string="Acronym", required=True)
    name = fields.Char(string="Name", required=True)
    ects = fields.Integer(string="ECTS Credits") 
    is_tutorship = fields.Boolean(string="Tutorship", default=False)

    internal_hours = fields.Integer(string="Internal hours") 
    external_hours = fields.Integer(string="External hours")       
    total_hours = fields.Integer(string="Total hours", compute='_compute_total_hours')

    product_id = fields.Many2one(
        comodel_name='product.product', 
        string="Service Product", 
        ondelete='set null',
        delegate=False,
        help="Field to link the subject with the technical product used in enrolments (Sale Orders)"
    )
            
    outcome_ids = fields.One2many(string="Learning Outcome", comodel_name="ems.outcome", inverse_name="subject_id")
    content_ids = fields.One2many(string="Content", comodel_name="ems.content", inverse_name="subject_id")        
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")       

    notes = fields.Text("Notes")

    @api.constrains('code', 'study_ids')
    def _check_code_unique_per_study(self):
        """The same official code can legitimately be reused by two different subjects when
        each belongs to a different curriculum (e.g. MP 3003 has different learning outcomes
        and hours in a CFGB and in a PFI) - a plain global 'unique(code)' would force a fake
        code suffix on one of them, breaking any external import/convalidation that matches by
        the real code. So a duplicate code is only a real conflict when the two subjects could
        actually be confused for one another: either one of them has no study at all (nothing
        to disambiguate by, so treated as a genuine duplicate, preserving the original
        behaviour for subjects not yet assigned to a study), or they share at least one study.
        Declared on 'study_ids' (not just 'code') so adding/removing a study - from either this
        subject's own form or the study's own 'Subjects' tab, which write the same many2many
        relation from its other side - re-validates it too.

        A data file's subject_ids can only be populated from 'ems.study.csv', a separate file
        loaded AFTER 'ems.subject.csv' - so a brand-new subject's own create() always fires this
        constraint first, with no study yet (same transient-state problem as
        'ems.planning.check_ponderation', which this mirrors) - 'install_mode=True' is the
        context Odoo's own data-file loader always applies (odoo/models.py::_load_records), so
        this only skips the check while more files may still be loading, never for a real UI
        edit."""
        if self.env.context.get("install_mode"):
            return
        for subject in self:
            others = self.search([('code', '=', subject.code), ('id', '!=', subject.id)])
            if not others:
                continue
            if not subject.study_ids or any(
                not other.study_ids or (other.study_ids & subject.study_ids) for other in others
            ):
                raise ValidationError(_("duplicated code!"))

    def _get_academic_category_id(self):
        """Attempts to obtain the ID of the category ems_category_academic. If it does not exist (e.g. data loading error), it returns False."""
        try:
            return self.env.ref('ems.ems_category_academic').id
        except ValueError:
            return False

    @api.model_create_multi
    def create(self, vals_list):
        categ_id = self._get_academic_category_id()
        for vals in vals_list:
            product_vals = {
                'name': vals.get('name', 'New Subject'),
                'default_code': vals.get('code', ''),
                'type': 'service',           
                'invoice_policy': 'order',
                'list_price': 0.0,
                'sale_ok': True,
                'purchase_ok': False,
                'ems_is_tutoria': vals.get('code', '').startswith(('T1_', 'T2_')),
            }
            if categ_id:
                product_vals['categ_id'] = categ_id

            new_product = self.env['product.product'].create(product_vals)
            
            vals['product_id'] = new_product.id

        return super(EmsSubject, self).create(vals_list)

    def write(self, vals):
        result = super(EmsSubject, self).write(vals)
        categ_id = self._get_academic_category_id()

        for subject in self:
            # A) Self-healing: create the linked product if it's missing.
            if not subject.product_id:
                product_vals = {
                    'name': subject.name,
                    'default_code': subject.code,
                    'type': 'service',
                    'invoice_policy': 'order',
                    'list_price': 0.0,
                    'sale_ok': True,
                    'purchase_ok': False,
                }
                if categ_id:
                    product_vals['categ_id'] = categ_id
                new_product = self.env['product.product'].create(product_vals)
                subject.write({'product_id': new_product.id})

            # B) Sync: keep the product in step with name/code changes.
            elif 'name' in vals or 'code' in vals:
                update_vals = {}
                if 'name' in vals:
                    update_vals['name'] = subject.name
                if 'code' in vals:
                    update_vals['default_code'] = subject.code
                    update_vals['ems_is_tutoria'] = subject.code.startswith(('T1_', 'T2_'))

                if update_vals:
                    subject.product_id.write(update_vals)

        return result

    @api.depends('internal_hours', 'external_hours')
    def _compute_total_hours(self):
        for subject in self:
            subject.total_hours = subject.internal_hours + subject.external_hours

    @api.depends('acronym', 'name')
    def _compute_display_name(self):
        for subject in self:
            subject.display_name = "%s: %s" % (subject.acronym, subject.name)
