# -*- coding: utf-8 -*-
import re

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.contacts.contact_data_request import ADDRESS_FIELDS, FAMILY_FIELDS, STUDENT_FIELDS
from .portal_view_only import ems_portal_manage_required


class EmsPortalContactData(CustomerPortal):
    """Issue #507 - /my/dades-contacte: the student, or a family for their selected child, reviews
    and completes the contact details on file and sends them for review.

    Always the student resolved by res.partner._ems_portal_contact_data_student(): no student id
    travels in the form, only whoever acts for the student gets here (a view-only account is sent
    home, like every other managing page), and only the family contacts already related to that
    student can be edited or removed. A family contact it adds may also be linked to the account's
    other children, chosen among those it answers for, and one that repeats a contact of those
    children (same document or phone) is pointed out first. Everything is read and staged with
    sudo, since portal users have no rights on the relations nor on ems.contact.data.request;
    nothing is written to the contacts themselves until a reviewer approves it
    (ems.contact.data.request.action_approve).
    """

    def _ems_contact_data_student(self):
        return request.env.user.partner_id._ems_portal_contact_data_student().sudo()

    def _ems_contact_data_siblings(self, student):
        return request.env.user.partner_id._ems_portal_siblings(student).sudo()

    def _ems_contact_data_request(self, student):
        course = request.env['res.partner'].sudo()._ems_running_course()
        return request.env['ems.contact.data.request'].sudo().search([
            ('student_id', '=', student.id), ('course_id', '=', course.id)], limit=1), course

    @http.route('/my/dades-contacte', type='http', auth='user', methods=['GET', 'POST'], website=True)
    @ems_portal_manage_required
    def portal_contact_data(self, **post):
        student = self._ems_contact_data_student()
        if not student:
            return self._ems_render_contact_data(student, {'student': {}, 'family': []})
        data_request, course = self._ems_contact_data_request(student)
        current = student._ems_contact_data()
        siblings = self._ems_contact_data_siblings(student)
        if request.httprequest.method != 'POST':
            data = data_request._ems_proposal() if data_request.state == 'submitted' else current
            self._ems_annotate_matches(student, siblings, data)
            return self._ems_render_contact_data(student, data, siblings, data_request=data_request,
                                                 sent=bool(post.get('sent')))

        Request = request.env['ems.contact.data.request'].sudo()
        proposal = self._ems_parse_contact_data(post, current, siblings)
        problems = Request._ems_contact_data_problems(proposal, student.is_adult, current=current)
        match_issues = self._ems_annotate_matches(student, siblings, proposal)
        if problems or match_issues:
            errors = {}
            for key, message in problems:
                errors.setdefault(key, []).append(message)
            for key, message in match_issues.items():
                errors.setdefault(f'{key}_confirm', []).append(message)
            return self._ems_render_contact_data(student, proposal, siblings, data_request=data_request,
                                                 errors=errors)
        Request._ems_open_for(student, course)._ems_submit(proposal)
        return request.redirect('/my/dades-contacte?sent=1')

    def _ems_annotate_matches(self, student, siblings, data):
        """Points out, on each family contact the answer adds, the contact of a sibling it repeats
        (entry['match']), and settles what the family answered about it (`confirm` yes/no, for the
        very contact shown - `posted_match`). Returns {key: message} for what still blocks sending:
        no answer yet, or "no" to a document, which identifies one person."""
        partner = request.env.user.partner_id
        issues = {}
        for entry in data['family']:
            if entry.get('id') or entry.get('remove'):
                continue
            match = partner._ems_sibling_contact_match(student, siblings, entry) if siblings else False
            sent_match_id = entry.get('confirmed_match_id')  # only on an entry shown again from what was sent
            entry['match'] = match
            entry['confirmed_match_id'] = False
            if not match:
                continue
            sentence = _("%(name)s, a contact of %(children)s, has the same identity document. Is it the same person?") \
                if match['reason'] == 'document' else \
                _("%(name)s, a contact of %(children)s, has the same mobile number. Is it the same person?")
            match['message'] = sentence % {'name': match['name'], 'children': ', '.join(match['children'])}
            match['yes_label'] = _("Yes, it is the same person: link them to %s", student.name)
            if entry.get('confirm') is None:
                entry['confirm'] = 'yes' if sent_match_id == match['id'] else ''
                entry['posted_match'] = str(match['id'])
            if entry['confirm'] not in ('yes', 'no') or entry.get('posted_match') != str(match['id']):
                issues[entry['key']] = _("Say whether it is the same person.")
            elif entry['confirm'] == 'yes':
                entry['confirmed_match_id'] = match['id']
            elif match['reason'] == 'document':
                issues[entry['key']] = _(
                    "A document belongs to one person: if it is not the same person, correct the document number.")
        return issues

    def _ems_parse_contact_data(self, post, current, siblings):
        """The posted form in the shape of res.partner._ems_contact_data(). Existing family contacts
        come from `current` - never from ids in the form - so only this student's own can be
        touched; new ones are the n<number>_* inputs added in the browser, and the other children
        they are also linked to are picked among `siblings`, never from ids in the form."""
        valid_relation_ids = request.env['res.partner.relation.type'].sudo().search([]).ids

        def value(name):
            return (post.get(name) or '').strip()

        student = {field: value(f's_{field}') for field in STUDENT_FIELDS}

        def fill(entry, key):
            for field in FAMILY_FIELDS:
                entry[field] = value(f'{key}_{field}')
            entry['same_address'] = bool(post.get(f'{key}_same_address'))
            if entry['same_address']:
                entry.update({field: student[field] for field in ADDRESS_FIELDS})
            return entry

        family = []
        for entry in current['family']:
            family.append(fill(dict(entry, remove=bool(post.get(f"{entry['key']}_remove"))), entry['key']))
        new_keys = sorted({match.group(1) for match in (re.match(r'^(n\d+)_', name) for name in post) if match},
                          key=lambda key: int(key[1:]))
        for key in new_keys:
            relation = value(f'{key}_relation_type_id')
            relation_id = int(relation) if relation.isdigit() and int(relation) in valid_relation_ids else False
            entry = fill({
                'key': key, 'id': False, 'remove': False, 'relation_type_id': relation_id,
                'also_for': [child.id for child in siblings if post.get(f'{key}_also_{child.id}')],
                'confirm': value(f'{key}_confirm'), 'posted_match': value(f'{key}_match'),
            }, key)
            if relation_id or any(entry[field] for field in FAMILY_FIELDS if field not in ADDRESS_FIELDS):
                family.append(entry)
        return {'student': student, 'family': family}

    def _ems_render_contact_data(self, student, data, siblings, data_request=None, errors=None, sent=False):
        values = self._prepare_portal_layout_values()
        for entry in data['family']:
            entry.setdefault('same_address', not any(entry.get(field) for field in ADDRESS_FIELDS) or all(
                (entry.get(field) or '') == (data['student'].get(field) or '') for field in ADDRESS_FIELDS))
        values.update({
            'page_name': 'contact_data',
            'student': student,
            'data': data,
            'siblings': [{'id': child.id, 'name': child.name} for child in siblings],
            'errors': {key: ' '.join(messages) for key, messages in (errors or {}).items()},
            'data_request': data_request,
            'sent': sent,
            'relation_types': request.env['res.partner.relation.type'].sudo().search([]),
            'viewing_as_family': student and student != request.env.user.partner_id,
            # New family contacts added in the browser continue after the ones already shown.
            'next_new_index': max([int(entry['key'][1:]) + 1 for entry in data['family']
                                   if entry['key'].startswith('n')] or [0]),
        })
        return request.render('ems.portal_contact_data', values)
