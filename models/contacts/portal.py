# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize

# Contact types that are (or were) a student: the only ones with family contacts.
STUDENT_LIKE_TYPES = ('student', 'applicant', 'alumni', 'withdrawal', 'expelled')


class ems_contact_portal(models.Model):
    _inherit = 'res.partner'

    # Issue #833: drives the warning at the top of the student form. Non-stored, like the form's
    # other banners (enrollment_slot_broken_count): it reads the family's emails and logins.
    portal_email_shared_with_family = fields.Boolean(
        string="Main email shared with the family",
        compute='_compute_portal_email_shared_with_family')

    @api.depends('email', 'contact_type', 'relation_all_ids')
    def _compute_portal_email_shared_with_family(self):
        for partner in self:
            partner.portal_email_shared_with_family = partner._ems_email_shared_with_family()

    def get_portal_students(self):
        """Returns the student partners this family contact may see on the portal.

        - If this partner is a family contact, returns its related students
          via the partner_multi_relation system, except the adult ones that
          have not authorized sharing with the family (auth_share). A family
          loses its child from the portal the day he turns 18, and gets him
          back, only to consult (_ems_portal_can_act_for), once he authorizes it.
          This is the single point every portal page reads the students from.
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
            return relations.mapped('other_partner_id').filtered(
                lambda student: not student.is_adult or student.auth_share).sorted('id')
        return self

    def _ems_revoke_student_portal(self):
        """Revoke portal access for this student/ex-student and its family.

        A family member keeps its access if it still has another enrolled child
        (sibling check); otherwise its access is revoked too. Reuses the sudo
        revoke path of ems.portal.access.wizard. Returns a summary dict
        {'revoked': [...], 'skipped': [...], 'issues': [...]} for the caller log.
        """
        self.ensure_one()
        summary = {'revoked': [], 'skipped': [], 'issues': []}

        def _revoke(partner):
            partner.filtered(lambda p: p._has_active_portal_user())._ems_apply_portal_access(
                'revoke', summary)

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

    def _ems_retire_graduate(self):
        """Revoke the portal of this graduate (and of its family, see _ems_revoke_student_portal)
        and archive it; Odoo refuses to archive a contact still linked to an active portal user, so
        one whose revoke failed is left active. Returns the issues to report."""
        self.ensure_one()
        issues = self._ems_revoke_student_portal()['issues']
        if self._has_active_portal_user():
            issues.append(_("%s: portal access could not be revoked, kept active") % self.display_name)
        else:
            self.write({'active': False})
        return issues

    def _ems_grant_student_portal(self):
        """Grant the portal to whoever gets it when this student is enrolled: the student, plus
        the family while a minor (_ems_portal_access_recipients, the portal access wizard's own
        rule). Used when a withdrawal registered by mistake is undone (issue #592). Returns a
        summary dict {'granted': [...], 'issues': [...]} for the caller's notification."""
        self.ensure_one()
        summary = {'granted': [], 'issues': []}
        recipients = self._ems_portal_access_recipients()
        for recipient in recipients.filtered(lambda r: not r.email):
            summary['issues'].append(_("%(student)s: recipient %(name)s has no email") % {
                'student': self.name, 'name': recipient.name})
        recipients.filtered('email')._ems_apply_portal_access('grant', summary)
        return summary

    def _ems_apply_portal_access(self, mode, summary):
        """Grant or revoke ('grant'/'revoke') the portal of every partner in self through the
        sudo path of ems.portal.access.wizard. Each partner it acts on is listed under
        summary['granted'] or summary['revoked']; a failure goes to summary['issues'] instead of
        raising, so one contact's problem does not abort the caller's whole batch."""
        wizard = self.env['ems.portal.access.wizard'].sudo().new({'mode': mode})
        done = 'granted' if mode == 'grant' else 'revoked'
        for partner in self:
            try:
                # A savepoint per contact: a failure must not leave half of its writes behind.
                with self.env.cr.savepoint():
                    result = wizard._apply_one(partner)
                if result == done:
                    summary[done].append(partner.display_name)
            except Exception as e:
                msg = e.args[0] if getattr(e, 'args', None) else str(e)
                summary['issues'].append('%s: %s' % (partner.display_name, msg))

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
        """Whether this portal partner may only consult the student he is looking at
        (get_portal_student) rather than act for him (_ems_portal_can_act_for): a minor on his
        own account, a family looking at an adult child who authorized sharing with it, or a
        family with no child left to see. Enrollment, authorizations, convalidations and
        documentation are hidden and refused to him (controllers/portal_view_only.py)."""
        self.ensure_one()
        return not self._ems_portal_can_act_for(self.get_portal_student())

    def _ems_portal_can_act_for(self, student):
        """Whether this portal partner may act on the student's behalf: whoever the centre
        contacts on his behalf (_ems_notification_recipients) - the student himself when adult,
        or the minor applicant with no family on file; the family while he is a minor.
        A student with no birth date counts as a minor. A family never acts for itself, which
        is what get_portal_student() returns when it has no child left to see."""
        self.ensure_one()
        if not student:
            return False
        if student == self:
            if self.contact_type == 'family':
                return False
            return self.contact_type not in ('student', 'applicant') \
                or self in self._ems_notification_recipients()
        return student in self.get_portal_students() \
            and self in student._ems_notification_recipients()

    def _ems_convalidation_can_request(self, student):
        """Whether this portal partner may file (and follow up) convalidation requests for the
        student - a rule of its own, narrower and wider than _ems_portal_can_act_for (issue #529):

        - a minor never files them himself, only his family; a minor with no family contact on
          file cannot have any filed until someone fills that contact in;
        - an adult files them himself, and so does his family when he authorized sharing with
          it (auth_share), which is exactly when get_portal_students() shows him to it."""
        self.ensure_one()
        if not student or student.contact_type not in ('student', 'applicant'):
            return False
        if student.is_adult:
            return self == student or (self.contact_type == 'family' and student in self.get_portal_students())
        return self != student and self in student._ems_family_contacts()

    def _ems_convalidation_portal_visible(self):
        """Whether the portal shows this partner the Convalidations page for the student he is
        looking at: whoever may request them, and the student himself, who at least reads his
        own requests (and is told why he cannot file one when he is a minor)."""
        self.ensure_one()
        student = self.get_portal_student()
        return student.contact_type in ('student', 'applicant') \
            and (student == self or self._ems_convalidation_can_request(student))

    def _ems_informed_recipients(self):
        """Whoever is kept informed about this student (convalidations, issue #529; Erasmus+
        results and place offers; ex officio withdrawal, issue #726): the student always, and his
        family too while he is a minor or when he authorized sharing with it (auth_share).
        Informing only: acting or signing for him is _ems_notification_recipients' rule."""
        self.ensure_one()
        if self.is_adult and not self.auth_share:
            return self
        return self | self._ems_family_contacts()

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

    # ------------------------------------------------------------------
    # A student sharing the main email with the family (issue #833)
    # ------------------------------------------------------------------
    def _ems_email_shared_with_family(self):
        """Whether this student's main email is also a family member's (their email, or their
        portal user's login): at enrolment the centre often gets a single address for the whole
        family. A portal login is unique, and the one with that email is the family's; the
        student signs in with the corporate account instead (_ems_portal_login)."""
        self.ensure_one()
        email = email_normalize(self.email)
        if not email or self.contact_type not in STUDENT_LIKE_TYPES or not self._origin.id:
            return False
        family = self._origin._ems_family_contacts()
        addresses = set(family.mapped('email_normalized'))
        addresses.update(map(email_normalize, family.with_context(active_test=False).sudo().user_ids.mapped('login')))
        return email in addresses

    def _ems_portal_login(self, email=None):
        """Login of this partner's portal user: their main email (or `email`, the one typed in
        Odoo's own portal wizard), except for a student sharing it with the family, who gets the
        corporate email; False while that student has none yet."""
        self.ensure_one()
        if self._ems_email_shared_with_family():
            return email_normalize(self.student_email) or False
        return email_normalize(email or self.email) or False

    def _ems_check_portal_login(self):
        """Refuse, with a message saying why, a portal user for a student sharing the email with
        the family while the corporate account that gives them their own login doesn't exist."""
        self.ensure_one()
        if not self._ems_portal_login() and self._ems_email_shared_with_family():
            raise UserError(_(
                "%s has the same main email as their family, so that login is the family's. They "
                "will get portal access with their corporate email when their Google account is "
                "created.") % self.name)

    def _ems_sync_portal_login(self):
        """Realign each partner's portal user's login with _ems_portal_login(), unless another
        user already holds it. Revoking access archives the user with its old login, and Odoo
        reactivates it without refreshing the login, so a changed email (or a student who must
        hand the shared email back to the family) would never take effect otherwise."""
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        for partner in self:
            user = partner.sudo().with_context(active_test=False).user_ids.filtered('share')[:1]
            login = partner._ems_portal_login()
            if not user or not login or email_normalize(user.login) == login:
                continue
            if not Users.search_count([('login', '=', login), ('id', '!=', user.id)]):
                user.write({'login': login})

    def _ems_students_sharing_email(self):
        """For a family member: the related students whose main email is this family member's
        too (each of them signs in with the corporate email, never with this one)."""
        self.ensure_one()
        email = email_normalize(self.email)
        if not email or self.contact_type != 'family':
            return self.browse()
        return self.env['res.partner.relation.all'].sudo().search([
            ('this_partner_id', '=', self.id),
            ('other_partner_id.contact_type', 'in', STUDENT_LIKE_TYPES),
            ('other_partner_id.email_normalized', '=', email),
        ]).mapped('other_partner_id')

    def _ems_grant_portal_with_corporate_email(self):
        """Grant the portal to a student left without it because their main email is the
        family's, now that the corporate email gives them a login of their own. Only when the
        family already has portal access, which is how the centre granted it for this student;
        never to one with a user already (an archived one means access was revoked). Returns
        the summary of _ems_apply_portal_access, or None when there was nothing to do."""
        self.ensure_one()
        if self.sudo().with_context(active_test=False).user_ids \
                or not self._ems_email_shared_with_family() \
                or not any(member._has_active_portal_user() for member in self._ems_family_contacts()):
            return None
        summary = {'granted': [], 'issues': []}
        self._ems_apply_portal_access('grant', summary)
        return summary

    @api.model
    def _ems_students_sharing_email_with_family(self):
        """Every student (or ex-student) whose main email is also a family member's, for the
        migration that fixes the existing portals (18.0.0.49.3)."""
        family_emails = self.with_context(active_test=False).search([
            ('contact_type', '=', 'family'), ('email_normalized', '!=', False),
        ]).mapped('email_normalized')
        candidates = self.with_context(active_test=False).search([
            ('contact_type', 'in', STUDENT_LIKE_TYPES),
            ('email_normalized', 'in', family_emails),
        ])
        return candidates.filtered(lambda student: student._ems_email_shared_with_family())

    def _ems_fix_shared_email_portals(self):
        """Bring the portals of these students sharing the email with the family to the issue
        #833 rule, for installations that granted them before it: a student holding the shared
        login moves to the corporate one and the family members they kept out are granted; a
        student left without a user gets one with the corporate login. Returns the summary
        {'granted': [...], 'issues': [...]} for the migration's log."""
        summary = {'granted': [], 'issues': []}
        for student in self.filtered(lambda partner: partner._ems_email_shared_with_family()):
            student._ems_sync_portal_login()
            if student._has_active_portal_user():
                family = (student._ems_notification_recipients() - student).filtered(
                    lambda member: member.email
                    and not member.sudo().with_context(active_test=False).user_ids)
                family._ems_apply_portal_access('grant', summary)
            else:
                result = student._ems_grant_portal_with_corporate_email()
                if result:
                    summary['granted'] += result['granted']
                    summary['issues'] += result['issues']
        return summary

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

    def _ems_portal_birth_date(self, value):
        """The birth date typed on the portal when confirming an enrollment (issue #640), or
        False when it is missing or not a plausible one: a day in the past, and no more than
        100 years ago (a typo in the year, not a real student)."""
        try:
            birth_date = fields.Date.to_date(value) if value else False
        except ValueError:
            return False
        today = self.env['ems.datetime_utils'].get_local_today()
        if not birth_date or not today - relativedelta(years=100) < birth_date < today:
            return False
        return birth_date

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
