# -*- coding: utf-8 -*-
import re

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.contacts.contact_data_request import ADDRESS_FIELDS, FAMILY_FIELDS, STUDENT_FIELDS


class EmsPortalContactData(CustomerPortal):
    """Issue #507 - /my/dades-contacte: the student, or a family for their selected child, reviews
    and completes the contact details on file and sends them for review.

    Always the student resolved by get_portal_student(): no student id travels in the form, and
    only the family contacts already related to that student can be edited or removed. Everything
    is read and staged with sudo, since portal users have no rights on the relations nor on
    ems.contact.data.request; nothing is written to the contacts themselves until a reviewer
    approves it (ems.contact.data.request.action_approve).
    """

    def _ems_contact_data_student(self):
        student = request.env.user.partner_id.get_portal_student().sudo()
        return student if student.contact_type in ('student', 'applicant') else student.browse()

    def _ems_contact_data_request(self, student):
        course = request.env['res.partner'].sudo()._ems_running_course()
        return request.env['ems.contact.data.request'].sudo().search([
            ('student_id', '=', student.id), ('course_id', '=', course.id)], limit=1), course

    @http.route('/my/dades-contacte', type='http', auth='user', methods=['GET', 'POST'], website=True)
    def portal_contact_data(self, **post):
        student = self._ems_contact_data_student()
        if not student:
            return self._ems_render_contact_data(student, {'student': {}, 'family': []})
        data_request, course = self._ems_contact_data_request(student)
        if request.httprequest.method != 'POST':
            data = data_request._ems_proposal() if data_request.state == 'submitted' \
                else student._ems_contact_data()
            return self._ems_render_contact_data(student, data, data_request=data_request,
                                                 sent=bool(post.get('sent')))

        Request = request.env['ems.contact.data.request'].sudo()
        proposal = self._ems_parse_contact_data(post, student._ems_contact_data())
        problems = Request._ems_contact_data_problems(proposal, student.is_adult)
        if problems:
            errors = {}
            for key, message in problems:
                errors.setdefault(key, []).append(message)
            return self._ems_render_contact_data(student, proposal, data_request=data_request, errors=errors)
        Request._ems_open_for(student, course)._ems_submit(proposal)
        return request.redirect('/my/dades-contacte?sent=1')

    def _ems_parse_contact_data(self, post, current):
        """The posted form in the shape of res.partner._ems_contact_data(). Existing family contacts
        come from `current` - never from ids in the form - so only this student's own can be
        touched; new ones are the n<number>_* inputs added in the browser."""
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
            entry = fill({'key': key, 'id': False, 'remove': False, 'relation_type_id': relation_id}, key)
            if relation_id or any(entry[field] for field in FAMILY_FIELDS if field not in ADDRESS_FIELDS):
                family.append(entry)
        return {'student': student, 'family': family}

    def _ems_render_contact_data(self, student, data, data_request=None, errors=None, sent=False):
        values = self._prepare_portal_layout_values()
        for entry in data['family']:
            entry.setdefault('same_address', not any(entry.get(field) for field in ADDRESS_FIELDS) or all(
                (entry.get(field) or '') == (data['student'].get(field) or '') for field in ADDRESS_FIELDS))
        values.update({
            'page_name': 'contact_data',
            'student': student,
            'data': data,
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
