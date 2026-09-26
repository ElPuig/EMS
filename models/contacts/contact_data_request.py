# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize

from ..shared import base

# Fields a student or family may review from the portal (issue #507). Name and birth date are
# official data and stay read-only there: their correction keeps going through the secretariat.
STUDENT_FIELDS = ('mobile', 'phone', 'email', 'street', 'zip', 'city',
                  'document_id', 'passport_id', 'medical_id', 'nuss')
FAMILY_FIELDS = ('firstname', 'lastname', 'mobile', 'email', 'document_id', 'passport_id',
                 'street', 'zip', 'city')
ADDRESS_FIELDS = ('street', 'zip', 'city')
PHONE_FIELDS = ('mobile', 'phone')
DNI_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE'
REQUEST_GROUPS = 'ems.group_tutor,ems.group_secretary,ems.group_head_of_studies,ems.group_academic_admin'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # groups=: the requests are only readable by the staff who send and review them (see
    # security/ir.model.access.csv). Without it, reading any student as a plain teacher would
    # prefetch these fields and fail on the missing access - the issue #492 trap.
    contact_data_request_ids = fields.One2many(
        'ems.contact.data.request', 'student_id', string='Contact data requests',
        groups=REQUEST_GROUPS)
    contact_data_request_state = fields.Selection(
        selection=lambda self: self.env['ems.contact.data.request']._fields['state'].selection,
        string='Contact data', compute='_compute_contact_data_request_state',
        groups=REQUEST_GROUPS)

    @api.depends('contact_data_request_ids.state')
    def _compute_contact_data_request_state(self):
        # The latest request's status, shown on the student's smart button.
        for partner in self:
            partner.contact_data_request_state = partner.contact_data_request_ids[:1].state

    def action_contact_data_request_bulk(self):
        """Open the contact data request assistant for the selected students/applicants - a
        server action binding, like action_authorization_send_bulk(), for the same reason: a
        translatable message is only possible from real Python."""
        students = self.filtered(lambda partner: partner.contact_type in ('student', 'applicant'))
        if not students:
            raise UserError(_("Please select at least one student or applicant."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Request contact data"),
            'res_model': 'ems.contact.data.request.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': students.ids, 'active_model': 'res.partner',
                        'default_target': 'students', 'default_only_incomplete': False},
        }

    def action_open_contact_data_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_ems_contact_data_request')
        action['domain'] = [('student_id', '=', self.id)]
        action['context'] = {'create': False}
        return action

    def _ems_portal_contact_data_student(self):
        """The student or applicant whose contact data this portal partner may review and send:
        the one it is looking at (get_portal_student) when it acts for them
        (_ems_portal_can_act_for). Nobody for a view-only account - a minor on their own account,
        a family looking at an adult child - nor for a family with no child left to see."""
        self.ensure_one()
        student = self.get_portal_student()
        if student.contact_type in ('student', 'applicant') and self._ems_portal_can_act_for(student):
            return student
        return self.browse()

    def _ems_contact_data_requested(self):
        """Whether this student has a contact data request still waiting for an answer this
        academic year - the portal home shows a banner for it. sudo: asked on behalf of a portal
        user, who has no rights on the requests."""
        self.ensure_one()
        return bool(self.env['ems.contact.data.request'].sudo().search_count([
            ('student_id', '=', self.id),
            ('course_id', '=', self._ems_running_course().id),
            ('state', '=', 'pending'),
        ]))

    def _ems_contact_data(self):
        """This student's reviewable data, in the shape the portal form posts it back:
        {'student': {field: value}, 'family': [{'key', 'id', 'name', 'relation', fields...}]}.
        sudo: read on behalf of a portal user, who has no rights on the relations."""
        self.ensure_one()
        student = self.sudo()
        data = {
            'student': {field: student[field] or '' for field in STUDENT_FIELDS},
            'family': [],
        }
        relations = self.env['res.partner.relation.all'].sudo().search([
            ('this_partner_id', '=', self.id),
            ('other_partner_id.contact_type', '=', 'family'),
        ])
        for relation in relations:
            family = relation.other_partner_id
            entry = {field: family[field] or '' for field in FAMILY_FIELDS}
            # A contact typed in as a single name keeps it in `name` only.
            entry['firstname'] = family.firstname or ('' if family.lastname else family.name or '')
            entry.update({
                'key': f'f{family.id}',
                'id': family.id,
                'name': family.name,
                'relation_type_id': relation.type_id.id,
                'relation': relation.type_id.name,
                'remove': False,
            })
            data['family'].append(entry)
        return data

    def _ems_contact_data_missing(self):
        """What is still missing from this student's contact data, as readable messages - the
        same rules the portal form enforces (ems.contact.data.request._ems_contact_data_problems),
        so a request is only sent to whoever actually needs one."""
        self.ensure_one()
        problems = self.env['ems.contact.data.request']._ems_contact_data_problems(
            self._ems_contact_data(), self.is_adult, formats=False)
        return [message for _key, message in problems]


class EmsContactDataRequest(models.Model):
    """A request to a student and their family to review and complete their contact data from
    the portal, and what they sent back, pending review (issue #507).

    One per student and academic year: sending again reopens it. The submitted changes are
    staged as lines and only written to the contacts when a reviewer approves them - a family
    changing its own email would otherwise lose its portal login mid-session, and a new family
    contact may turn out to be one already on file. See
    docs/en/developers/contacts/contact_data_request.md.
    """
    _name = 'ems.contact.data.request'
    _description = 'Contact data update request'
    _order = 'id desc'
    _rec_name = 'student_id'

    _sql_constraints = [
        ('student_course_unique', 'unique(student_id, course_id)',
         "A student can only have one contact data request per academic year."),
    ]

    student_id = fields.Many2one(
        'res.partner', string='Student', required=True, ondelete='cascade', index=True,
        domain=[('contact_type', 'in', ('student', 'applicant'))])
    course_id = fields.Many2one('ems.course', string='Academic Year', required=True)
    group_id = fields.Many2one(related='student_id.main_group_id', store=True, string='Group')
    tutor_id = fields.Many2one(related='student_id.tutor_id', string='Tutor')
    state = fields.Selection([
        ('pending', 'Pending answer'),
        ('submitted', 'To review'),
        ('done', 'Done'),
    ], string='Status', default='pending', required=True, index=True)
    missing_fields = fields.Text(string='Missing', readonly=True,
                                 help="What was missing when the request was last sent.")
    sent_date = fields.Datetime(string='Sent on', readonly=True)
    reminder_count = fields.Integer(string='Reminders', readonly=True)
    last_reminder_date = fields.Datetime(string='Last reminder', readonly=True)
    submitted_date = fields.Datetime(string='Answered on', readonly=True)
    submitted_uid = fields.Many2one('res.users', string='Answered by', readonly=True)
    review_uid = fields.Many2one('res.users', string='Reviewed by', readonly=True)
    review_date = fields.Datetime(string='Reviewed on', readonly=True)
    rejection_reason = fields.Text(string='Reason for returning it', readonly=True)
    line_ids = fields.One2many('ems.contact.data.request.line', 'request_id', string='Changes')
    has_possible_duplicate = fields.Boolean(
        string='Possible duplicate', compute='_compute_has_possible_duplicate', store=True)

    @api.depends('line_ids.possible_duplicate_id')
    def _compute_has_possible_duplicate(self):
        for request in self:
            request.has_possible_duplicate = bool(request.line_ids.possible_duplicate_id)

    # ------------------------------------------------------------------
    # Validation - shared by the portal form and the "what is missing" check
    # ------------------------------------------------------------------
    @api.model
    def _ems_valid_dni_nie(self, value):
        """Spanish DNI (8 digits + letter) or NIE (X/Y/Z + 7 digits + letter) with its check letter."""
        match = re.fullmatch(r'([XYZ]?)(\d{7,8})([A-Z])', value)
        if not match:
            return False
        prefix, digits, letter = match.groups()
        if prefix and len(digits) != 7 or not prefix and len(digits) != 8:
            return False
        number = int(str('XYZ'.index(prefix)) + digits if prefix else digits)
        return DNI_LETTERS[number % 23] == letter

    @api.model
    def _ems_valid_phone(self, value):
        try:
            import phonenumbers
            return phonenumbers.is_possible_number(phonenumbers.parse(value, 'ES'))
        except Exception:
            return False

    @api.model
    def _ems_format_problems(self, prefix, values, fields_list):
        problems = []
        for field in fields_list:
            value = (values.get(field) or '').strip()
            if not value:
                continue
            if field == 'email' and not email_normalize(value):
                problems.append((f'{prefix}_{field}', _("%s is not a valid email address.", value)))
            elif field in PHONE_FIELDS and not self._ems_valid_phone(value):
                problems.append((f'{prefix}_{field}', _("%s is not a valid phone number.", value)))
            elif field == 'document_id' and not self._ems_valid_dni_nie(re.sub(r'[\s-]', '', value).upper()):
                problems.append((f'{prefix}_{field}', _("%s is not a valid DNI/NIE.", value)))
            elif field == 'nuss' and not re.fullmatch(r'\d{12}', value):
                problems.append((f'{prefix}_{field}', _("The NUSS must be exactly 12 numeric digits.")))
        return problems

    @api.model
    def _ems_personal_email_problems(self, data, current):
        """[(input key, message)] for every email `data` changes to an address of the centre's own
        domain. res.partner refuses to store one (issue #514), so it is refused here, before the
        request is sent, and not when a reviewer approves it. An address already on file is left
        alone, as the partner constraint does."""
        on_file = {'s': current['student'].get('email')}
        on_file.update({entry['key']: entry.get('email') for entry in current['family']})
        people = [('s', data['student'])] + [
            (entry['key'], entry) for entry in data['family'] if not entry.get('remove')]
        problems = []
        for key, values in people:
            email = (values.get('email') or '').strip()
            if not email or email == (on_file.get(key) or '').strip():
                continue
            try:
                self.env.company._ems_check_personal_email(email)
            except ValidationError as error:
                problems.append((f'{key}_email', error.args[0]))
        return problems

    @api.model
    def _ems_contact_data_problems(self, data, is_adult, formats=True, current=None):
        """[(input key, message)] for everything wrong or missing in `data` (the shape of
        res.partner._ems_contact_data()). The required fields are the ones family communications
        and portal access depend on - see the "Mandatory fields" table in the developer doc.
        `current` is the data on file: with `formats`, only the emails that differ from it are
        checked against the centre's own domain (all of them when it is not given)."""
        problems = []
        student = data['student']
        labels = self.env['res.partner']._fields
        for field in ADDRESS_FIELDS:
            if not student.get(field):
                problems.append((f's_{field}', _("%s is missing.", labels[field].get_description(self.env)['string'])))
        if not (student.get('document_id') or student.get('passport_id')):
            problems.append(('s_document_id', _("An identity document (DNI/NIE or passport) is missing.")))
        if is_adult and not student.get('email'):
            problems.append(('s_email', _("An adult student needs a personal email: it is their portal login.")))
        if formats:
            problems += self._ems_format_problems('s', student, STUDENT_FIELDS)

        family = [entry for entry in data['family'] if not entry.get('remove')]
        if not is_adult and not family:
            problems.append(('family', _("At least one legal tutor is needed.")))
        if not is_adult and family and not any(entry.get('email') for entry in family):
            problems.append(('family', _("At least one family contact needs an email: it is their portal login.")))
        emails = {}
        for entry in family:
            key = entry['key']
            who = ' '.join(filter(None, (entry.get('firstname'), entry.get('lastname')))) or _("the new family contact")
            for field, message in (
                ('firstname', _("The first name of %s is missing.")),
                ('lastname', _("The last name of %s is missing.")),
                ('mobile', _("The mobile of %s is missing.")),
            ):
                if not entry.get(field):
                    problems.append((f'{key}_{field}', message % who))
            if not entry.get('relation_type_id'):
                problems.append((f'{key}_relation_type_id', _("The relation of %s is missing.") % who))
            email = email_normalize(entry.get('email') or '')
            if email and email in emails:
                problems.append((f'{key}_email', _(
                    "%(who)s and %(other)s cannot share an email: each one needs their own portal login.",
                    who=who, other=emails[email])))
            elif email:
                emails[email] = who
            if formats:
                problems += self._ems_format_problems(key, entry, FAMILY_FIELDS)
        if formats:
            problems += self._ems_personal_email_problems(data, current or {'student': {}, 'family': []})
        return problems

    # ------------------------------------------------------------------
    # Submission (portal)
    # ------------------------------------------------------------------
    @api.model
    def _ems_open_for(self, student, course):
        """This student's request for `course`, created if there is none yet."""
        request = self.search([('student_id', '=', student.id), ('course_id', '=', course.id)], limit=1)
        return request or self.create({'student_id': student.id, 'course_id': course.id})

    def _ems_submit(self, proposal):
        """Stage what the student/family sent (already validated) as lines against the data on
        file now. Nothing changed at all means the data was confirmed as it is: done, with nothing
        to review."""
        self.ensure_one()
        current = self.student_id._ems_contact_data()
        lines = self._ems_diff_lines(self.student_id, current, proposal)
        self.line_ids.unlink()
        self.write({
            'line_ids': [(0, 0, vals) for vals in lines],
            'state': 'submitted' if lines else 'done',
            'submitted_date': fields.Datetime.now(),
            'submitted_uid': self.env.uid,
            'rejection_reason': False,
            'review_uid': False,
            'review_date': False,
        })

    @api.model
    def _ems_diff_lines(self, student, current, proposal):
        """Line values for every field `proposal` changes against `current` (both in the shape of
        res.partner._ems_contact_data())."""
        lines = []
        current_family = {entry['key']: entry for entry in current['family']}

        def changes(before, after, fields_list):
            return [(field, before.get(field) or '', (after.get(field) or '').strip())
                    for field in fields_list
                    if (before.get(field) or '').strip() != (after.get(field) or '').strip()]

        for field, old, new in changes(current['student'], proposal['student'], STUDENT_FIELDS):
            lines.append({'action': 'update', 'person_key': 's', 'partner_id': student.id,
                          'field_name': field, 'old_value': old, 'new_value': new})
        for entry in proposal['family']:
            before = current_family.get(entry['key'])
            if before:
                if entry.get('remove'):
                    lines.append({'action': 'remove', 'person_key': entry['key'],
                                  'partner_id': before['id']})
                    continue
                for field, old, new in changes(before, entry, FAMILY_FIELDS):
                    lines.append({'action': 'update', 'person_key': entry['key'],
                                  'partner_id': before['id'], 'field_name': field,
                                  'old_value': old, 'new_value': new})
                continue
            if entry.get('remove'):
                continue
            match, possible_duplicate = self.env['res.partner']._ems_find_family(
                document=entry.get('document_id') or entry.get('passport_id'),
                mobile=entry.get('mobile'), firstname=entry.get('firstname'))
            for field in FAMILY_FIELDS:
                value = (entry.get(field) or '').strip()
                if value:
                    lines.append({
                        'action': 'create', 'person_key': entry['key'],
                        'field_name': field, 'new_value': value,
                        'relation_type_id': int(entry['relation_type_id']),
                        'matched_partner_id': match.id,
                        'possible_duplicate_id': possible_duplicate.id,
                    })
        return lines

    def _ems_proposal(self):
        """The data on file with this request's staged changes laid over it - what the portal
        form shows again while the request waits for review."""
        self.ensure_one()
        data = self.student_id._ems_contact_data()
        family = {entry['key']: entry for entry in data['family']}
        for line in self.line_ids:
            if line.person_key == 's':
                data['student'][line.field_name] = line.new_value or ''
            elif line.action == 'remove' and line.person_key in family:
                family[line.person_key]['remove'] = True
            elif line.action == 'update' and line.person_key in family:
                family[line.person_key][line.field_name] = line.new_value or ''
            elif line.action == 'create':
                entry = family.get(line.person_key)
                if not entry:
                    entry = family[line.person_key] = {
                        'key': line.person_key, 'id': False, 'remove': False,
                        'relation_type_id': line.relation_type_id.id}
                    data['family'].append(entry)
                entry[line.field_name] = line.new_value or ''
        return data

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------
    def action_approve(self):
        """Write the staged changes to the student and their family, with the reviewer's own
        rights - a tutor can already edit their students and those students' family contacts
        (rule_contact_tutor). Only creating or linking a family contact goes through sudo, as the
        relation wizard does."""
        requests = self.filtered(lambda request: request.state == 'submitted')
        if not requests:
            raise UserError(_("There is nothing to approve: only answered requests can be approved."))
        requests.check_access('write')
        for request in requests:
            request._ems_apply()
            request.write({
                'state': 'done',
                'review_uid': self.env.uid,
                'review_date': fields.Datetime.now(),
                'missing_fields': '\n'.join(request.student_id._ems_contact_data_missing()),
            })
        return True

    def _ems_apply(self):
        self.ensure_one()
        student = self.student_id
        people = {}
        for line in self.line_ids:
            people.setdefault(line.person_key, self.env['ems.contact.data.request.line'])
            people[line.person_key] |= line
        for lines in people.values():
            first = lines[0]
            if first.action == 'update':
                first.partner_id.write({line.field_name: line.new_value or False for line in lines})
            elif first.action == 'remove':
                self.env['res.partner.relation'].search([
                    ('left_partner_id', '=', first.partner_id.id),
                    ('right_partner_id', '=', student.id),
                ]).with_context(ems_remove_orphan_family=True).unlink()
            else:
                vals = {line.field_name: line.new_value for line in lines}
                family, _possible_duplicate = self.env['res.partner']._ems_find_family(
                    document=vals.get('document_id') or vals.get('passport_id'),
                    mobile=vals.get('mobile'), firstname=vals.get('firstname'))
                if family:
                    # Already on file (a sibling's family): only fill in what it lacks.
                    family.write({field: value for field, value in vals.items() if not family[field]})
                    student._ems_link_family(family, first.relation_type_id)
                else:
                    student._ems_create_family_contact(vals, first.relation_type_id)
        student.message_post(body=_("Contact data updated from the portal request, reviewed by %s.",
                                    self.env.user.name))

    def action_open_reject_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Return to the family"),
            'res_model': 'ems.contact.data.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_ids': [(6, 0, self.filtered(
                lambda request: request.state == 'submitted').ids)]},
        }

    def _ems_reject(self, reason):
        """Send the answer back: the request is pending again, with the reason, and the family is
        emailed so they can correct it."""
        self.check_access('write')
        self.line_ids.unlink()
        self.write({
            'state': 'pending',
            'rejection_reason': reason,
            'review_uid': self.env.uid,
            'review_date': fields.Datetime.now(),
        })
        for request in self:
            request._ems_send_request_email()

    # ------------------------------------------------------------------
    # Sending and reminders
    # ------------------------------------------------------------------
    def _ems_mark_sent(self):
        self.write({'state': 'pending', 'sent_date': fields.Datetime.now(), 'rejection_reason': False,
                    'reminder_count': 0, 'last_reminder_date': False})
        for request in self:
            request.missing_fields = '\n'.join(request.student_id._ems_contact_data_missing())

    def action_send_reminder(self):
        """Email again whoever has not answered yet."""
        pending = self.filtered(lambda request: request.state == 'pending')
        if not pending:
            raise UserError(_("There is no pending request among the selected ones."))
        pending.check_access('write')
        mailed, issues = 0, []
        for request in pending:
            sent, issue = request._ems_send_request_email(reminder=True)
            mailed += sent
            if issue:
                issues.append(issue)
            request.write({'reminder_count': request.reminder_count + 1,
                           'last_reminder_date': fields.Datetime.now()})
        message = _("%s reminder email(s) queued.", mailed)
        if issues:
            message += "\n" + _("Nobody reachable - contact them by phone:") + "\n- " + "\n- ".join(issues)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Send reminder"),
                'message': message,
                'type': 'warning' if issues else 'success',
                'sticky': bool(issues),
            },
        }

    def _ems_send_request_email(self, reminder=False):
        """Email this request to the student - or, for a minor, to the family - with the link to
        the portal page. Same recipients as every other notice addressed to "the student"
        (res.partner._ems_notification_recipients()): whoever acts for them on the portal, never a
        view-only account such as a minor's own. Returns (emails queued, issue or None)."""
        self.ensure_one()
        student = self.student_id
        template = self.env.ref('ems.email_template_contact_data_request', raise_if_not_found=False)
        if not template:
            return 0, None
        recipients = student._ems_notification_recipients().filtered('email')
        if not recipients:
            return 0, student.name
        for recipient in recipients:
            lang = recipient.lang or student.lang
            # force_send=False: a whole-level batch goes out through the regular mail queue.
            template.with_context(
                lang=lang,
                course_name=self.course_id.name,
                # Outside the template's {{ }}: a translator must not touch its expressions.
                subject_prefix=self.with_context(lang=lang).env._("Reminder: ") if reminder else '',
                rejection_reason=self.rejection_reason or '',
                # In the recipient's language, not the sender's.
                missing_fields=student.with_context(lang=lang)._ems_contact_data_missing(),
            ).sudo().send_mail(student.id, force_send=False,
                               email_values={'email_to': recipient.email})
        return len(recipients), None

    @api.model
    def _ems_user_can_request(self):
        """Secretary, academic admin and head of studies request data from anyone; a tutor from
        their own students (enforced by the send assistant's scope and the record rules)."""
        return base.EmsBase.get_user_sees_every_student(self) or self.env.user.has_group('ems.group_tutor')


class EmsContactDataRequestLine(models.Model):
    """One change a student or family asked for: a field of an existing contact, a field of a new
    family contact (lines sharing person_key are one person), or removing a family contact."""
    _name = 'ems.contact.data.request.line'
    _description = 'Contact data update request change'
    _order = 'request_id, person_key, id'

    request_id = fields.Many2one('ems.contact.data.request', required=True, ondelete='cascade', index=True)
    action = fields.Selection([
        ('update', 'Update'),
        ('create', 'New family contact'),
        ('remove', 'No longer a contact'),
    ], required=True)
    person_key = fields.Char(required=True)
    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='cascade')
    person_name = fields.Char(string='Person', compute='_compute_person_name')
    field_name = fields.Char()
    field_label = fields.Char(string='Field', compute='_compute_field_label')
    old_value = fields.Char(string='On file')
    new_value = fields.Char(string='Proposed')
    relation_type_id = fields.Many2one('res.partner.relation.type', string='Relation')
    matched_partner_id = fields.Many2one(
        'res.partner', string='Already on file as', ondelete='set null',
        help="The new family contact matches this contact, by document or by mobile and first "
             "name: approving links it instead of creating another one.")
    possible_duplicate_id = fields.Many2one(
        'res.partner', string='Possible duplicate of', ondelete='set null',
        help="Another family contact has the same mobile under a different name: a new contact "
             "will be created. Check whether it is the same person.")

    @api.depends('partner_id', 'person_key', 'request_id.line_ids.new_value')
    def _compute_person_name(self):
        for line in self:
            if line.partner_id:
                line.person_name = line.partner_id.name
                continue
            siblings = line.request_id.line_ids.filtered(lambda other: other.person_key == line.person_key)
            names = {other.field_name: other.new_value for other in siblings}
            line.person_name = ' '.join(filter(None, (names.get('firstname'), names.get('lastname'))))

    @api.depends('field_name')
    def _compute_field_label(self):
        partner_fields = self.env['res.partner']._fields
        for line in self:
            field = partner_fields.get(line.field_name or '')
            line.field_label = field.get_description(self.env)['string'] if field else False


class EmsContactDataRequestRejectWizard(models.TransientModel):
    _name = 'ems.contact.data.request.reject.wizard'
    _description = 'Return a contact data request to the family'

    # Explicit relation table: the auto-generated name is over PostgreSQL's 63-character limit.
    request_ids = fields.Many2many('ems.contact.data.request', relation='ems_cdr_reject_wizard_request_rel',
                                   column1='wizard_id', column2='request_id', string='Requests')
    reason = fields.Text(string='Reason', required=True,
                         help="Sent to the family by email: say what they have to correct.")

    def action_reject(self):
        self.ensure_one()
        self.request_ids._ems_reject(self.reason)
        return {'type': 'ir.actions.act_window_close'}
