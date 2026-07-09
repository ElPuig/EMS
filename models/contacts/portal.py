# -*- coding: utf-8 -*-

from odoo import models


class ems_contact_portal(models.Model):
    _inherit = 'res.partner'

    def get_portal_students(self):
        """Returns all student partners related to this family contact.

        - If this partner is a family contact, returns all related students
          via the partner_multi_relation system.
        - Otherwise, returns self as a single-element recordset.

        Uses sudo() because portal users don't have direct access to
        res.partner.relation.all via record rules.

        Usage in controllers:
            students = request.env.user.partner_id.get_portal_students()
        """
        self.ensure_one()
        if self.contact_type == 'family':
            relations = self.env['res.partner.relation.all'].sudo().search([
                ('this_partner_id', '=', self.id),
                ('other_partner_id.contact_type', '=', 'student'),
            ])
            return relations.mapped('other_partner_id').sorted('id')
        return self

    def _ems_revoke_student_portal(self):
        """Revoke portal access for this student/ex-student and its family.

        A family member keeps its access if it still has another enrolled child
        (sibling check); otherwise its access is revoked too. Reuses the sudo
        revoke path of ems.portal.access.wizard. Returns a summary dict
        {'revoked': [...], 'skipped': [...], 'issues': [...]} for the caller log.
        """
        self.ensure_one()
        wizard = self.env['ems.portal.access.wizard'].sudo().new({'mode': 'revoke'})
        summary = {'revoked': [], 'skipped': [], 'issues': []}

        def _revoke(partner):
            if not partner._has_active_portal_user():
                return
            try:
                if wizard._apply_one(partner) == 'revoked':
                    summary['revoked'].append(partner.display_name)
            except Exception as e:
                msg = e.args[0] if getattr(e, 'args', None) else str(e)
                summary['issues'].append('%s: %s' % (partner.display_name, msg))

        # 1. The student/ex-student's own portal user (typically adult students).
        _revoke(self)

        # 2. Family contacts: revoke only if they have no other still-enrolled child.
        Relation = self.env['res.partner.relation.all'].sudo()
        families = Relation.search([
            ('this_partner_id', '=', self.id),
            ('other_partner_id.contact_type', '=', 'family'),
        ]).mapped('other_partner_id')
        for member in families:
            other_students = Relation.search([
                ('this_partner_id', '=', member.id),
                ('other_partner_id.contact_type', '=', 'student'),
                ('other_partner_id.active', '=', True),
                ('other_partner_id', '!=', self.id),
            ])
            if other_students:
                summary['skipped'].append(member.display_name)
                continue
            _revoke(member)
        return summary

    def get_portal_student(self, student_id=None):
        """Returns the student partner for this partner.

        - If student_id is provided, validates it belongs to this family
          contact before returning it. Falls back to the first student
          if not valid.
        - If this partner is not a family contact, returns self.

        Usage in controllers:
            student = request.env.user.partner_id.get_portal_student()
            student = request.env.user.partner_id.get_portal_student(student_id=78)
        """
        self.ensure_one()
        if self.contact_type == 'family':
            students = self.get_portal_students()
            if not students:
                return self
            if student_id:
                try:
                    sid = int(student_id)
                except (TypeError, ValueError):
                    sid = None
                if sid:
                    match = students.filtered(lambda s: s.id == sid)
                    if match:
                        return match[0]
            # Fall back to the persisted selection, then first student
            if self.selected_student_id and self.selected_student_id in students:
                return self.selected_student_id
            return students[0]
        return self

    def get_portal_inner_circle_ids(self):
        """Returns partner IDs considered 'own side' in portal chats:
        the student itself plus any related family contacts.

        Caller must ensure self is a student partner (typically obtained
        via get_portal_student()).
        """
        self.ensure_one()
        relations = self.env['res.partner.relation.all'].sudo().search([
            ('this_partner_id', '=', self.id),
            ('other_partner_id.contact_type', '=', 'family'),
        ])
        return [self.id] + relations.mapped('other_partner_id').ids

    def get_portal_enrollment_ids(self):
        """Returns all sale order IDs for this student in the portal context.

        Uses sudo() because family members need access to the student's sale orders.
        The caller is responsible for ensuring self is a valid student partner
        (typically obtained via get_portal_student()).

        Usage in controllers:
            sale_order_ids = student.get_portal_enrollment_ids()
        """
        self.ensure_one()
        return self.env['sale.order'].sudo().search(
            [('partner_id', '=', self.id)],
            limit=100,
        ).ids

    def get_portal_enrollment(self, course):
        """Returns the active enrollment for this student in the portal context.

        Uses sudo() because family members (contact_type='family') need access
        to the student's sale orders, which are not owned by their portal user.
        The caller is responsible for ensuring self is a valid student partner
        (typically obtained via get_portal_student()).

        Usage in controllers:
            enrollment = student.get_portal_enrollment(current_course)
        """
        self.ensure_one()
        return self.env['sale.order'].sudo().search([
            ('partner_id', '=', self.id),
            ('state', 'in', ['sent', 'sale']),
            ('ems_course_id', '=', course.id if course else False),
        ], limit=1)
