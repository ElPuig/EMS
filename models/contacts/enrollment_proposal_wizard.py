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
    dest_study_id = fields.Many2one(
        'ems.study', related='template_id.ems_study_id', string='Destination study')
    ems_group_id = fields.Many2one(
        'ems.group', string='Destination group',
        domain="[('study_id', '=', dest_study_id)]",
        help="Suggested group written to every generated enrollment. Leave empty to "
             "let each student get its own suggested group.")

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
                lambda p: p.contact_type in ('student', 'applicant')
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
            # Applicant intake: preselect the first-course template so the secretary
            # only reviews (the destination group is filled by _onchange_suggest_group).
            if students and all(p.contact_type == 'applicant' for p in students):
                first_template = templates.sorted('study_year')[:1]
                if first_template:
                    res['template_id'] = first_template.id
        return res

    @api.onchange('template_id', 'student_ids')
    def _onchange_suggest_group(self):
        """Pre-fill the destination group. Applicants: the first group of the shared
        pre-enrollment shift. Continuing students: the same letter+shift when they all
        share the current group (a proposal is usually launched over one group)."""
        self.ems_group_id = False
        if not (self.template_id and self.student_ids):
            return
        applicants = self.student_ids.filtered(lambda p: p.contact_type == 'applicant')
        if applicants:
            shifts = set(applicants.mapped('preinscription_shift'))
            if len(shifts) == 1:
                self.ems_group_id = self._ems_suggested_group(applicants[0], self.template_id)
            return
        groups = self.student_ids.mapped('main_group_id')
        if len(self.student_ids) == 1 or len(groups) == 1:
            self.ems_group_id = self._ems_suggested_group(
                self.student_ids[0], self.template_id)

    def _ems_suggested_group(self, partner, template):
        """Suggest a destination group for a proposed enrollment.

        - Continuing student: keep the same letter and shift in the destination
          course (SMX1A -> SMX2A); empty if there is no single match.
        - Applicant (new intake): the lowest-letter group of the destination course
          matching the pre-enrollment shift (the 'A' group always exists; tutors
          redistribute the extra groups in September).
        """
        Group = self.env['ems.group']
        study = template.ems_study_id
        course = template.study_year
        if not (study and course):
            return Group
        if partner.contact_type == 'applicant':
            domain = [('study_id', '=', study.id), ('course', '=', course)]
            if partner.preinscription_shift:
                domain.append(('shift', '=', partner.preinscription_shift))
            return Group.search(domain, order='acronym', limit=1)
        current = partner.main_group_id
        if not current:
            return Group
        domain = [
            ('study_id', '=', study.id),
            ('course', '=', course),
            ('acronym', '=', current.acronym),
        ]
        if current.shift:
            domain.append(('shift', '=', current.shift))
        matches = Group.search(domain)
        return matches if len(matches) == 1 else Group

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

            group = self.ems_group_id or self._ems_suggested_group(student, self.template_id)
            shift = student.main_group_id.shift or student.preinscription_shift
            order = self.env['sale.order'].create({
                'partner_id': student.id,
                'ems_study_id': student.study_id.id if student.study_id else False,
                'ems_course_id': current_course.id if current_course else False,
                'shift': shift,
                'ems_group_id': group.id if group else False,
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
