# -*- coding: utf-8 -*-
import re
import unicodedata

from odoo import api, models


class EmsFamilyContact(models.Model):
    """Finding, creating and linking a student's family contacts (issue #507).

    One place for what the relation wizard, the Esfera import and the contact-data update requests
    all do: recognise a family contact already on file before creating another one, then link it
    to the student. See docs/en/developers/contacts/contact_data_request.md, "Recognising a family
    contact".
    """
    _inherit = 'res.partner'

    # The part of a phone number that identifies the line: a Spanish number's 9 digits, whatever
    # prefix or spacing it was stored with. Used only to narrow the candidates in SQL; the match
    # itself compares full E.164 keys.
    _EMS_PHONE_TAIL_DIGITS = 9

    @api.model
    def _ems_phone_key(self, number):
        """Comparable form of a phone number: E.164 when it parses (Spain by default, so a bare
        "612 345 678" and "+34612345678" agree), otherwise its digits alone. False when empty."""
        if not number:
            return False
        try:
            import phonenumbers
            parsed = phonenumbers.parse(number, 'ES')
            if phonenumbers.is_possible_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
        return re.sub(r'\D', '', number) or False

    @api.model
    def _ems_first_name_key(self, name):
        """A first name reduced to lowercase letters, without accents or spaces ("Luz Mila" and
        "Luzmila" agree)."""
        decomposed = unicodedata.normalize('NFD', name or '')
        return ''.join(char for char in decomposed if char.isalpha()).lower()

    @api.model
    def _ems_first_names_match(self, name, other):
        """Whether two first names can belong to the same person: one contained in the other, so
        "Raquel" matches "Raquel Salguero" but "Esther" never matches "Chaylin"."""
        key, other_key = self._ems_first_name_key(name), self._ems_first_name_key(other)
        return bool(key and other_key) and (key in other_key or other_key in key)

    @api.model
    def _ems_families_with_phone(self, number):
        """Active family contacts holding `number` as mobile or phone, in any stored format."""
        key = self._ems_phone_key(number)
        if not key:
            return self.env['res.partner']
        tail = re.sub(r'\D', '', key)[-self._EMS_PHONE_TAIL_DIGITS:]
        self.env['res.partner'].flush_model(['mobile', 'phone', 'contact_type', 'active'])
        self.env.cr.execute("""
            SELECT id FROM res_partner
             WHERE contact_type = 'family' AND active
               AND (right(regexp_replace(coalesce(mobile, ''), '\\D', '', 'g'), %(digits)s) = %(tail)s
                 OR right(regexp_replace(coalesce(phone, ''), '\\D', '', 'g'), %(digits)s) = %(tail)s)
        """, {'digits': self._EMS_PHONE_TAIL_DIGITS, 'tail': tail})
        candidates = self.env['res.partner'].sudo().browse([row[0] for row in self.env.cr.fetchall()])
        return candidates.filtered(lambda partner: key in (
            self._ems_phone_key(partner.mobile), self._ems_phone_key(partner.phone)))

    @api.model
    def _ems_find_family(self, document=False, mobile=False, firstname=False):
        """The family contact already on file for this person, as (family, possible_duplicate).

        1. By identity document (DNI/NIE or passport), when one is given.
        2. Otherwise by mobile number, accepted only when exactly one family contact holds it
           and its first name matches `firstname`. Parents sharing one phone, or a number that
           changed hands, would otherwise merge two different people into one contact.

        When the mobile matches someone who is not accepted, that contact comes back as
        possible_duplicate, so the caller creates a new contact and says so. Only family
        contacts are searched, never students: a student commonly gives the family's phone.
        Both records come back with sudo - the callers are the controlled paths that may link a
        family contact the current user cannot read yet (a sibling's, from another group).
        """
        Partner = self.env['res.partner'].sudo()
        document = re.sub(r'\s', '', document or '').upper()
        if document:
            family = Partner.search([
                ('contact_type', '=', 'family'),
                '|', ('document_id', '=ilike', document), ('passport_id', '=ilike', document),
            ], limit=1)
            if family:
                return family, Partner
        candidates = self._ems_families_with_phone(mobile)
        if not candidates:
            return Partner, Partner
        if len(candidates) == 1 and self._ems_first_names_match(
                candidates.firstname or candidates.name, firstname):
            return candidates, Partner
        return Partner, candidates[:1]

    def _ems_link_family(self, family, relation_type):
        """Relate `family` to this student with `relation_type`, unless they already are."""
        self.ensure_one()
        Relation = self.env['res.partner.relation'].sudo()
        if not Relation.search_count([
            ('left_partner_id', '=', family.id), ('right_partner_id', '=', self.id),
        ]):
            Relation.create({
                'left_partner_id': family.id,
                'type_id': relation_type.id,
                'right_partner_id': self.id,
            })

    def _ems_create_family_contact(self, vals, relation_type):
        """Create a family contact from `vals` and relate it to this student.

        sudo: a tutor has no create rights on res.partner or res.partner.relation (see
        security/ir.model.access.csv); every caller is a controlled entry point that already
        checked the user may manage this student.
        """
        self.ensure_one()
        family = self.env['res.partner'].sudo().create(dict(vals, contact_type='family'))
        self._ems_link_family(family, relation_type)
        return family
