# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityDocument(models.Model):
    _name = "ems.quality.document"
    _description = "Controlled document: what it is, who owns it, which version it is at and where it lives."
    _inherit = ['mail.thread']
    _order = "code, name"
    _sql_constraints = [
        # Nullable on purpose: a document can be registered before the coordination assigns it a
        # code, and those are exactly the ones worth listing. Postgres treats NULLs as distinct,
        # so several uncoded documents coexist without tripping the constraint.
        ('unique_code', 'unique (code)', "Another document already uses this code."),
    ]

    code = fields.Char(string="Code", tracking=True, help="As in the centre's documentation: PE3.01.15. Empty while the document has not been coded yet.")
    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    kind = fields.Selection(
        string="Kind",
        selection=[
            ('procedure', "Procedure"),
            ('record', "Record"),
            ('template', "Template"),
            ('strategic', "Strategic document"),
            ('form', "Form"),
            ('manual', "Manual"),
        ],
        required=True,
        default='record',
        tracking=True,
    )
    procedure_id = fields.Many2one(string="Procedure", comodel_name="ems.quality.procedure", ondelete='set null', tracking=True)
    process_id = fields.Many2one(
        string="Process",
        comodel_name="ems.quality.process",
        compute="_compute_process_id",
        store=True,
        readonly=False,
        ondelete='set null',
        tracking=True,
        help="Taken from the procedure when there is one, and editable for documents that hang straight off a process.",
    )
    responsible_role_id = fields.Many2one(string="Responsible post", comodel_name="ems.role", tracking=True, help="Who drafts and maintains it.")
    version = fields.Char(string="Version", tracking=True)
    state = fields.Selection(
        string="State",
        selection=[('draft', "Draft"), ('review', "Under review"), ('approved', "Approved"), ('obsolete', "Obsolete")],
        required=True,
        default='draft',
        tracking=True,
    )
    approval_date = fields.Date(string="Approved on", tracking=True)
    revision_date = fields.Date(string="Last revised on", tracking=True)
    next_review_date = fields.Date(string="Next review", tracking=True, help="What the management review asks for: which documents need updating.")
    requested_by_role_id = fields.Many2one(string="Requested by", comodel_name="ems.role")
    request_date = fields.Date(string="Requested on")
    due_date = fields.Date(string="Due on")
    superseded_by_id = fields.Many2one(string="Superseded by", comodel_name="ems.quality.document", ondelete='set null', tracking=True)
    supersedes_ids = fields.One2many(string="Supersedes", comodel_name="ems.quality.document", inverse_name="superseded_by_id")
    # Deliberately not data/custom/ CSV columns: they change whenever a document is replaced,
    # which makes them live application state (same carve-out as ems.course.is_current and
    # ir.sequence.number_next_actual). A synced column would revert the change on the next
    # upgrade. Loaded from a code,url file kept outside the repository instead.
    url = fields.Char(string="Link", tracking=True, help="Where the file actually lives, normally in the centre's Drive.")
    drive_file_id = fields.Char(string="Drive file id", help="Stored alongside the link so it survives the file being moved or renamed.")
    is_minute_template = fields.Boolean(string="Minute template", help="Marks the controlled template that minutes and evidence records are generated from.")
    published_moodle = fields.Boolean(string="Published on Moodle")
    published_web = fields.Boolean(string="Published on the website")
    published_mail = fields.Boolean(string="Distributed by e-mail")
    published_date = fields.Date(string="Last distributed on")
    is_legacy_code = fields.Boolean(
        string="Code out of the current map",
        compute="_compute_is_legacy_code",
        store=True,
        help="The code does not start with any process code of the current map: a leftover from a superseded coding scheme.",
    )
    needs_review = fields.Boolean(
        string="Review due",
        compute="_compute_needs_review",
        search="_search_needs_review",
        help="Approved, with a next review date already in the past.",
    )
    active = fields.Boolean(string="Active", default=True)

    @api.depends('procedure_id')
    def _compute_process_id(self):
        for document in self:
            if document.procedure_id:
                document.process_id = document.procedure_id.process_id

    @api.depends('code')
    def _compute_is_legacy_code(self):
        """Flag codes whose leading segment is not a process of the current map.

        Compared segment by segment rather than with startswith(): 'PS23.2.1' - a code from the
        superseded scheme - does start with 'PS2', so a prefix test would let exactly the codes
        this is meant to catch slip through."""
        process_codes = set(self.env['ems.quality.process'].with_context(active_test=False).search([]).mapped('code'))
        for document in self:
            code = (document.code or '').strip()
            document.is_legacy_code = bool(code) and bool(process_codes) and code.split('.')[0] not in process_codes

    def _compute_needs_review(self):
        today = fields.Date.context_today(self)
        for document in self:
            document.needs_review = document.state == 'approved' and bool(document.next_review_date) and document.next_review_date < today

    def _search_needs_review(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError
        domain = [('state', '=', 'approved'), ('next_review_date', '<', fields.Date.context_today(self))]
        if (operator == '=') != bool(value):
            return ['!'] + domain
        return domain

    @api.depends('code', 'name', 'version')
    def _compute_display_name(self):
        for document in self:
            parts = [part for part in (document.code, document.name) if part]
            label = ": ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
            document.display_name = f"{label} (v{document.version})" if document.version else label
