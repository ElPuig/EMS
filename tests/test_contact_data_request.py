from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import (CORPORATE_TEST_DOMAIN, create_level_study_group, create_role_employee, create_role_user,
                     enforce_corporate_email_policy, mock_outgoing_email, next_student_id)

DNI_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE'


def valid_dni(number):
    """A DNI with its right check letter, e.g. valid_dni(12345678) -> '12345678Z'."""
    return f'{number:08d}{DNI_LETTERS[number % 23]}'


def create_contact_data_fixtures(cls, prefix='TCDR'):
    """A group with a tutor, a minor student with one family contact (incomplete data: no address,
    no document, family without last name) and an adult student with complete data, both enrolled
    in the running course. Fictitious addresses and numbers only (CLAUDE.md, "Email safety")."""
    Course = cls.env['ems.course']
    cls.course = cls.env['res.partner']._ems_running_course() \
        or Course.create({'start': 2096, 'end': 2097, 'is_current': True})
    cls.level, cls.study, cls.group = create_level_study_group(cls, prefix, study={
        'code': f'{prefix}01', 'acronym': f'{prefix}S', 'name': f'Test Contact Data Study {prefix}',
    })
    cls.tutor = create_role_user(cls, 'tutor', f'test_tutor_{prefix.lower()}',
                                 name=f'Test Tutor ({prefix})', email=f'tutor.{prefix.lower()}@example.com')
    cls.group.tutor_id = create_role_employee(cls, cls.tutor)

    def student(name, age, **vals):
        partner = cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'main_group_id': cls.group.id,
            'birth_date': date.today() - relativedelta(years=age),
            'student_id': next_student_id(), **vals,
        })
        cls.env['sale.order'].create({
            'partner_id': partner.id, 'ems_study_id': cls.study.id, 'ems_course_id': cls.course.id,
        })
        return partner

    cls.minor = student(f'Minor Student ({prefix})', 15)
    cls.family = cls.env['res.partner'].create({
        'firstname': 'Contact', 'lastname': False, 'contact_type': 'family',
        'mobile': '+34 711 200 001', 'email': f'family.{prefix.lower()}@example.com',
    })
    cls.env['res.partner.relation'].create({
        'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_mother').id,
        'right_partner_id': cls.minor.id,
    })
    cls.adult = student(f'Adult Student ({prefix})', 19, email=f'adult.{prefix.lower()}@example.com',
                        street='Test Street 1', zip='08921', city='Test City', document_id=valid_dni(10000001))


class TestContactDataRequest(TransactionCase):
    """ems.contact.data.request (issue #507): what is missing, validating the portal form,
    staging the answer, approving, returning and reminding - and who may do it. See
    docs/en/developers/contacts/contact_data_request.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_contact_data_fixtures(cls)
        cls.Request = cls.env['ems.contact.data.request'].with_context(lang='en_US')
        cls.mother = cls.env.ref('ems.relation_type_mother')
        cls.father = cls.env.ref('ems.relation_type_father')

    def _complete(self, data):
        data['student'].update(street='Test Street 2', zip='08922', city='Test City',
                               document_id=valid_dni(10000002))
        for entry in data['family']:
            entry['lastname'] = entry.get('lastname') or 'Surname'
        return data

    def _request(self, student=None):
        return self.Request._ems_open_for(student or self.minor, self.course)

    # --- what is missing --------------------------------------------------------------------

    def test_missing_lists_address_document_and_family_last_name(self):
        missing = self.minor.with_context(lang='en_US')._ems_contact_data_missing()
        self.assertEqual(len(missing), 5, missing)
        self.assertTrue(any('identity document' in message for message in missing))
        self.assertTrue(any('last name' in message for message in missing))

    def test_complete_adult_has_nothing_missing(self):
        self.assertEqual(self.adult._ems_contact_data_missing(), [])

    def test_student_mobile_and_family_document_are_optional(self):
        data = self._complete(self.minor._ems_contact_data())
        self.assertFalse(data['student']['mobile'])
        self.assertFalse(data['family'][0]['document_id'])
        self.assertEqual(self.Request._ems_contact_data_problems(data, is_adult=False), [])

    def test_minor_without_family_is_rejected(self):
        data = self._complete(self.minor._ems_contact_data())
        data['family'][0]['remove'] = True
        keys = [key for key, _message in self.Request._ems_contact_data_problems(data, is_adult=False)]
        self.assertIn('family', keys)

    def test_adult_without_email_is_rejected(self):
        data = self.adult._ems_contact_data()
        data['student']['email'] = ''
        keys = [key for key, _message in self.Request._ems_contact_data_problems(data, is_adult=True)]
        self.assertEqual(keys, ['s_email'])

    def test_second_tutor_cannot_share_the_email(self):
        data = self._complete(self.minor._ems_contact_data())
        data['family'].append({
            'key': 'n0', 'id': False, 'remove': False, 'relation_type_id': self.father.id,
            'firstname': 'Other', 'lastname': 'Tutor', 'mobile': '711200002',
            'email': self.family.email,
        })
        keys = [key for key, _message in self.Request._ems_contact_data_problems(data, is_adult=False)]
        self.assertEqual(keys, ['n0_email'])

    def test_formats_are_validated(self):
        data = self._complete(self.minor._ems_contact_data())
        data['student'].update(document_id='12345678A', nuss='123', email='not-an-email', mobile='12')
        keys = {key for key, _message in self.Request._ems_contact_data_problems(data, is_adult=False)}
        self.assertEqual(keys, {'s_document_id', 's_nuss', 's_email', 's_mobile'})

    def test_dni_and_nie_check_letter(self):
        self.assertTrue(self.Request._ems_valid_dni_nie('12345678Z'))
        self.assertTrue(self.Request._ems_valid_dni_nie('X1234567L'))
        self.assertFalse(self.Request._ems_valid_dni_nie('12345678A'))
        self.assertFalse(self.Request._ems_valid_dni_nie('X12345678L'))

    # --- recognising a family contact -------------------------------------------------------

    def test_find_family_by_mobile_with_matching_first_name(self):
        family, duplicate = self.env['res.partner']._ems_find_family(mobile='711200001', firstname='Contact Maria')
        self.assertEqual(family, self.family)
        self.assertFalse(duplicate)

    def test_find_family_same_mobile_other_name_is_a_possible_duplicate(self):
        family, duplicate = self.env['res.partner']._ems_find_family(mobile='711 200 001', firstname='Joan')
        self.assertFalse(family)
        self.assertEqual(duplicate, self.family)

    def test_find_family_shared_mobile_is_never_merged(self):
        self.env['res.partner'].create({'firstname': 'Contact', 'lastname': 'Twin',
                                        'contact_type': 'family', 'phone': '711200001'})
        family, duplicate = self.env['res.partner']._ems_find_family(mobile='711200001', firstname='Contact')
        self.assertFalse(family)
        self.assertTrue(duplicate)

    def test_find_family_ignores_students(self):
        self.adult.mobile = '711200009'
        family, duplicate = self.env['res.partner']._ems_find_family(mobile='711200009', firstname='Adult')
        self.assertFalse(family or duplicate)

    def test_find_family_by_document_first(self):
        self.family.document_id = valid_dni(10000003)
        family, _duplicate = self.env['res.partner']._ems_find_family(
            document=valid_dni(10000003).lower(), mobile='600000000', firstname='Anyone')
        self.assertEqual(family, self.family)

    # --- submitting and approving -----------------------------------------------------------

    def test_submit_stages_changes_without_touching_contacts(self):
        request = self._request()
        request._ems_submit(self._complete(self.minor._ems_contact_data()))
        self.assertEqual(request.state, 'submitted')
        self.assertFalse(self.minor.street)
        self.assertIn('street', request.line_ids.mapped('field_name'))

    def test_submit_without_changes_is_done(self):
        request = self._request(self.adult)
        request._ems_submit(self.adult._ems_contact_data())
        self.assertEqual(request.state, 'done')
        self.assertFalse(request.line_ids)

    def test_approve_writes_student_family_and_new_contact(self):
        data = self._complete(self.minor._ems_contact_data())
        data['family'].append({
            'key': 'n0', 'id': False, 'remove': False, 'relation_type_id': self.father.id,
            'firstname': 'New', 'lastname': 'Father', 'mobile': '711200003',
            'email': 'father.tcdr@example.com',
        })
        request = self._request()
        request._ems_submit(data)
        request.with_user(self.tutor).action_approve()
        self.assertEqual(request.state, 'done')
        self.assertEqual(request.review_uid, self.tutor)
        self.assertEqual(self.minor.street, 'Test Street 2')
        self.assertEqual(self.family.lastname, 'Surname')
        family = self.minor._ems_family_contacts()
        self.assertEqual(len(family), 2)
        self.assertIn('New Father', family.mapped('name'))
        self.assertEqual(self.minor._ems_contact_data_missing(), [])

    def test_approve_links_a_family_contact_already_on_file(self):
        sibling_parent = self.env['res.partner'].create({
            'firstname': 'Known', 'lastname': 'Parent', 'contact_type': 'family',
            'document_id': valid_dni(10000004), 'mobile': '711200004',
        })
        data = self._complete(self.minor._ems_contact_data())
        data['family'].append({
            'key': 'n0', 'id': False, 'remove': False, 'relation_type_id': self.father.id,
            'firstname': 'Known', 'lastname': 'Parent', 'mobile': '711200004',
            'email': 'known.parent@example.com',
        })
        request = self._request()
        request._ems_submit(data)
        self.assertEqual(request.line_ids.matched_partner_id, sibling_parent)
        request.action_approve()
        self.assertIn(sibling_parent, self.minor._ems_family_contacts())
        self.assertEqual(sibling_parent.email, 'known.parent@example.com')
        self.assertFalse(self.env['res.partner'].search_count([
            ('contact_type', '=', 'family'), ('mobile', '=', '711200004'), ('id', '!=', sibling_parent.id)]))

    def test_possible_duplicate_is_flagged(self):
        data = self._complete(self.minor._ems_contact_data())
        data['family'].append({
            'key': 'n0', 'id': False, 'remove': False, 'relation_type_id': self.father.id,
            'firstname': 'Different', 'lastname': 'Name', 'mobile': '711200001',
            'email': 'different.tcdr@example.com',
        })
        request = self._request()
        request._ems_submit(data)
        self.assertTrue(request.has_possible_duplicate)

    def test_approve_removes_a_family_contact(self):
        other = self.env['res.partner'].create({
            'firstname': 'Former', 'lastname': 'Contact', 'contact_type': 'family', 'mobile': '711200005',
            'email': 'former.tcdr@example.com',
        })
        self.env['res.partner.relation'].create({
            'left_partner_id': other.id, 'type_id': self.father.id, 'right_partner_id': self.minor.id})
        data = self._complete(self.minor._ems_contact_data())
        next(entry for entry in data['family'] if entry['id'] == other.id)['remove'] = True
        request = self._request()
        request._ems_submit(data)
        request.action_approve()
        self.assertEqual(self.minor._ems_family_contacts(), self.family)

    def test_approve_email_change_moves_portal_login(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Family Portal (TCDR)', 'login': self.family.email, 'partner_id': self.family.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        data = self._complete(self.minor._ems_contact_data())
        data['family'][0]['email'] = 'new.family.tcdr@example.com'
        request = self._request()
        request._ems_submit(data)
        request.action_approve()
        self.assertEqual(user.login, 'new.family.tcdr@example.com')

    def test_proposal_shows_staged_changes(self):
        data = self._complete(self.minor._ems_contact_data())
        request = self._request()
        request._ems_submit(data)
        self.assertEqual(request._ems_proposal()['student']['street'], 'Test Street 2')

    # --- returning and reminding ------------------------------------------------------------

    def test_reject_returns_it_pending_and_emails_the_family(self):
        request = self._request()
        request._ems_submit(self._complete(self.minor._ems_contact_data()))
        self.env['ems.contact.data.request.reject.wizard'].create({
            'request_ids': [(6, 0, request.ids)], 'reason': 'The DNI photo is missing',
        }).action_reject()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.rejection_reason, 'The DNI photo is missing')
        self.assertFalse(request.line_ids)
        mail = self.env['mail.mail'].search([('email_to', '=', self.family.email)], order='id desc', limit=1)
        self.assertIn('The DNI photo is missing', mail.body_html)

    def test_reminder_counts_and_emails_pending_only(self):
        request = self._request()
        request._ems_mark_sent()
        request.action_send_reminder()
        self.assertEqual(request.reminder_count, 1)
        self.assertTrue(self.env['mail.mail'].search_count([('email_to', '=', self.family.email)]))
        request.state = 'done'
        with self.assertRaises(UserError):
            request.action_send_reminder()

    def test_only_the_reminder_subject_is_prefixed_in_the_recipients_language(self):
        self.family.lang = 'ca_ES'
        request = self._request()
        request._ems_send_request_email()
        request._ems_send_request_email(reminder=True)
        subjects = self.env['mail.mail'].search([('email_to', '=', self.family.email)], order='id').mapped('subject')
        self.assertEqual(len(subjects), 2)
        self.assertTrue(subjects[0].startswith('Reviseu les dades de contacte de'), subjects[0])
        self.assertTrue(subjects[1].startswith('Recordatori: Reviseu les dades de contacte de'), subjects[1])

    # --- access -----------------------------------------------------------------------------

    def test_other_tutor_cannot_approve(self):
        _level, _study, other_group = create_level_study_group(self, 'TCDO', study={
            'code': 'TCDO01', 'acronym': 'TCDOS', 'name': 'Other Contact Data Study'})
        other_tutor = create_role_user(self, 'tutor', 'test_other_tutor_tcdr', name='Other Tutor (TCDR)')
        other_group.tutor_id = create_role_employee(self, other_tutor)
        request = self._request()
        request._ems_submit(self._complete(self.minor._ems_contact_data()))
        with self.assertRaises(AccessError):
            request.with_user(other_tutor).action_approve()

    def test_teacher_reads_students_without_the_requests(self):
        teacher = create_role_user(self, 'teacher', 'test_teacher_tcdr', name='Teacher (TCDR)')
        self._request()
        self.minor.with_user(teacher).read(['name', 'contact_type', 'email'])
        with self.assertRaises(AccessError):
            self.env['ems.contact.data.request'].with_user(teacher).search([])


class TestContactDataRequestCorporateEmail(TransactionCase):
    """A personal email can never be an address of the centre's own domain (issue #514): the portal
    form refuses it before the request is sent, and only when the answer changes the address."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        enforce_corporate_email_policy(cls)
        create_contact_data_fixtures(cls, 'TCCE')
        cls.Request = cls.env['ems.contact.data.request'].with_context(lang='en_US')
        cls.corporate = f'laia.puig@{CORPORATE_TEST_DOMAIN}'

    def _answer(self):
        """The minor's data with everything required filled in, as the family would send it."""
        data = self.minor._ems_contact_data()
        data['student'].update(street='Test Street 2', zip='08922', city='Test City',
                               document_id=valid_dni(10000003))
        data['family'][0]['lastname'] = 'Surname'
        return data

    def _problems(self, data, **kwargs):
        return self.Request._ems_contact_data_problems(data, is_adult=False, **kwargs)

    def test_a_corporate_address_is_refused_for_the_student_and_for_every_family_contact(self):
        current = self.minor._ems_contact_data()
        data = self._answer()
        data['student']['email'] = self.corporate
        data['family'][0]['email'] = f'mother@alumnes.{CORPORATE_TEST_DOMAIN}'
        data['family'].append({
            'key': 'n0', 'id': False, 'remove': False, 'relation_type_id': self.env.ref('ems.relation_type_father').id,
            'firstname': 'New', 'lastname': 'Father', 'mobile': '711200009', 'email': self.corporate.upper(),
        })
        problems = dict(self._problems(data, current=current))
        self.assertEqual(set(problems), {'s_email', f'f{self.family.id}_email', 'n0_email'})
        for message in problems.values():
            self.assertIn("can't be used as a personal email", message)

    def test_an_address_already_on_file_is_not_asked_to_change(self):
        # Legacy data from before the rule: the partner constraint only fires on a write of the
        # email, so an answer that keeps it must go through.
        self.env.flush_all()
        self.env.cr.execute("UPDATE res_partner SET email = %s WHERE id = %s", (self.corporate, self.family.id))
        self.family.invalidate_recordset(['email'])
        current = self.minor._ems_contact_data()
        data = self._answer()
        self.assertEqual(data['family'][0]['email'], self.corporate)
        self.assertEqual(self._problems(data, current=current), [])
        data['family'][0]['email'] = f'other.mother@{CORPORATE_TEST_DOMAIN}'
        self.assertEqual([key for key, _message in self._problems(data, current=current)],
                         [f'f{self.family.id}_email'])

    def test_without_the_data_on_file_every_corporate_address_counts_as_new(self):
        data = self._answer()
        data['student']['email'] = self.corporate
        self.assertEqual([key for key, _message in self._problems(data)], ['s_email'])

    def test_a_family_contact_being_removed_is_not_checked(self):
        data = self._answer()
        data['family'][0].update(email=self.corporate, remove=True)
        self.assertNotIn(f'f{self.family.id}_email',
                         [key for key, _message in self._problems(data, current=self.minor._ems_contact_data())])

    def test_what_is_missing_ignores_the_domain(self):
        data = self._answer()
        data['student']['email'] = self.corporate
        self.assertEqual(self.Request._ems_contact_data_problems(data, is_adult=False, formats=False), [])

    def test_the_partner_constraint_is_still_the_last_word(self):
        # Approval writes the emails with the reviewer's rights: a corporate address staged by
        # other means is refused by res.partner itself.
        with self.assertRaisesRegex(ValidationError, "can't be used as a personal email"):
            self.family.email = self.corporate


class TestContactDataRequestMenu(TransactionCase):
    """Student Data sits under Educational Community > Students (issue #507): Students is a section
    holding the Students list and this menu."""

    def test_students_is_a_section_with_the_students_list_and_student_data(self):
        community = self.env.ref('ems.menu_community')
        section = self.env.ref('ems.menu_students_root')
        students = self.env.ref('ems.menu_students')
        data = self.env.ref('ems.menu_contact_data_requests')
        self.assertEqual(section.parent_id, community)
        self.assertFalse(section.action, "The section only groups: clicking it must not open anything")
        self.assertEqual(section.child_id.sorted(lambda menu: (menu.sequence, menu.id)), students | data)
        self.assertEqual(data.action, self.env.ref('ems.action_ems_contact_data_request'))
        # import_student_cog_menu.js and update_student_cog_menu.js read the Students action from it.
        self.assertEqual(students.action, self.env.ref('ems.action_student_kanban'))

    def test_menu_names_are_translated(self):
        section = self.env.ref('ems.menu_students_root')
        data = self.env.ref('ems.menu_contact_data_requests')
        self.assertEqual(data.with_context(lang='en_US').name, 'Student Data')
        self.assertEqual(data.with_context(lang='ca_ES').name, 'Dades Estudiants')
        self.assertEqual(data.with_context(lang='es_ES').name, 'Datos Estudiantes')
        self.assertEqual(section.with_context(lang='ca_ES').name, 'Estudiants')
        self.assertEqual(section.with_context(lang='es_ES').name, 'Estudiantes')
