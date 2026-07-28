# -*- coding: utf-8 -*-
import base64
import csv
import io
import json
from datetime import datetime

from markupsafe import Markup

from odoo import models, fields, _
from odoo.exceptions import UserError


class EmsCSVColumn(models.TransientModel):
    _name = 'ems.csv_column'
    _description = 'CSV column (temporary mapping helper)'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=0)
    wizard_id = fields.Many2one('ems.student_update_wizard', ondelete='cascade')


class EmsStudentUpdateWizard(models.TransientModel):
    _name = 'ems.student_update_wizard'
    _description = 'Student data update wizard'

    file = fields.Binary(string='CSV file', required=True)
    file_name = fields.Char()
    csv_columns_json = fields.Char()   # used only for step visibility condition

    # Match key
    col_student_id = fields.Many2one('ems.csv_column', string='Student ID (IDALU, RALC...)',
                                     domain="[('wizard_id', '=', id)]", ondelete='set null')

    # Student fields
    col_name          = fields.Many2one('ems.csv_column', string='Full name',        domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_phone         = fields.Many2one('ems.csv_column', string='Phone',            domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_mobile        = fields.Many2one('ems.csv_column', string='Mobile',           domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_email         = fields.Many2one('ems.csv_column', string='Email',            domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_student_email = fields.Many2one('ems.csv_column', string='Student email',    domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_birth_date    = fields.Many2one('ems.csv_column', string='Birth date',       domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_document_id   = fields.Many2one('ems.csv_column', string='DNI / NIE',        domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_passport_id   = fields.Many2one('ems.csv_column', string='Passport',         domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_medical_id    = fields.Many2one('ems.csv_column', string='Medical ID (TIS)', domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_nuss          = fields.Many2one('ems.csv_column', string='NUSS',             domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_car_plate     = fields.Many2one('ems.csv_column', string='Car plate',        domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_street        = fields.Many2one('ems.csv_column', string='Street',           domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_city          = fields.Many2one('ems.csv_column', string='City',             domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_zip           = fields.Many2one('ems.csv_column', string='Postal code',      domain="[('wizard_id', '=', id)]", ondelete='set null')

    # Bank account
    col_iban          = fields.Many2one('ems.csv_column', string='IBAN',                domain="[('wizard_id', '=', id)]", ondelete='set null')
    col_acc_holder    = fields.Many2one('ems.csv_column', string='Account holder name', domain="[('wizard_id', '=', id)]", ondelete='set null')

    result_html = fields.Html(readonly=True)
    result_csv  = fields.Binary(readonly=True)
    result_csv_filename = fields.Char(readonly=True)

    # col_* field → (model, field_name) whose already-translated label we reuse
    _COL_LABEL_SOURCE = {
        'col_name':          ('res.partner',      'name'),
        'col_phone':         ('res.partner',      'phone'),
        'col_mobile':        ('res.partner',      'mobile'),
        'col_email':         ('res.partner',      'email'),
        'col_student_email': ('res.partner',      'student_email'),
        'col_birth_date':    ('res.partner',      'birth_date'),
        'col_document_id':   ('res.partner',      'document_id'),
        'col_passport_id':   ('res.partner',      'passport_id'),
        'col_medical_id':    ('res.partner',      'medical_id'),
        'col_nuss':          ('res.partner',      'nuss'),
        'col_car_plate':     ('res.partner',      'car_plate'),
        'col_street':        ('res.partner',      'street'),
        'col_city':          ('res.partner',      'city'),
        'col_zip':           ('res.partner',      'zip'),
        'col_acc_holder':    ('res.partner.bank', 'acc_holder_name'),
    }

    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields, attributes)
        if not attributes or 'string' in attributes:
            # Group sources by model to batch the fields_get calls
            by_model = {}
            for wiz_field, (model, partner_field) in self._COL_LABEL_SOURCE.items():
                if wiz_field in res:
                    by_model.setdefault(model, {})[wiz_field] = partner_field
            for model, mapping in by_model.items():
                partner_defs = self.env[model].fields_get(
                    list(mapping.values()), ['string']
                )
                for wiz_field, partner_field in mapping.items():
                    if partner_field in partner_defs:
                        res[wiz_field]['string'] = partner_defs[partner_field]['string']
        return res

    def _decode_csv(self):
        content = base64.b64decode(self.file)
        for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise UserError(_("Could not decode the CSV file. Please save it as UTF-8."))

    def _parse_date(self, value):
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    def _reload_action(self):
        return {
            'name': _("EMS: Update students from CSV"),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'views': [[False, 'form']],
            'target': 'new',
        }

    def action_load_columns(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Please upload a CSV file first."))
        text = self._decode_csv()
        reader = csv.reader(io.StringIO(text))
        try:
            headers = next(reader)
        except StopIteration:
            raise UserError(_("The CSV file appears to be empty."))
        headers = [h.strip() for h in headers if h.strip()]
        if not headers:
            raise UserError(_("Could not read column headers from the CSV file."))
        # Replace column records
        self.env['ems.csv_column'].search([('wizard_id', '=', self.id)]).unlink()
        for seq, h in enumerate(headers):
            self.env['ems.csv_column'].create({'name': h, 'sequence': seq, 'wizard_id': self.id})
        self.csv_columns_json = json.dumps(headers)
        return self._reload_action()

    def action_update(self):
        self.ensure_one()
        if not self.col_student_id:
            raise UserError(_("Please select the IDALU column before updating."))

        FIELD_MAP = {
            'name':          self.col_name.name if self.col_name else False,
            'phone':         self.col_phone.name if self.col_phone else False,
            'mobile':        self.col_mobile.name if self.col_mobile else False,
            'email':         self.col_email.name if self.col_email else False,
            'student_email': self.col_student_email.name if self.col_student_email else False,
            'birth_date':    self.col_birth_date.name if self.col_birth_date else False,
            'document_id':   self.col_document_id.name if self.col_document_id else False,
            'passport_id':   self.col_passport_id.name if self.col_passport_id else False,
            'medical_id':    self.col_medical_id.name if self.col_medical_id else False,
            'nuss':          self.col_nuss.name if self.col_nuss else False,
            'car_plate':     self.col_car_plate.name if self.col_car_plate else False,
            'street':        self.col_street.name if self.col_street else False,
            'city':          self.col_city.name if self.col_city else False,
            'zip':           self.col_zip.name if self.col_zip else False,
        }
        active_fields = {field: col for field, col in FIELD_MAP.items() if col}

        idalu_col = self.col_student_id.name
        text = self._decode_csv()
        reader = csv.DictReader(io.StringIO(text))

        updated = 0
        not_found = 0
        errors = []
        result_rows = []   # original row + ems_import_status column
        fieldnames = None

        for row in reader:
            if fieldnames is None:
                fieldnames = list(row.keys())
            idalu = row.get(idalu_col, '').strip()
            if not idalu:
                continue

            student = self.env['res.partner'].search([
                ('student_id', '=', idalu),
                ('contact_type', '=', 'student'),
            ], limit=1)

            if not student:
                not_found += 1
                result_rows.append({**row, 'ems_import_status': 'IDALU not found'})
                continue

            vals = {}
            for field, col in active_fields.items():
                raw = row.get(col, '').strip()
                if field == 'birth_date':
                    if raw:
                        parsed = self._parse_date(raw)
                        if parsed:
                            vals[field] = parsed
                        else:
                            errors.append(_(
                                "Row %(idalu)s: could not parse date '%(value)s'.",
                                idalu=idalu, value=raw,
                            ))
                else:
                    vals[field] = raw or False

            row_error = None
            try:
                # Odoo's @api.constrains checks (e.g. res.partner._check_nuss) run
                # AFTER the underlying SQL write already flushed — without a
                # savepoint, a "failed" row would silently keep its already-applied
                # field changes in the transaction despite being reported as an
                # error. The savepoint rolls the whole row back cleanly on any
                # exception so "reported as failed" actually means "not applied".
                with self.env.cr.savepoint():
                    student.write(vals)
            except Exception as e:
                row_error = str(e)
                errors.append(_("Row %(idalu)s: %(error)s", idalu=idalu, error=row_error))
                result_rows.append({**row, 'ems_import_status': f'error: {row_error}'})
                continue

            updated += 1

            if self.col_iban:
                iban = row.get(self.col_iban.name, '').strip()
                if iban:
                    holder = row.get(self.col_acc_holder.name, '').strip() if self.col_acc_holder else ''
                    try:
                        with self.env.cr.savepoint():
                            BankAccount = self.env['res.partner.bank'].with_context(active_test=False)
                            existing = BankAccount.search([
                                ('partner_id', '=', student.id),
                                ('acc_number', '=', iban),
                            ], limit=1)
                            if existing:
                                existing.write({'active': True, 'acc_holder_name': holder or False})
                                # Archive any other accounts for this student
                                BankAccount.search([
                                    ('partner_id', '=', student.id),
                                    ('id', '!=', existing.id),
                                ]).write({'active': False})
                            else:
                                # Archive all current accounts and create new
                                BankAccount.search([('partner_id', '=', student.id)]).write({'active': False})
                                self.env['res.partner.bank'].create({
                                    'acc_number': iban,
                                    'partner_id': student.id,
                                    'acc_holder_name': holder or False,
                                })
                    except Exception as e:
                        errors.append(_("Row %(idalu)s (bank): %(error)s", idalu=idalu, error=str(e)))

            result_rows.append({**row, 'ems_import_status': 'imported'})

        # Build result CSV (original columns + ems_import_status)
        if result_rows:
            out = io.StringIO()
            all_fieldnames = (fieldnames or []) + ['ems_import_status']
            writer = csv.DictWriter(out, fieldnames=all_fieldnames, extrasaction='ignore', lineterminator='\n')
            writer.writeheader()
            writer.writerows(result_rows)
            self.result_csv = base64.b64encode(out.getvalue().encode('utf-8'))
            self.result_csv_filename = 'import_result.csv'

        html = Markup('<p>{}</p>').format(_(
            "%(updated)s student(s) updated, %(not_found)s IDALU not found.",
            updated=updated, not_found=not_found,
        ))
        if errors:
            items = Markup('').join(Markup('<li>{}</li>').format(e) for e in errors)
            html += Markup('<p><b>{}</b></p><ul>{}</ul>').format(
                _("Errors (%(count)s):", count=len(errors)), items)

        self.result_html = html
        return self._reload_action()
