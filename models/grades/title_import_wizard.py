# -*- coding: utf-8 -*-

import base64
import csv
import io

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .year_record import TITLE_EFFECTS


def _normalize_header(value):
    return str(value or '').strip().lower().replace('’', "'").replace('‘', "'")


def _cell_text(value):
    """A cell as text: an xlsx number such as 4665445099.0 back to '4665445099'."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value if value is not None else '').strip()


def _title_notification(summary, titles):
    """The result notification of the Register title wizard."""
    message = _("%(titles)s title(s) registered.", titles=titles)
    if summary['graduated']:
        message += " " + _("%(graduated)s student(s) left the centre as graduates.",
                           graduated=summary['graduated'])
    if summary['alumni']:
        message += " " + _("%(alumni)s withdrawal(s) became alumni.", alumni=summary['alumni'])
    if summary['revoked']:
        message += " " + _("%(revoked)s portal access(es) revoked.", revoked=summary['revoked'])
    if summary['issues']:
        message += "\n" + _("Issues:") + "\n- " + "\n- ".join(summary['issues'])
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': _("Titles"),
            'message': message,
            'type': 'warning' if summary['issues'] else 'success',
            'sticky': bool(summary['issues']),
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
        },
    }


def _register_titles(records):
    """Tick the title of `records` and apply its effects on the students, returning
    (records registered, summary of _ems_register_title()). The write skips the automatic effects
    so they run once, here, where their summary is kept."""
    records = records.filtered(lambda record: not record.title_obtained)
    records.with_context(ems_skip_title_effects=True).write({'title_obtained': True})
    return records, records._ems_register_title()


class EmsTitleImportWizard(models.TransientModel):
    _name = 'ems.title_import_wizard'
    _description = 'Title import wizard (titles obtained, from Esfera)'

    # Headers are matched normalized (_normalize_header), in Catalan as Esfera exports them or
    # in Spanish. Only the student identifier is required: a file with that single column is a
    # plain list of graduates of the course chosen in the wizard.
    _STUDENT_ID_HEADERS = ("identificador de l'alumne/a", 'identificador del alumno/a', 'idalu')
    # Optional: rows of another course are left out (the course comes from the wizard).
    _COURSE_HEADERS = ('curs', 'curso')
    # Optional: a cancelled title request does not count, unless the student has another one.
    _STATUS_HEADERS = ("estat de la sol·licitud", 'estado de la solicitud')
    # Optional, only shown in the preview of a student missing from EMS.
    _NAME_HEADERS = (('nom', 'nombre'), ('primer cognom', 'primer apellido'),
                     ('segon cognom', 'segundo apellido'))

    file = fields.Binary(string="File", required=True)
    file_name = fields.Char(string="File name")
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', required=True,
                                default=lambda self: self._default_course(),
                                help="Course the titles were obtained in. Rows of the file with "
                                     "another course in their 'Curs' column are left out.")
    line_ids = fields.One2many(string="Students", comodel_name='ems.title_import_wizard.line',
                               inverse_name='wizard_id')
    apply_count = fields.Integer(string="Titles to register", compute='_compute_apply_count')
    result_html = fields.Html(string="Import result", readonly=True)
    log_file = fields.Binary(string="Import log (CSV)", readonly=True)
    log_file_name = fields.Char()

    @api.model
    def _default_course(self):
        """The course before the current one: titles reach the centre once the course is over."""
        current = self.env.company.current_course_id
        if not current:
            return self.env['ems.course']
        previous = self.env['ems.course'].search([('start', '<', current.start)],
                                                 order='start desc', limit=1)
        return previous or current

    @api.depends('line_ids.to_apply')
    def _compute_apply_count(self):
        for wizard in self:
            wizard.apply_count = len(wizard.line_ids.filtered('to_apply'))

    # --- reading the file ---

    def _read_tables(self):
        """Every sheet of the file as a list of rows (lists of text cells)."""
        raw = base64.b64decode(self.file or b'')
        if raw[:2] == b'PK':
            try:
                import openpyxl
            except ImportError:
                raise UserError(_("openpyxl is required to import xlsx files."))
            workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            return [[[_cell_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
                    for sheet in workbook.worksheets]
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Esfera exports its CSV in Windows-1252.
            text = raw.decode('cp1252', errors='replace')
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=';,\t')
            delimiter = dialect.delimiter
        except csv.Error:
            # A one-column file has no delimiter to detect.
            delimiter = ';'
        return [[[_cell_text(cell) for cell in row]
                 for row in csv.reader(io.StringIO(text), delimiter=delimiter)]]

    def _find_columns(self, rows):
        """(index of the header row, {key: column}) or (None, {}) without an identifier column."""
        for index, row in enumerate(rows[:20]):
            headers = [_normalize_header(cell) for cell in row]

            def column(aliases):
                return next((i for i, header in enumerate(headers) if header in aliases), None)

            student_column = column(self._STUDENT_ID_HEADERS)
            if student_column is None:
                continue
            columns = {
                'student': student_column,
                'course': column(self._COURSE_HEADERS),
                'status': column(self._STATUS_HEADERS),
                'names': [i for i in (column(aliases) for aliases in self._NAME_HEADERS)
                          if i is not None],
            }
            return index, columns
        return None, {}

    def _read_students(self):
        """{identifier: {'name': str, 'courses': [str], 'statuses': [str]}} in file order."""
        students = {}
        found_header = False
        for rows in self._read_tables():
            header_index, columns = self._find_columns(rows)
            if header_index is None:
                continue
            found_header = True

            def cell(row, i):
                return row[i] if i is not None and i < len(row) else ''

            for row in rows[header_index + 1:]:
                identifier = cell(row, columns['student'])
                if not identifier:
                    continue
                entry = students.setdefault(identifier, {'name': '', 'courses': [], 'statuses': []})
                entry['name'] = entry['name'] or ' '.join(
                    filter(None, (cell(row, i) for i in columns['names'])))
                entry['courses'].append(cell(row, columns['course']))
                entry['statuses'].append(cell(row, columns['status']))
        if not found_header:
            raise UserError(_(
                "The file has no column with the student identifier. It needs a column named "
                "\"Identificador de l'alumne/a\" or \"IDALU\"."))
        return students

    # --- preview and apply ---

    def _line_vals(self, identifier, entry):
        vals = {'student_identifier': identifier, 'name': entry['name']}
        # An empty cell (or no such column) does not rule the row out.
        if not any(not course or course == self.course_id.name for course in entry['courses']):
            return dict(vals, outcome='other_course')
        if not any('anul' not in status.lower() for status in entry['statuses']):
            return dict(vals, outcome='cancelled')
        student = self.env['res.partner'].with_context(active_test=False).search(
            [('student_id', '=', identifier)], limit=1)
        if not student:
            return dict(vals, outcome='not_found')
        vals.update(student_id=student.id, name=student.name)
        record = self.env['ems.student.year_record'].search(
            [('student_id', '=', student.id), ('course_id', '=', self.course_id.id)], limit=1)
        if not record:
            return dict(vals, outcome='no_record')
        vals['record_id'] = record.id
        if record.title_obtained:
            return dict(vals, outcome='already')
        return dict(vals, outcome=record._ems_title_effect())

    def action_preview(self):
        self.ensure_one()
        students = self._read_students()
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, self._line_vals(identifier, entry)) for identifier, entry in students.items()]
        return self._reopen()

    def action_apply(self):
        """Register the titles one line at a time, so the log can say what happened to each
        student, and show the result in the wizard with its CSV log (downloaded on its own)."""
        self.ensure_one()
        totals = {'titles': 0, 'graduated': 0, 'alumni': 0, 'revoked': 0, 'issues': []}
        log = []
        for line in self.line_ids:
            registered, summary = _register_titles(line.record_id) if line.to_apply \
                else (line.record_id.browse(), {'issues': []})
            if registered:
                totals['titles'] += 1
                for key in ('graduated', 'alumni', 'revoked'):
                    totals[key] += summary[key]
                totals['issues'] += summary['issues']
            log.append((line, bool(registered), summary['issues']))
        self.log_file = self._build_log_csv(log)
        self.log_file_name = (f"import_titles_"
                              f"{self.env['ems.datetime_utils'].get_local_datetime().strftime('%Y%m%d_%H%M%S')}.csv")
        self.result_html = self._build_result_html(totals)
        return self._reopen()

    def _build_log_csv(self, log):
        outcomes = dict(self.line_ids._fields['outcome']._description_selection(self.env))
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([_("Student ID (IDALU)"), _("Name"), _("Course"), _("Result"),
                         _("Title registered"), _("Issues")])
        for line, registered, issues in log:
            writer.writerow([line.student_identifier, line.name or '', self.course_id.name,
                             outcomes.get(line.outcome, ''), _("Yes") if registered else _("No"),
                             " | ".join(issues)])
        return base64.b64encode(output.getvalue().encode('utf-8-sig'))

    def _build_result_html(self, totals):
        skipped = len(self.line_ids) - totals['titles']
        issues_html = Markup("")
        if totals['issues']:
            issues_html = Markup("<p><strong>{} ({}):</strong></p>{}").format(
                _("Issues"), len(totals['issues']), self.env['ems.base'].build_html_list(totals['issues']))
        return Markup(
            "<p>✅ <strong>{}:</strong> {}</p>"
            "<p>🎓 <strong>{}:</strong> {}</p>"
            "<p>🔁 <strong>{}:</strong> {}</p>"
            "<p>🔒 <strong>{}:</strong> {}</p>"
            "<p>⏭️ <strong>{}:</strong> {}</p>"
            "{}"
        ).format(
            _("Titles registered"), totals['titles'],
            _("Students who left the centre as graduates"), totals['graduated'],
            _("Withdrawals that became alumni"), totals['alumni'],
            _("Portal accesses revoked"), totals['revoked'],
            _("Rows not registered (see the log)"), skipped,
            issues_html,
        )

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Import titles"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }


class EmsTitleImportWizardLine(models.TransientModel):
    _name = 'ems.title_import_wizard.line'
    _description = 'Title import wizard line (preview)'
    _order = 'outcome, name'

    wizard_id = fields.Many2one(string="Wizard", comodel_name='ems.title_import_wizard',
                                ondelete='cascade')
    student_identifier = fields.Char(string="Student ID (IDALU)")
    name = fields.Char(string="Name")
    student_id = fields.Many2one(string="Student", comodel_name='res.partner')
    record_id = fields.Many2one(string="Academic record", comodel_name='ems.student.year_record')
    outcome = fields.Selection(string="Result", selection=TITLE_EFFECTS + [
        ('already', 'Title already registered'),
        ('no_record', 'No academic record for the course'),
        ('not_found', 'Not found in EMS'),
        ('cancelled', 'Title request cancelled'),
        ('other_course', 'Another course'),
    ])
    to_apply = fields.Boolean(string="To apply", compute='_compute_to_apply')

    @api.depends('outcome')
    def _compute_to_apply(self):
        effects = {effect for effect, _label in TITLE_EFFECTS}
        for line in self:
            line.to_apply = line.outcome in effects


class EmsTitleRegisterWizard(models.TransientModel):
    _name = 'ems.title_register_wizard'
    _description = 'Register a title obtained by one student'

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 readonly=True)
    # Picked by course, which is what the operator knows; the record follows from it.
    available_course_ids = fields.Many2many(string="Available courses", comodel_name='ems.course',
                                            compute='_compute_available_course_ids')
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', required=True,
                                domain="[('id', 'in', available_course_ids)]")
    record_id = fields.Many2one(string="Academic record", comodel_name='ems.student.year_record',
                                compute='_compute_record_id')
    effect = fields.Selection(string="Effect on the student", selection=TITLE_EFFECTS,
                              compute='_compute_effect')

    def _pending_records(self, student):
        """The student's closed records without a title."""
        return self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('title_obtained', '=', False),
            ('is_provisional', '=', False)])

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        records = self._pending_records(self.env['res.partner'].browse(res.get('student_id')))
        if not records:
            raise UserError(_("This student has no course in the academic history without a "
                              "title registered."))
        # The latest course: the one a title usually arrives for.
        res['course_id'] = max(records.course_id, key=lambda course: course.start).id
        return res

    @api.depends('student_id')
    def _compute_available_course_ids(self):
        for wizard in self:
            wizard.available_course_ids = self._pending_records(wizard.student_id).course_id

    @api.depends('student_id', 'course_id')
    def _compute_record_id(self):
        for wizard in self:
            wizard.record_id = self._pending_records(wizard.student_id).filtered(
                lambda record: record.course_id == wizard.course_id)[:1]

    @api.depends('record_id')
    def _compute_effect(self):
        for wizard in self:
            wizard.effect = wizard.record_id._ems_title_effect() if wizard.record_id else False

    def action_apply(self):
        self.ensure_one()
        registered, summary = _register_titles(self.record_id)
        return _title_notification(summary, len(registered))
