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

    def _ems_family_contacts(self):
        """Family contacts related to this student, empty if none is on file.

        sudo() because res.partner.relation.all is not readable by the portal users that
        reach this through get_portal_inner_circle_ids(), and because a tutor granting
        access to their own students has no rights on it either.
        """
        self.ensure_one()
        return self.env['res.partner.relation.all'].sudo().search([
            ('this_partner_id', '=', self.id),
            ('other_partner_id.contact_type', '=', 'family'),
        ]).mapped('other_partner_id')

    def _ems_notification_recipients(self):
        """Partners that should be contacted on this student's behalf - portal credentials,
        an authorization sent during the course, anything addressed to "the student" that a
        minor's family must receive instead.

        - Adult (student or applicant) -> himself (uses his main `email`).
        - Minor with family contacts -> those family contacts, whether he is a
          student or an applicant. An ex-student coming back is an applicant of the
          study he is heading to (sale.order._ems_offer_to_ex_student), and his family
          relations survived the withdrawal, so the family is known and is who must
          be contacted, exactly as for any other minor.
        - Minor applicant with no family contact -> himself. This is the applicant
          straight from a GEDAC preinscription: the family contacts are genuinely not
          known yet, so his personal `email` is the only address available.
        - Minor student with no family contact -> nobody; the callers
          (ems.portal.access.wizard, ems.authorization.send.wizard) report it as an issue.

        Lives here rather than on either wizard because both need the identical rule -
        see docs/en/developers/contacts/portal_access_wizard.md.
        """
        self.ensure_one()
        if self.is_adult:
            return self
        family = self._ems_family_contacts()
        if family or self.contact_type != 'applicant':
            return family
        return self

    def _ems_portal_access_recipients(self):
        """Partners that get a portal account for this student: whoever acts on his behalf
        (_ems_notification_recipients) plus the student himself. A minor gets an account of his
        own too, to look at his schedule and the messages addressed to him, while his family
        keeps managing everything else (_ems_portal_is_view_only)."""
        self.ensure_one()
        return self._ems_notification_recipients() | self

    def _ems_portal_is_view_only(self):
        """Whether this portal partner is a student looking at his own account without being
        the one who acts for himself: a minor with a family on file, or a minor student with
        none at all. Enrollment, authorizations, convalidations and documentation are hidden
        and refused to him. The one minor who does act for himself is the applicant straight
        from a GEDAC preinscription with no family on file (_ems_notification_recipients)."""
        self.ensure_one()
        return self.contact_type in ('student', 'applicant') \
            and self not in self._ems_notification_recipients()

    def _ems_portal_can_act_for(self, student):
        """Whether this portal partner may act on the student's behalf: the student himself when
        nobody else does it for him (_ems_portal_is_view_only), or his family while he is a
        minor. A student with no birth date counts as a minor. Portal access is granted along
        the same line (_ems_portal_access_recipients), but not kept in step with it: a family
        keeps its account when the student turns 18."""
        self.ensure_one()
        if not student:
            return False
        if student == self:
            return not student._ems_portal_is_view_only()
        return not student.is_adult and student in self.get_portal_students()

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
        return [self.id] + self._ems_family_contacts().ids

    def get_portal_authorizations(self):
        """Every authorization addressed to this student for the courses that are live for
        them - the one being taught and the one being enrolled into - whether it came through
        an enrollment or was sent on its own during the school year (issue #443).

        Read from partner_id rather than from the enrollment precisely because the second
        kind has no enrollment: the running course's enrollment is confirmed and closed by
        the time those are sent, which is why they exist at all.

        sudo() for the same reason as every other helper here: a family's portal user does
        not own its child's records.

        Usage in controllers:
            authorizations = student.get_portal_authorizations()
        """
        self.ensure_one()
        Course = self.env['ems.course']
        courses = Course.search(['|', ('is_current', '=', True),
                                 ('is_enrollment_default', '=', True)])
        return self.env['ems.authorization'].sudo().search([
            ('partner_id', '=', self.id),
            ('course_id', 'in', courses.ids),
        ], order='course_id desc, id')

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
