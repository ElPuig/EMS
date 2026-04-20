# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class EmsEnrollmentProposalWizard(models.TransientModel):
    _name = 'ems.enrollment_proposal_wizard'
    _description = 'Enrollment proposal wizard'

    student_ids = fields.Many2many('res.partner', string='Students')
    template_id = fields.Many2one('sale.order.template', string='Enrollment template', required=True)
    available_template_ids = fields.Many2many(
        'sale.order.template',
        compute='_compute_available_templates',
        string='Available templates',
    )

    @api.depends('student_ids')
    def _compute_available_templates(self):
        for wizard in self:
            if not wizard.student_ids:
                wizard.available_template_ids = False
                continue
            studies = wizard.student_ids.mapped('study_id')
            courses = wizard.student_ids.mapped('main_group_id.course')
            min_course = min(courses) if courses else 1
            wizard.available_template_ids = self.env['sale.order.template'].search([
                ('ems_study_id', 'in', studies.ids),
                ('study_year', '>=', min_course),
            ])

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            students = self.env['res.partner'].browse(active_ids).filtered(
                lambda p: p.contact_type == 'student'
            )
            studies = students.mapped('study_id')
            if len(studies) > 1:
                raise UserError(_(
                    "Selected students belong to different studies. "
                    "Please select students from the same group."
                ))
            courses = students.mapped('main_group_id.course')
            min_course = min(courses) if courses else 1
            templates = self.env['sale.order.template'].search([
                ('ems_study_id', 'in', studies.ids),
                ('study_year', '>=', min_course),
            ])
            if not templates:
                raise UserError(_(
                    "No enrollment templates available for the selected students' study."
                ))
            res['student_ids'] = [fields.Command.set(students.ids)]
        return res

    def action_create_enrollments(self):
        self.ensure_one()
        current_course = self.env['ems.course'].search(
            [('is_enrollment_default', '=', True)], limit=1
        )
        if not current_course:
            current_course = self.env['ems.course'].search(
                [('is_current', '=', True)], limit=1
            )

        created = 0
        skipped = 0
        for student in self.student_ids:
            existing = self.env['sale.order'].search([
                ('partner_id', '=', student.id),
                ('ems_course_id', '=', current_course.id if current_course else False),
                ('state', 'not in', ['cancel']),
            ], limit=1)
            if existing:
                skipped += 1
                continue

            order = self.env['sale.order'].create({
                'partner_id': student.id,
                'ems_study_id': student.study_id.id if student.study_id else False,
                'ems_course_id': current_course.id if current_course else False,
                'shift': student.main_group_id.shift if student.main_group_id else False,
                'sale_order_template_id': self.template_id.id,
            })
            order._onchange_sale_order_template_id()
            order.apply_authorizations()
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Enrollments created'),
                'message': _('%d created, %d skipped (already had enrollment).') % (created, skipped),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
