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

    # For use with generic products, like fees that will be applied on levels.
    ems_level_ids = fields.Many2many(
        comodel_name='ems.level',
        relation='product_template_ems_level_rel',
        column1='product_template_id',
        column2='ems_level_id',
        string="Allowed Levels",
        help="Levels where this generic product is available (e.g. VET, Bachelor)."
    )    

    # Flag to know if it's a calculated fee
    ems_is_enrollment_fee = fields.Boolean(
        string="Is Enrollment Fee", 
        default=False,
        help="Check this if this product represents a calculated fee (e.g. Matricula). "
             "It triggers automatic price calculation logic."
    )

    # Unitary cost of a subject in this level to calculate the fee
    ems_subject_unit_cost = fields.Float(
        string="Subject Unit Cost",
        digits=(10, 2),
        default=0.0,
        help="Unit cost per subject (e.g. 65.00) used for fee calculation."
    )

    @api.depends('ems_subject_ids.study_ids')
    def _compute_ems_study_ids(self):
        for product in self:
            # We look for studies on all subjects related to this product.
            product.ems_study_ids = product.ems_subject_ids.mapped('study_ids')