# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize
from ..shared import base
import datetime
import re
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

class EmsStudentBenefit(models.Model):
    _name = 'ems.student.benefit'
    _description = 'Student Benefits and Exemptions'
    _order = 'student_id, benefit_type'

    student_id = fields.Many2one('res.partner', string="Student", required=True, ondelete='cascade')
    
    benefit_type = fields.Selection([
        # Bonificaciones
        ('large_family_gen', 'Large Family (General)'),
        ('single_parent_gen', 'Single Parent (General)'),
        ('scholarship', 'Ministry Scholarship'),
        # Exenciones
        ('large_family_spec', 'Large Family (Special)'),
        ('single_parent_spec', 'Single Parent (Special)'),
        ('disability', 'Disability (>33%)'),
        ('other', 'Other Exemption')
    ], string="Type", required=True)
    
    category = fields.Selection([
        ('bonification', 'Bonification (Partial)'),
        ('exemption', 'Exemption (Total)')
    ], string="Category", compute="_compute_category", store=True)

    document = fields.Binary(string="Document", required=True)
    document_name = fields.Char(string="File Name")
    renewal_date = fields.Date(string="Renewal/Review Date")
    notes = fields.Char(string="Notes")

    @api.depends('benefit_type')
    def _compute_category(self):
        for benefit in self:
            if not benefit.benefit_type:
                # If no type is selected, there is no Bonification or Exemption.
                benefit.category = False
            elif benefit.benefit_type in ['large_family_gen', 'single_parent_gen', 'scholarship']:
                benefit.category = 'bonification'
            else:
                benefit.category = 'exemption'

    @api.onchange('benefit_type')
    def _onchange_benefit_type(self):
        if self.benefit_type:
            today = fields.Date.today()
            
            # Scholarship case: 9 months
            if self.benefit_type == 'scholarship':
                self.renewal_date = today + relativedelta(months=9)
            # Other cases: 2 years
            else:
                self.renewal_date = today + relativedelta(years=2)

class ResPartner(models.Model):
    _inherit = ['res.partner'] # NOTE: unable to inherit also from ems.base, I got an error like 'TypeError: Many2many fields ResPartner.channel_ids and res.partner.channel_ids use the same table and columns'.
            
    # view-oriented fields:
    # level_id and study_id are used for form view purposes (linked dropdowns: level > study > group) and will be computed on save.
    level_id = fields.Many2one(string='Level', comodel_name='ems.level')    
    study_id = fields.Many2one(string='Studies', comodel_name='ems.study') 
    # readonly=True (bug found 2026-09-06): a related field is only auto-readonly when its
    # target is itself readonly or when 'store' would need an inverse Odoo can't build. Since
    # neither applied here, Odoo silently auto-generated a write-through inverse - editing this
    # field from a student's own form would have actually reassigned that student's WHOLE
    # GROUP's tutor (main_group_id.tutor_id), for every one of its students, not just a display
    # value scoped to this one student. It's purely a read-only mirror of the group's own tutor;
    # to actually change a tutor, edit it on the ems.group record.
    tutor_id = fields.Many2one(string='Tutor', related="main_group_id.tutor_id", readonly=True) # Related field: auto-computed and auto-refreshed within the form.
    
    # model-data fields:
    main_group_id = fields.Many2one(string='Main Group', comodel_name='ems.group')
    enrollment_ids = fields.One2many(string='Enrollment', comodel_name='ems.enrollment', inverse_name='student_id')
    strike_ids = fields.One2many(string='Strikes', comodel_name='ems.strike', inverse_name='student_id')
    strike_count = fields.Integer(string='Strike count', compute='_compute_strike_count')
    # Study granted at pre-enrollment (GEDAC), for a student the centre already has:
    # the internal continuer changing studies next course (ESO4 -> SMX1). Only active
    # students use it -- an applicant's destination already lives in study_id, which is
    # free because it has no current study. Always read it via _ems_destination_study().
    preinscription_study_id = fields.Many2one(
        comodel_name='ems.study', string='Preinscription study',
        help="Study granted by the preinscription (GEDAC) for the next course. Only set "
             "on students already enrolled in another study; an applicant keeps its "
             "granted study in the study field.")
    # Shift granted at pre-enrollment (GEDAC/preinscription), stored on the applicant
    # who still has no group to derive it from. Consumed by the enrollment proposal to
    # pre-fill the enrollment shift and pick the destination group.
    preinscription_shift = fields.Selection(
        selection=[('morning', 'Morning'), ('afternoon', 'Afternoon')],
        string='Preinscription shift',
        help="Shift granted to the applicant at pre-enrollment (before having a group).")
    # Course the applicant is admitted into, from the preinscription. Lets the
    # enrollment proposal preselect the right-course template (some applicants join
    # directly beyond 1st course) and lets the intake list group by course. Covers
    # up to 4th course (ESO); FP/BTX only use 1st-2nd.
    preinscription_course = fields.Selection(
        selection=[('1', '1r'), ('2', '2n'), ('3', '3r'), ('4', '4t')],
        string='Preinscription course',
        help="Course granted to the applicant at pre-enrollment (1st to 4th).")
    # Special educational needs (NEE) typology, as reported by the preinscription
    # ("Tipus alumne"). Sensitive data: the ORM `groups` restrict it to tutors,
    # secretary and admin, and it is never rendered on the portal. Empty = ordinary.
    special_needs = fields.Selection(
        selection=[('nee_a', 'NEE-A'), ('nee_b', 'NEE-B')],
        string='Special educational needs',
        groups='ems.group_tutor,ems.group_secretary,ems.group_academic_admin',
        help="Special educational needs typology from the preinscription: type A "
             "(disability, ASD, serious behavioural/developmental/mental disorders); "
             "type B (specially disadvantaged socio-economic or socio-cultural "
             "situation). Leave empty for ordinary students.")
    # Contact lifecycle: applicant -> student -> alumni (graduated at least once)
    #                                         \-> withdrawal (never graduated)
    #                                         \-> expelled (permanently expelled).
    # The ~25 domains filtering by contact_type == 'student' exclude applicant,
    # alumni, withdrawal and expelled automatically (no changes needed elsewhere).
    contact_type = fields.Selection(string='Contact Type', selection=[
        ('provider', 'Provider'),
        ('student', 'Student'),
        ('family', 'Family'),
        ('applicant', 'Applicant'),
        ('alumni', 'Alumni'),
        ('withdrawal', 'Withdrawal'),
        ('expelled', 'Expelled'),
    ])
    # Permanent graduation mark: set to True when the graduation is registered and
    # never reset to False. It is the key that decides alumni vs withdrawal in
    # _ems_convert_to_ex_student() (an explicit 'expulsion' kind overrides both).
    has_graduated = fields.Boolean(string="Has graduated", default=False)
    # Exit metadata (written by the graduation/withdrawal wizards).
    exit_type = fields.Selection([
        ('graduation', 'Graduation'),
        ('withdrawal', 'Withdrawal'),
        ('expulsion', 'Expulsion'),
    ], string="Exit type")
    exit_course_id = fields.Many2one('ems.course', string="Exit course")
    exit_date = fields.Date(string="Exit date")
    exit_reason = fields.Text(string="Exit reason")
    # Academic history: one frozen record per course (see models/grades/year_record.py).
    year_record_ids = fields.One2many(string="Academic history",
                                      comodel_name='ems.student.year_record',
                                      inverse_name='student_id')
    # Derived transition state (not stored). Consumed by the "no destination" report.
    transition_status = fields.Selection([
        ('enrolled', 'Enrolled next course'),
        ('unplaced', 'Enrolled without group'),
        ('graduated', 'Graduated'),
        ('former', 'Former student'),
        ('missing', 'No destination'),
    ], string="Transition status", compute='_compute_transition_status',
        search='_search_transition_status', store=False)
    # Backs the "My students" search facet the Students action applies by default (issue #421).
    # Never rendered as a field in any view - it exists so the facet has something to search on.
    is_my_student = fields.Boolean(string="Taught by me", compute='_compute_is_my_student',
        search='_search_is_my_student', store=False)
    # Feeds the shared 'ems_archived_reason_ribbon' field widget (form + kanban, same widget
    # used by hr.employee's departure_reason_id - see static/src/js/backend/
    # archived_reason_ribbon_field.js). Empty/False when there's nothing specific to show
    # (not archived, or archived with no specific lifecycle reason - family/provider/applicant).
    archived_reason_label = fields.Char(string="Archived reason", compute='_compute_archived_reason')
    archived_reason_color = fields.Char(string="Archived reason color", compute='_compute_archived_reason')
    family_relation = fields.Char(string="Family relation")
    document_id = fields.Char(string="Document ID")
    passport_id = fields.Char(string="Passport")
    student_email = fields.Char(string="Student email")	
    student_id = fields.Char(string="Student ID")
    medical_id = fields.Char(string="Medical ID")
    nuss = fields.Char(string="NUSS")

    @api.constrains('nuss')
    def _check_nuss(self):
        for partner in self:
            if partner.nuss and not re.fullmatch(r'\d{12}', partner.nuss):
                raise ValidationError(_("The NUSS must be exactly 12 numeric digits."))
    birth_date = fields.Date(string="Birth Date")
    birth_country_id = fields.Many2one(string="Birth Country", comodel_name='res.country')
    citizenship_id =  fields.Many2one(string="Citizenship", comodel_name='res.country')
    auth_image = fields.Boolean(string="Image Rights", compute="_compute_auth_booleans", store=True)
    auth_trip  = fields.Boolean(string="Scholar Trips", compute="_compute_auth_booleans", store=True)
    auth_healt = fields.Boolean(string="Health Data", compute="_compute_auth_booleans", store=True)
    auth_share = fields.Boolean(string="Share with family", compute="_compute_auth_booleans", store=True, help="If marked, the student (even if adult) allows to share its educational information with its family.")
    
    car_plate = fields.Char(string="Car Plate")
    is_adult = fields.Boolean(string="Adult", compute="_compute_is_adult", store=False)
    wpi_enrolled = fields.Boolean(string="WPI enrolled")

    document_ids = fields.One2many('ems.student.document', 'partner_id', string='Documents')

    selected_student_id = fields.Many2one(
        'res.partner',
        string='Selected student (portal)',
        domain=[('contact_type', '=', 'student')],
        ondelete='set null',
    )

    # Fields to store student Benefits:
    benefit_ids = fields.One2many(string='Benefits & Exemptions', comodel_name='ems.student.benefit', inverse_name='student_id')
    benefit_status = fields.Selection([
        ('none', 'None'),
        ('bonification', 'Bonification'),
        ('exemption', 'Exemption')
    ], string="Benefits", compute="_compute_benefit_status", store=True)

    ems_authorization_ids = fields.Many2many(
        'ems.authorization',
        compute='_compute_ems_authorization_ids',
        string='Authorizations'
    )

    ems_current_enrollment_id = fields.Many2one(
        'sale.order',
        string='Current Enrollment',
        compute='_compute_current_enrollment',
        store=False,
        search='_search_current_enrollment',
    )
    ems_enrollment_state = fields.Selection(related='ems_current_enrollment_id.state', store=False, string='Enrollment State')

    # NOTE: this field is computed when loaded within a form or list
    read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)
    is_tutor_readonly = fields.Boolean(default=lambda self:self._get_is_tutor_readonly(), store=False)
    # Drives the Studies tab's "saving will move this student's enrollments" warning
    # (issue #395) - unlike the two booleans above, this one must react live to an
    # on-screen, not-yet-saved edit of main_group_id, so it needs a real compute/depends,
    # not the default()-only idiom (which only ever evaluates once, at load time).
    main_group_pending_change = fields.Boolean(compute='_compute_main_group_pending_change', store=False)

    def _ems_enrollment_in_force(self):
        """The student's enrollment that governs what may be done with them now.

        What rules an authorization is the year being TAUGHT, not the one being
        enrolled into, so the running course comes first. The fallback exists for the
        one window where that yields nothing: between transitioning a study and the
        global flip, the student has already been moved into the incoming course and
        holds no enrollment for the outgoing one — which is exactly what left 122 of
        122 SMX students showing every signed authorization as unsigned.

        Preferring the enrollment-default course instead would break later on: once
        27-28 is opened for enrolment halfway through 26-27, the flags would start
        reading a draft enrollment nobody has signed yet and fall back to false in
        the middle of the school year.

        Shared with ems_current_enrollment_id so the two cannot drift apart, which is
        how the discrepancy arose in the first place.
        """
        self.ensure_one()
        Course = self.env['ems.course']
        running = Course.search([('is_current', '=', True)], limit=1)
        orders = self.sale_order_ids.filtered(
            lambda order: order.state in ('draft', 'sent', 'sale'))
        in_force = orders.filtered(lambda order: order.ems_course_id == running)
        if in_force:
            return in_force[0]
        enrolling = Course.search([('is_enrollment_default', '=', True)], limit=1)
        return orders.filtered(lambda order: order.ems_course_id == enrolling)[:1]

    @api.depends(
    'sale_order_ids.ems_course_id',
    'sale_order_ids.ems_authorization_ids.status',
    'sale_order_ids.ems_authorization_ids.template_id.auth_type',
    )
    def _compute_auth_booleans(self):
        for student in self:
            image, trip, health, share = False, False, False, False
            for order in student._ems_enrollment_in_force():
                for auth in order.ems_authorization_ids:
                    if auth.status == 'yes':
                        if auth.template_id.auth_type == 'image':
                            image = True
                        elif auth.template_id.auth_type == 'trip':
                            trip = True
                        elif auth.template_id.auth_type == 'health':
                            health = True
                        elif auth.template_id.auth_type == 'share':
                            share = True
            student.auth_image = image
            student.auth_trip = trip
            student.auth_healt = health
            student.auth_share = share        

    @api.depends('sale_order_ids.ems_course_id', 'sale_order_ids.state',
                 'sale_order_ids.ems_authorization_ids')
    def _compute_ems_authorization_ids(self):
        # Same enrollment the flags above read, so the Secretary tab cannot show an
        # empty list next to a green badge: both come from _ems_enrollment_in_force().
        for partner in self:
            partner.ems_authorization_ids = \
                partner._ems_enrollment_in_force().ems_authorization_ids

    def _search_current_enrollment(self, operator, value):
        return [('sale_order_ids.name', operator, value)]

    def _compute_current_enrollment(self):
        for partner in self:
            partner.ems_current_enrollment_id = partner._ems_enrollment_in_force()

    def action_open_current_enrollment(self):
        self.ensure_one()
        if not self.ems_current_enrollment_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.ems_current_enrollment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_strikes(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_strike_list')
        action['domain'] = [('student_id', '=', self.id)]
        action['context'] = {}
        return action

    def action_new_enrollment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.id,
                'default_ems_study_id': self.study_id.id if self.study_id else False,
                'default_shift': (self.main_group_id.shift if self.main_group_id
                                  else self.preinscription_shift),
            }
        }

    def action_enrollment_proposal(self):
        students = self.filtered(lambda p: p.contact_type in ('student', 'applicant'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enrollment proposal'),
            'res_model': 'ems.enrollment_proposal_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': students.ids,
            },
        }

    def action_portal_access_bulk(self):
        """Open the bulk portal-access wizard for the selected students/applicants.

        Lives here rather than inline in the `action_portal_access_bulk` server
        action because safe_eval's context has no `_`, so a translatable error
        message is only possible from real Python (an inline `_(...)` raised a
        NameError that masked the real "nothing selected" cause).
        """
        students = self.filtered(lambda p: p.contact_type in ('student', 'applicant'))
        if not students:
            raise UserError(_(
                "Please select at least one student or applicant. Send their new "
                "enrollment to a withdrawal or a graduate and they become an "
                "applicant, which is what allows granting portal access; confirming "
                "that enrollment then makes them a student again."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Portal access'),
            'res_model': 'ems.portal.access.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': students.ids},
        }

    def action_graduation_wizard(self):
        students = self.filtered(lambda p: p.contact_type == 'student')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Graduation'),
            'res_model': 'ems.graduation_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': students.ids},
        }

    def action_withdrawal_wizard(self):
        students = self.filtered(lambda p: p.contact_type == 'student')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Withdrawal'),
            'res_model': 'ems.withdrawal_wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {'active_ids': students.ids},
        }

    def action_suggest_destination_group(self):
        """Fill the destination group on the selected students' next-course
        enrollments that still have none. Students without an enrollment are
        skipped (there is no matrícula to place). Used from the "students without
        destination" report."""
        enrollments = self.mapped('ems_current_enrollment_id')
        filled = enrollments._ems_fill_suggested_group()
        skipped = len(self.filtered(lambda p: not p.ems_current_enrollment_id))
        message = _("%(filled)s destination group(s) filled.", filled=filled)
        if skipped:
            message += " " + _("%(skipped)s skipped (no enrollment).", skipped=skipped)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Suggest destination group"),
                'message': message,
                'type': 'success',
                'sticky': False,
                # Without this the list keeps showing the rows as they were, which
                # reads as if nothing had happened. 'soft_reload' restores the very
                # same controller (action.restore), so the search filters, the
                # group-by and the search panel all survive; the row selection does
                # not, because the records are read again.
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.depends('contact_type', 'exit_type', 'sale_order_ids.ems_course_id',
                 'sale_order_ids.state', 'sale_order_ids.ems_group_id')
    def _compute_transition_status(self):
        next_course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)
        for partner in self:
            if partner.contact_type in ('alumni', 'withdrawal', 'expelled'):
                partner.transition_status = 'former'
            elif partner.exit_type == 'graduation':
                # A still-active student with a graduation mark is a pending graduate
                # (once executed it becomes alumni, caught by 'former' above).
                partner.transition_status = 'graduated'
            else:
                enrollment = next_course and self.env['sale.order'].search([
                    ('partner_id', '=', partner.id),
                    ('ems_course_id', '=', next_course.id),
                    ('state', '!=', 'cancel')], limit=1)
                if not enrollment:
                    # No next-course enrollment at all.
                    partner.transition_status = 'missing'
                elif enrollment.ems_group_id:
                    partner.transition_status = 'enrolled'
                else:
                    # Enrolled but not placeable yet (no destination group).
                    partner.transition_status = 'unplaced'

    def _search_transition_status(self, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError(_("Unsupported search on transition_status"))
        # Only lifecycle contacts can have a transition status.
        candidates = self.search([('contact_type', 'in', ['student', 'alumni', 'withdrawal', 'expelled'])])
        matching = candidates.filtered(lambda p: p.transition_status == value)
        positive = (operator == '=')
        return [('id', 'in' if positive else 'not in', matching.ids)]

    def _ems_my_students_domain(self):
        """Domain matching the students of the current user's own groups, shared by the
        compute and the search below so the two can never disagree (issue #421).

        Returns an EMPTY domain - not a domain matching nothing - for a user with no groups
        at all, so administration and secretariat are not filtered even though the Students
        action applies the facet to them too. An ir.actions.act_window's context is a string
        evaluated client-side and has no ORM access, so it cannot decide per user whether to
        add 'search_default_my_students'; making the search inert for those users is what
        keeps that action a plain act_window. See the developer doc for the full rationale.
        """
        employee = self.env.user.sudo().employee_id
        groups = employee._get_own_groups() if employee else self.env['ems.group']
        if not groups:
            return []
        # Two branches, deliberately of different width.
        #
        # 'main_group_id' covers the groups themselves: everyone whose main group is one of
        # mine, whatever they happen to be enrolled in there.
        #
        # ems.enrollment covers the students who reach one of my groups WITHOUT it being their
        # main one - a reinforcement group (nobody's main group is a reinforcement one, its
        # students are attached through ems.enrollment only) and a repeater carrying a failed
        # subject down into a lower course's group. Matching those by group alone was too wide
        # (found 2026-09-09 by a teacher of SMX1A/SMX1B, who was shown 19 students of SMX2A and
        # SMX2B whose only link was some other teacher's subject taught in SMX1A/SMX1B): what
        # actually makes such a student mine is the exact (group, subject) pair I teach, the
        # ternary ems.enrollment mirrors from ems.teaching. Only 4 of those 19 survive the pair
        # match, which are precisely the repeaters sitting in one of this teacher's own classes.
        #
        # The pair match is built from 'teaching_ids' alone, not from 'groups': a group that is
        # only in scope because the employee tutors it (no ems.teaching row) contributes no
        # subject of theirs, and its own tutorands are already covered by the branch above.
        #
        # active_test=False because the Students action itself runs with it: archived alumni and
        # withdrawals must stay reachable once the 'students_only' facet is removed.
        pairs = {(teaching.group_id.id, teaching.subject_id.id)
                 for teaching in employee.teaching_ids}
        enrolled = self.env['ems.enrollment'].sudo().with_context(active_test=False).search([
            ('group_id', 'in', [group_id for group_id, _subject_id in pairs]),
            ('subject_id', 'in', [subject_id for _group_id, subject_id in pairs]),
        ]).filtered(lambda enrollment: (enrollment.group_id.id, enrollment.subject_id.id) in pairs)
        return ['|', ('main_group_id', 'in', groups.ids), ('id', 'in', enrolled.student_id.ids)]

    @api.depends('main_group_id')
    def _compute_is_my_student(self):
        mine = self.filtered_domain(self._ems_my_students_domain())
        for partner in self:
            partner.is_my_student = partner in mine

    def _search_is_my_student(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(_("Unsupported search on is_my_student"))
        domain = self._ems_my_students_domain()
        if (operator == '=') == value:
            return domain
        # Negated: with no groups every student is "mine", so "not mine" matches nobody.
        return ['!'] + domain if domain else [('id', '=', False)]

    @api.depends('contact_type')
    def _compute_archived_reason(self):
        # Fixed color constants (confirmed with the developer 2026-08-01) - 'expelled' is
        # deliberately left with no color, falling back to the widget's own default red, same
        # reasoning as leaving hr.departure.reason's "Fired" record uncolored (see
        # docs/en/developers/contacts/contact.md). Labels use _() directly rather than reading
        # contact_type's own selection metadata, since that isn't translated by plain attribute
        # access (only _description_selection(env) is) - simpler to just translate here.
        reasons = {
            'alumni': (_("Alumni"), '#4C7A5D'),
            'withdrawal': (_("Withdrawal"), '#C97B3D'),
            'expelled': (_("Expelled"), False),
        }
        for partner in self:
            label, color = reasons.get(partner.contact_type, (False, False))
            partner.archived_reason_label = label
            partner.archived_reason_color = color

    @api.depends('benefit_ids', 'benefit_ids.category')
    def _compute_benefit_status(self):
        for partner in self:
            if not partner.benefit_ids:
                partner.benefit_status = 'none'
            else:
                categories = partner.benefit_ids.mapped('category')
                # Priority 1: If there is an exemption, the status will be Exemption.
                if 'exemption' in categories:
                    partner.benefit_status = 'exemption'
                # Priority 2: If there is a bonus, the status will be Exemption.
                elif 'bonification' in categories:
                    partner.benefit_status = 'bonification'
                # If there are lines but no defined category
                else:
                    partner.benefit_status = 'none'

    @api.depends('strike_ids')
    def _compute_strike_count(self):
        for partner in self:
            partner.strike_count = len(partner.strike_ids)

    @api.depends('birth_date')
    def _compute_is_adult(self):
        for partner in self:
            partner.is_adult = bool(partner.birth_date) and (
                relativedelta(datetime.date.today(), partner.birth_date).years >= 18)

    @api.depends('main_group_id')
    def _compute_main_group_pending_change(self):
        # '_origin' is the persisted (last-saved) record even while 'main_group_id' itself
        # holds an on-screen, not-yet-saved edit - the same distinction the actual write()
        # cascade (_migrate_enrollments_on_group_change) makes between the old and new group,
        # just evaluated live in the form instead of at save time.
        for partner in self:
            old_group = partner._origin.main_group_id
            partner.main_group_pending_change = bool(
                old_group and partner.main_group_id and old_group != partner.main_group_id)

    @api.onchange('level_id')
    def _onchange_level_id(self):
        for partner in self:
            partner.study_id = False

    @api.onchange('study_id')
    def _onchange_study_id(self):
        for partner in self:
            partner.main_group_id = False
     
    @api.model_create_multi
    def create(self, values):
        # Fired when the model is created (Source: https://www.cybrosys.com/blog/how-to-override-create-write-and-unlink-methods-in-odoo-17)
        # NOTE: values is a list of dicts (method fired only once)
        # Auto-place a brand-new student the same way write() already does for an EXISTING
        # one on a study_id change (see write()'s own 'study_refresh_candidates' block for the
        # full rationale) - mirrored entry-by-entry here instead of recordset-wide, since
        # create() never has a "previous main_group_id" to compare against: every study_id
        # given at create time is inherently a first placement, so - unlike write() - an
        # explicit main_group_id given alongside it is never excluded here: there is no
        # "previous group" a create() could ever be migrating enrollments away FROM. Same
        # two remaining exclusions as write(): not self.env.su (system flows) and a
        # non-'student' contact_type (applicant_import_wizard). student_import_wizard stays
        # excluded too, since it never sets study_id in the first place.
        is_su = self.env.su
        study_refresh_flags = []
        for entry in values:
            is_candidate = not is_su and 'study_id' in entry and entry.get('contact_type') == 'student'
            study_refresh_flags.append(is_candidate)
            if is_candidate and not entry.get('main_group_id'):
                entry['main_group_id'] = self._ems_auto_group_for_study(entry.get('study_id')).id

            self._compute_group_data(entry)

            # NOTE: I don't know why, but the 'contact_type' value does not arrive for contact data (contact within student
            #       form) so the value will be manually setup here.
            if 'parent_id' in entry and entry['parent_id']:
                parent = self.env['res.partner'].browse(entry['parent_id'])
                if parent.contact_type == 'student':
                    entry['contact_type'] = 'family'
                elif parent.contact_type == 'provider':
                    entry['contact_type'] = 'provider'

        contact = super(ResPartner, self).create(values)
        contact._sync_category()

        # zip() relies on api.model_create_multi's guaranteed order-preservation between the
        # input values and the returned recordset.
        study_refresh_candidates = self.browse(
            record.id for record, is_candidate in zip(contact, study_refresh_flags) if is_candidate)
        if study_refresh_candidates:
            study_refresh_candidates._ems_refresh_enrollments_from_template()

        # Google Workspace: enqueue account creation for brand-new students without
        # a corporate email yet (skips CSV imports of existing students that already have one).
        # Google Workspace: enqueue account creation only when the student has all
        # the required data (covers mass imports created with full data at once).
        contact._gw_enqueue_if_ready()

        return contact

    def write(self, values):
        # Fired when the model is updated (Source: https://www.cybrosys.com/blog/how-to-override-create-write-and-unlink-methods-in-odoo-17)
        # Note: values is a dict (method fired once per entry)
        # Capture (before the write) the students/families whose main email is about
        # to change while they hold active portal access: their access must be moved
        # from the old email to the new one (see _apply_portal_email_change).
        portal_email_changed = self.env['res.partner']
        if 'email' in values:
            new_email = email_normalize(values.get('email'))
            portal_email_changed = self.filtered(
                lambda p: p.contact_type in ('student', 'family')
                and email_normalize(p.email) != new_email
                and p._has_active_portal_user())
        # Capture (before the write) the previous main group of every partner about to
        # change it, so their subject enrollments in that group can follow them to the new
        # one (see _migrate_enrollments_on_group_change below). Skipped under env.su: that
        # flag is what tells apart an interactive group change (tutor/admin/secretary on the
        # form, or a bulk re-import) from a system flow acting on the user's behalf, chiefly
        # sale.order._ems_apply_destination_placement() (course transition / enrollment
        # placement), which moves a student to a new group ON PURPOSE without touching the
        # outgoing group's enrollments - those are the ending year's history, not something
        # to repoint. Same env.su vs. env.user distinction already used for the same reason
        # in ems.enrollment.default_get().
        old_main_groups = {}
        if 'main_group_id' in values and not self.env.su:
            old_main_groups = {partner.id: partner.main_group_id for partner in self}

        # Refresh ems.enrollment from the matching enrollment template whenever a
        # student's study_id actually changes interactively (see
        # _ems_refresh_enrollments_from_template). Scoped narrowly on purpose:
        # - 'not self.env.su': excludes system flows acting on the user's behalf that
        #   already resolve their own group/subjects, chiefly sale.order.
        #   _ems_apply_destination_placement() (always writes main_group_id and
        #   study_id together, so it never matches this branch anyway) - same
        #   env.su distinction already used for old_main_groups above and in
        #   ems.enrollment.default_get().
        # - contact_type == 'student' (effective, after this same write): excludes
        #   applicants (applicant_import_wizard, the course transition wizard's pending
        #   graduates) which also write study_id without a group, on purpose - they are
        #   not placed yet, so there is nothing to enroll them into.
        # - An explicit main_group_id in the same write is only excluded when the partner
        #   ALREADY had a group before this write (a genuine group change, not a first
        #   placement): that case is handled by the pre-existing old_main_groups/
        #   _migrate_enrollments_on_group_change mechanism above instead, which repoints
        #   the OLD (same-study) enrollments into the new group. A partner with NO
        #   previous group has nothing to migrate FROM, so the template refresh runs
        #   anyway, using the explicitly given group instead of auto-picking one - found
        #   the hard way (issue #455 follow-up): filling Studies then Main Group before
        #   the very first save is the normal way to place a new/unplaced student, and
        #   used to silently produce zero enrollments.
        study_refresh_candidates = self.env['res.partner']
        if 'study_id' in values and not self.env.su:
            new_study_id = values.get('study_id')
            new_group_id = values.get('main_group_id')
            study_refresh_candidates = self.filtered(
                lambda partner: values.get('contact_type', partner.contact_type) == 'student'
                and partner.study_id.id != new_study_id
                and (not new_group_id or not partner.main_group_id)
            )
            if study_refresh_candidates and not new_group_id:
                # Resolved explicitly either way (a found group, or False) rather than left
                # as whatever it already was: otherwise a direct write() bypassing the form's
                # own _onchange_study_id (which clears it client-side) would leave main_group_id
                # stuck on a group belonging to the OLD study - the exact "incongruence between
                # main_group, level and studies" _compute_group_data already guards against for
                # every other path. See _ems_auto_group_for_study() for how the group is picked.
                values['main_group_id'] = self._ems_auto_group_for_study(new_study_id).id

        self._compute_group_data(values)
        contact = super(ResPartner, self).write(values)
        if 'contact_type' in values:
            self._sync_category()

        if old_main_groups:
            self._migrate_enrollments_on_group_change(old_main_groups)

        if study_refresh_candidates:
            study_refresh_candidates._ems_refresh_enrollments_from_template()

        for partner in portal_email_changed:
            partner._apply_portal_email_change()

        # Google Workspace: with form autosave the student is created with partial
        # data; enqueue once the required fields are completed (deduplicated).
        self._gw_enqueue_if_ready()

        # Google Workspace: when the birth date arrives/changes on a student that
        # already has an account, re-place it in the minor/adult OU accordingly
        # (accounts created without a birth date start in the minors OU).
        if 'birth_date' in values:
            self._gw_enqueue_relocate()

        # Google Workspace: archive -> schedule the suspension after a grace period
        # (issue #388); unarchive -> call it off, or reactivate if the cron got there
        # first and the account is already suspended.
        if 'active' in values:
            if values['active']:
                self._gw_cancel_scheduled_deactivation()
                self._gw_enqueue_reactivate()
            else:
                self._gw_schedule_deactivation()

        return contact

    def toggle_active(self):
        """Archiving one or several students opens the withdrawal wizard instead
        of archiving directly, mirroring hr.employee (archiving asks for a reason
        via hr.departure.wizard) — from the list (single or multi-selection) or
        from the form, same as the "Withdrawal" button. Unlike the employee flow
        — which archives first and only then attaches an optional reason — the
        student is archived by the wizard itself once confirmed (see
        EmsWithdrawalWizard.action_apply): withdrawal already changes more state
        atomically (contact_type, operational records, portal) than a bare
        active flip, so none of it may run before the reason is captured, and
        nothing should happen at all if the wizard is cancelled.
        """
        students = self.filtered(lambda p: p.contact_type == 'student' and p.active)
        if students and not self.env.context.get('no_wizard'):
            others = self - students
            if others:
                others.toggle_active()
            return students.action_withdrawal_wizard()
        return super().toggle_active()

    @api.onchange('email')
    def _onchange_email_portal_warning(self):
        """Inform the user, before saving, that changing the main email of a
        contact with portal access will move that access to the new email."""
        if self.contact_type in ('student', 'family') and self._has_active_portal_user():
            return {
                'warning': {
                    'title': _("Portal access will be updated"),
                    'message': _(
                        "Changing the main email revokes the portal access linked to "
                        "the old email and sends a new portal invitation to the new "
                        "email. Discard the change if you don't want this."),
                }
            }

    def _has_active_portal_user(self):
        """True when the partner has a non-archived portal user (access enabled now)."""
        self.ensure_one()
        return any(u._is_portal() for u in self.user_ids)

    def _apply_portal_email_change(self):
        """Move portal access from the old email to the partner's current email.

        Reuses the EMS portal access wizard so the (already tested) revoke + grant
        path runs, including the login/email resync done in _sync_user_login. Runs
        with sudo because tutors lack rights over res.users.
        """
        self.ensure_one()
        wizard = self.env['ems.portal.access.wizard'].sudo().new({'mode': 'revoke'})
        wizard._apply_one(self)
        wizard.mode = 'grant'
        wizard._apply_one(self)
        self._post_portal_email_change_message()

    def _post_portal_email_change_message(self):
        """Log the email change as a portal-visible comment on the related student(s).

        The portal "communications" page lists messages addressed to the student
        (partner_ids) and excludes internal notes, so we post a comment targeting
        each student. For a family contact, that means every related student.
        """
        self.ensure_one()
        if self.contact_type == 'student':
            students = self
        else:
            students = self.relation_all_ids.other_partner_id.filtered(
                lambda p: p.contact_type == 'student')
        body = _(
            "The main email of %(name)s has changed to %(email)s. The portal access "
            "has been updated accordingly: the previous access has been revoked and a "
            "new invitation has been sent to the new email.") % {
                'name': self.display_name, 'email': self.email}
        for student in students:
            student.sudo().message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=student.ids,
            )

    def _ems_destination_study(self):
        """Study these contacts are heading to next course.

        Hides the storage asymmetry between the two ways in: the internal continuer
        keeps its current study in study_id, so its GEDAC destination needs a field of
        its own, while an applicant has no current study and already holds the granted
        one in study_id. Everything reasoning about "where is this contact going" must
        go through here instead of reading either field directly.
        """
        return self.mapped(lambda partner: partner.preinscription_study_id or partner.study_id)

    def _ems_convert_to_student(self):
        """Convert applicants or ex-students back into active students.

        Invoked by the sale.order confirmation (applicant admission), the
        transition wizard and the final Esfer@ re-import. Clears the exit
        metadata but never touches has_graduated, which is a permanent mark.
        Unarchives: an ex-student converted back is by definition active again,
        and _ems_convert_to_ex_student() is what archived it in the first place.
        """
        self.write({
            'active': True,
            'contact_type': 'student',
            'exit_type': False,
            'exit_course_id': False,
            'exit_date': False,
            'exit_reason': False,
        })

    def _ems_convert_to_ex_student(self, kind=None):
        """Convert students into alumni, withdrawal or expelled.

        With no explicit `kind`, a partner who has graduated from any study at least
        once becomes alumni forever; one who never graduated becomes a withdrawal
        (unchanged, existing behaviour for every caller that doesn't pass `kind`).
        Passing `kind='expulsion'` overrides that entirely - an expelled student is
        never alumni regardless of has_graduated. In every case the student is
        detached from its group/level/study so it no longer occupies a place. Used
        by the withdrawal wizard (immediate) and the transition wizard.
        """
        for partner in self:
            if kind == 'expulsion':
                new_contact_type = 'expelled'
            else:
                new_contact_type = 'alumni' if partner.has_graduated else 'withdrawal'
            partner.write({
                'contact_type': new_contact_type,
                'main_group_id': False,
                'level_id': False,
                'study_id': False,
            })
            # Schedule the corporate Google account's suspension (issue #388): the
            # student is warned now and the account is only suspended once the grace
            # period runs out. sudo: the secretary running the withdrawal has no rights
            # over the mail template / queue job. Guarded internally by
            # google_ws_enabled and student_email.
            partner.sudo()._gw_schedule_deactivation()

    def _ems_clear_operational_records(self):
        """Delete the operational records of a student leaving the centre.

        Called ONLY after the academic history has been frozen (ems.student.year_record):
        the history keeps what the student studied, the grades per learning outcome and the
        attendance rate, so the live records have nothing left to say. Leaving them behind is
        what makes an ex-student keep showing up where they no longer belong: enrolled in the
        group's subjects, in the evaluation matrix, in the attendance sessions still to be
        taken, or as the group's delegate.

        sudo: the secretary running the withdrawal has no write rights over grades or
        attendance, but detaching a student who has left is a legitimate system cleanup.
        Used by the withdrawal wizard (immediate) and, later, by the transition wizard.
        """
        for partner in self:
            group = partner.main_group_id
            # Subject enrollments: without this the student stays in group.enrolled_student_ids
            # and grade_session.fill_students() would put them back in every new round.
            # ems_bypass_grade_guard: this withdrawal flow runs AFTER the academic history has
            # already been frozen (see docstring above) and deliberately clears the live grade
            # lines itself right below, so ems.enrollment.unlink()'s usual "has scored grades"
            # guard must not block it here.
            self.env['ems.enrollment'].sudo().with_context(ems_bypass_grade_guard=True).search(
                [('student_id', '=', partner.id)]).unlink()
            # Grade lines of the live sessions (the grades are copied in the year record).
            self.env['ems.grade_outcome_line'].sudo().search(
                [('student_id', '=', partner.id)]).unlink()
            self.env['ems.grade_subject_line'].sudo().search(
                [('student_id', '=', partner.id)]).unlink()
            # Attendance lines (the attendance rate is copied in the year record).
            self.env['ems.attendance_session_line'].sudo().search(
                [('student_id', '=', partner.id)]).unlink()
            # Attendance schedule lines: student_ids is a materialised M2m, never recomputed.
            # Moved from ems.attendance_template.student_ids (removed) 2026-08-11 - see
            # plans/calendar_driven_attendance_templates.md, point 1.
            schedules = self.env['ems.attendance_schedule'].sudo().search(
                [('student_ids', 'in', partner.id)])
            schedules.student_ids = [(3, partner.id)]
            # Attendance issues: the year record already froze attendance_issue_count, so
            # the live notifications have nothing left to say about a student who has gone.
            # Dropping its rows can leave a tutor notification with no student at all;
            # remove_if_empty() disposes of it and cancels its pending queue job.
            issue_students = self.env['ems.attendance_issue_student'].sudo().search(
                [('student_id', '=', partner.id)])
            tutor_issues = issue_students.attendance_issue_tutor_id
            issue_students.unlink()
            for tutor_issue in tutor_issues.exists():
                tutor_issue.remove_if_empty()
            partner._ems_clear_stale_delegate(group)

    def _ems_clear_stale_delegate(self, group):
        """Clears 'group.delegate_id' if it still points at one of these partners, who is no
        longer actually a member of it. Shared by '_ems_clear_operational_records()' above (a
        student leaving the centre entirely) and course_transition_wizard._apply_detach_unplaced()
        (a student stranded with no placement target, e.g. the last cohort of a finishing cycle) -
        both leave a student's OWN group behind without the group record itself going anywhere
        (groups are reused across years), so only the now-invalid delegate reference needs
        clearing, never the group. Must be called with 'group' captured BEFORE 'main_group_id'
        is written away - once cleared, there is nothing left to read it from."""
        for partner in self:
            if group.delegate_id == partner:
                group.sudo().delegate_id = False

    def _sync_category(self):
        # The "student" category doubles as the shared student-lifecycle marker: the
        # four lifecycle types (student, applicant, alumni, withdrawal) all carry it,
        # so the family-relation conditions (right side = student category) stay valid
        # through every transition, while family/provider never get it (no
        # family-to-family relations). Ex-students and applicants additionally carry
        # their own distinctive tag.
        student = self.env.ref('ems.partner_category_student')
        category_map = {
            'student': student,
            'family': self.env.ref('ems.partner_category_family'),
            'provider': self.env.ref('ems.partner_category_provider'),
            'applicant': student | self.env.ref('ems.partner_category_applicant'),
            'alumni': student | self.env.ref('ems.partner_category_alumni'),
            'withdrawal': student | self.env.ref('ems.partner_category_withdrawal'),
            'expelled': student | self.env.ref('ems.partner_category_expelled'),
        }
        all_managed = self.env['res.partner.category']
        for categories in category_map.values():
            all_managed |= categories
        for record in self:
            categories = category_map.get(record.contact_type)
            if categories:
                record.category_id = (record.category_id - all_managed) | categories

    @api.model
    def _ems_resync_lifecycle_categories(self):
        """Re-tag applicants and ex-students so they carry the shared student
        category the family-relation conditions rely on. Idempotent; invoked from a
        data <function> on upgrade to heal partners created before the shared marker."""
        partners = self.search([('contact_type', 'in', ('applicant', 'alumni', 'withdrawal', 'expelled'))])
        partners._sync_category()

    def _migrate_enrollments_on_group_change(self, old_main_groups):
        """For each partner whose main group actually changed (old_main_groups maps
        partner id -> its previous main_group_id, captured before write()), moves its
        subject enrollments from the old group to the new one - see
        ems.enrollment._ems_move_group(). A partner with no previous group (a first
        placement) or whose group ended up unchanged is skipped: there is nothing to
        move."""
        Enrollment = self.env['ems.enrollment']
        for partner in self:
            old_group = old_main_groups.get(partner.id)
            if old_group and partner.main_group_id and old_group != partner.main_group_id:
                Enrollment._ems_move_group(partner, old_group, partner.main_group_id)

    def _ems_refresh_enrollments_from_template(self):
        """Regenerates each student's ems.enrollment lines from the enrollment template
        matching its (new) study + main group's course - called by write() right after
        an interactive study_id change (see there for the exact gating). Mirrors the
        subject/group resolution sale.order._ems_apply_destination_placement() already
        uses (same product->subject lookup, same _ems_equivalent_for_course() fallback
        for a subject taught in a different course), so both flows land on the same
        result for the same template. Idempotent: an existing (student, group, subject)
        already matching the template is left untouched.

        A student with no main_group_id (the new study has no group yet) is skipped
        without error - nothing to enroll into. A stale enrollment (not part of the new
        template) is removed unless the student already has scored grades on it, in
        which case it is left alone and reported via a chatter note.
        """
        Enrollment = self.env['ems.enrollment'].sudo()
        GradeSession = self.env['ems.grade_session']
        for student in self:
            group = student.main_group_id
            if not group:
                continue
            template = self.env['sale.order.template']._ems_find_for(student.study_id, group.course)
            if not template:
                continue

            new_pairs = set()
            for subject in self.env['ems.subject'].sudo().search([
                ('product_id', 'in', template.sale_order_template_line_ids.product_id.ids)
            ]):
                subject_course = student.study_id._ems_subject_course(subject.product_id)
                subject_group = group
                if subject_course and subject_course != group.course:
                    subject_group = group._ems_equivalent_for_course(subject_course) or group
                new_pairs.add((subject_group.id, subject.id))
                if not Enrollment.search_count([
                    ('student_id', '=', student.id), ('group_id', '=', subject_group.id), ('subject_id', '=', subject.id)
                ]):
                    Enrollment.create({'student_id': student.id, 'group_id': subject_group.id, 'subject_id': subject.id})

            stale = Enrollment.search([('student_id', '=', student.id)]).filtered(
                lambda enrollment: (enrollment.group_id.id, enrollment.subject_id.id) not in new_pairs)
            kept_with_grades = stale.filtered(
                lambda enrollment: GradeSession._ems_has_scored_grades(
                    student.id, enrollment.group_id.id, enrollment.subject_id.id))
            (stale - kept_with_grades).unlink()
            if kept_with_grades:
                intro = _(
                    "The study change refreshed this student's enrollments from the "
                    "%(template)s template, but the following subjects already have "
                    "grades and were kept as-is:",
                    template=template.display_name,
                )
                items = kept_with_grades.mapped(
                    lambda enrollment: f"{enrollment.subject_id.display_name} ({enrollment.group_id.display_name})")
                student.message_post(body=Markup("<p>{}</p>").format(intro) + base.EmsBase.build_html_list(self, items))

    @api.model
    def _ems_auto_group_for_study(self, study_id):
        """First ems.group alphabetically for the given study (or an empty recordset if
        study_id is falsy or no group exists yet for it) - no course filter needed: a main
        group's own name is built as study.acronym + course + acronym (see
        ems.group._compute_name), so ordering by name within the study already lands on its
        lowest course first. Shared by write()'s and create()'s own study_id-driven
        main_group_id auto-placement - see both callers for the full placement rationale."""
        if not study_id:
            return self.env['ems.group']
        return self.env['ems.group'].search([('study_id', '=', study_id)], order='name', limit=1)

    def _compute_group_data(self, values):
        # Avoids incongruences between the main_group, level and studies.     
        if 'main_group_id' in values and values.get('main_group_id'):   
            group = self.env["ems.group"].search([("id", "=", values.get('main_group_id'))]) or False                 
            values["level_id"] = group.level_id.id
            values["study_id"] = group.study_id.id

        elif 'study_id' in values and values.get('study_id'):
            study = self.env["ems.study"].search([("id", "=", values.get('study_id'))]) or False            
            values["level_id"] = study.level_id.id

    def _get_read_only_user(self):
        is_admin = base.EmsBase.get_user_is_admin(self)
        is_secretary = base.EmsBase.get_user_is_secretary(self)
        is_head_of_studies = base.EmsBase.get_user_is_head_of_studies(self)
        return not (is_admin or is_secretary or is_head_of_studies or self._user_is_tutor_of_record())

    def _user_is_tutor_of_record(self):
        # True when the current user is a tutor of this student, or a tutor of a
        # student related to this family contact (so tutors can also edit the
        # profiles of their students' parents/legal guardians).
        tutors = self.env.user.employee_ids.filtered(lambda t: t.tutorship_ids)
        if not tutors:
            return False
        if self.tutor_id in tutors:
            return True
        related_tutors = self.relation_all_ids.other_partner_id.tutor_id
        return bool(related_tutors & tutors)

    def _get_is_tutor_readonly(self):
        # True only when the user is a tutor of this student and NOT admin/secretary/HoS.
        # Used to make non-contact fields read-only for tutors while admin/secretary/HoS
        # keep full edit access.
        is_admin = base.EmsBase.get_user_is_admin(self)
        is_secretary = base.EmsBase.get_user_is_secretary(self)
        is_head_of_studies = base.EmsBase.get_user_is_head_of_studies(self)
        if is_admin or is_secretary or is_head_of_studies:
            return False
        for t in self.env.user.employee_ids:
            if t.id != False and len(t.tutorship_ids) > 0:
                if self.tutor_id == t:
                    return True
        return False

    def open_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.id,
            'view_id': self.env.ref('ems.view_contact_form').id,
            'view_mode': 'form',
        }

    def action_open_relation_wizard(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.id,
            'street': self.street,
            'street2': self.street2,
            'city': self.city,
            'state_id': self.state_id.id,
            'zip': self.zip,
            'country_id': self.country_id.id,
        })
        return {
            'name': 'New student contact',
            'type': 'ir.actions.act_window',
            'res_model': 'ems.contact.relation.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }