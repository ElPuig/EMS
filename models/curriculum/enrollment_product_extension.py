# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    _description = "Expand the product object with a reverse link to the subject to collect the studies to which it belongs."

    # Creating a reverse link to the course
    # As the subject has a field called ‘product_id’, here we can see ‘which subject I am enrolled in’.
    ems_subject_ids = fields.One2many(
        'ems.subject', 
        'product_id', 
        string="Linked Subject"
    )

    # We automatically bring the studies for that subject.
    ems_study_ids = fields.Many2many(
        'ems.study', 
        string="Allowed Studies",
        compute='_compute_ems_study_ids',
        store=True # By saving it in BD, we can use it in domains and quick filters.
    )

    # Select as generic so that it can be included in all enrollments
    is_generic = fields.Boolean(
        string="Is Generic", 
        help="If checked, this product will appear in enrollments for ALL studies (e.g. Fees, Insurance).",
        default=False
    )

    @api.depends('ems_subject_ids.study_ids')
    def _compute_ems_study_ids(self):
        for product in self:
            # We look for studies on all subjects related to this product.
            product.ems_study_ids = product.ems_subject_ids.mapped('study_ids')