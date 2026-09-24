# -*- coding: utf-8 -*-

import calendar
import logging
from datetime import date

from pytz import UTC

from odoo.tools import config, email_normalize
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from cryptography.fernet import Fernet

_logger = logging.getLogger(__name__)

MONTHS = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'), ('5', 'May'), ('6', 'June'),
    ('7', 'July'), ('8', 'August'), ('9', 'September'), ('10', 'October'), ('11', 'November'),
    ('12', 'December'),
]

class ems_company(models.Model):
    _inherit = 'res.company'

	# NOTE: If created within settings, setting up a zero value erases the entry and the default value is used. 
    #		Using this approach, the delay can be zero (useful for testing purposes on a devel environment).
    #       Also, string and help values are only defined within the settings form. 
    attendance_issue_status_delay = fields.Integer(default=15)
    attendance_issue_tutor_default = fields.Float(default=21.0)
    strike_escalation_threshold = fields.Integer(default=3)
    # NOTE: defaults to 'all' so an installation upgrading into this version keeps today's
    # always-notify-the-family behaviour unchanged. A brand-new installation starts on the
    # stricter 'kicked_out' instead, set by post_init_hook (see __init__.py).
    strike_family_notification_mode = fields.Selection(
        selection=[
            ('all', 'All strikes'),
            ('kicked_out', 'Kicked out only'),
        ],
        default='all', required=True,
    )
    auto_checkin_mode = fields.Selection(
        selection=[
            ('disabled', 'Disabled'),
            ('first',    'First (first scheduled working hour)'),
            ('start',    'Start (start of the current attendance scheduled session)'),
            ('current',  'Current (current time)'),
        ],
        default='disabled',
    )
    auto_checkout_mode = fields.Selection(
        selection=[('native', 'Native (after maximum hours)'), ('ems', 'EMS (at last scheduled hour)')],
        default='native',
    )
    auto_checkout_time = fields.Float(default=1.0)
    auto_checkout_retry_until = fields.Float(default=6.0)

    limesurvey_api = fields.Char()
    limesurvey_usr = fields.Char()    
    limesurvey_pwd = fields.Char(compute='_compute_limesurvey_pwd', inverse='_inverse_limesurvey_pwd', store=False)
    limesurvey_pwd_encrypted = fields.Char(copy=False)
    limesurvey_gid = fields.Integer(default=1)

    ems_full_day_hours = fields.Float(default=7.5)
    ems_health_allowance_hours = fields.Float(default=15.0)

    schedule_import_first_entry_time = fields.Float(default=8.0)
    schedule_import_last_entry_time  = fields.Float(default=21.0)

    # Issue #276 - yearly period (no year: it repeats every year) during which students and
    # families can file convalidation requests from the portal, in the centre's local time. Staff
    # handle requests at any time. See docs/en/developers/grades/convalidation.md.
    convalidation_start_day = fields.Integer(default=1)
    convalidation_start_month = fields.Selection(selection=MONTHS, default='10', required=True)
    convalidation_start_time = fields.Float(default=8.0)
    convalidation_end_day = fields.Integer(default=31)
    convalidation_end_month = fields.Selection(selection=MONTHS, default='3', required=True)
    convalidation_end_time = fields.Float(default=23 + 59 / 60)

    current_course_id = fields.Many2one(comodel_name="ems.course")
    enrollment_course_id = fields.Many2one(
        comodel_name="ems.course", string="Enrollment course",
        help="The course new enrollments are created for. Keeps ems.course.is_enrollment_default "
             "in sync, the same way current_course_id keeps is_current.")
    default_schedule_framework_id = fields.Many2one(
        comodel_name="resource.calendar", domain="[('is_framework', '=', True)]", required=True,
        default=lambda self: self.env.ref('ems.schedule_framework_default', raise_if_not_found=False))

    director_id = fields.Many2one(
        comodel_name="hr.employee", string="Director",
        help="The person acting as the center's Director. Every top-level department's Manager "
             "(Head of Studies/Deputy) will have their own Manager set to this employee automatically.")

    secretariat_email = fields.Char()

    notice_email_signature = fields.Html(
        string="Notice email signature", translate=True,
        help="Default sign-off appended to every Notice email. Copied onto each new notice "
             "as its own editable signature - editing it here only affects notices created "
             "afterward.")

    # Official Departament d'Educació center code (e.g. '8028047'). Used by the GEDAC
    # applicant import to keep only the rows assigned to this center.
    center_code = fields.Char(string="Center code")

    # --- Google Workspace (creación automática de cuentas de alumno) ---
    # Enfoque: rol de administrador personalizado asignado a la cuenta de servicio,
    # restringido a la OU /alumnos (NO domain-wide delegation, sin suplantación).
    google_ws_enabled       = fields.Boolean(string="Google Workspace enabled", default=False)
    google_ws_domain        = fields.Char(string="Google Workspace domain", default='elpuig.xeill.net')
    google_ws_ou_minor      = fields.Char(string="OU (minors)", default='/alumnos')
    google_ws_ou_adult      = fields.Char(string="OU (adults 18+)", default='/alumnos/+18')
    google_ws_ou_suspended  = fields.Char(string="OU (suspended)", default='/alumnos/bajas',
        help="OU where suspended (former) students are moved.")
    # --- Staff accounts (teachers and ASP) ---
    google_ws_ou_teacher    = fields.Char(string="OU (teachers)", default='/claustro/doble-factor-autenticación',
        help="OU where teacher accounts are created.")
    google_ws_ou_asp        = fields.Char(string="OU (ASP)", default='/pas',
        help="OU where Administrative and Services Personnel accounts are created.")
    google_ws_ou_staff_suspended = fields.Char(string="OU (staff suspended)", default='/claustro/bajas',
        help="OU where suspended (former) staff accounts are moved.")
    google_ws_dry_run       = fields.Boolean(
        string="Google Workspace dry-run", default=True,
        help="If enabled, the account creation is logged without calling the real Google API.")
    # Service Account JSON, stored encrypted (same Fernet pattern as limesurvey_pwd)
    google_ws_sa_json           = fields.Text(compute='_compute_google_ws_sa_json',
                                              inverse='_inverse_google_ws_sa_json', store=False)
    google_ws_sa_json_encrypted = fields.Char(copy=False)

    @api.constrains('secretariat_email')
    def _check_secretariat_email_format(self):
        for company in self:
            if company.secretariat_email and not email_normalize(company.secretariat_email):
                raise ValidationError(_(
                    "%(email)s is not a valid email address.", email=company.secretariat_email))

    @api.constrains('convalidation_start_day', 'convalidation_start_month', 'convalidation_start_time',
                    'convalidation_end_day', 'convalidation_end_month', 'convalidation_end_time')
    def _check_convalidation_period(self):
        month_names = dict(self._fields['convalidation_start_month']._description_selection(self.env))
        for company in self:
            start, end = company._ems_convalidation_period_keys()
            for month, day, minute in (start, end):
                # A non-leap year: the period has to be the same every year, so no 29 February.
                if not 1 <= day <= calendar.monthrange(2001, month)[1]:
                    raise ValidationError(_(
                        "The convalidation request period uses a day that does not exist: "
                        "%(day)s %(month)s.", day=day, month=month_names[str(month)]))
                if not 0 <= minute < 24 * 60:
                    raise ValidationError(_(
                        "The convalidation request period's times must be between 00:00 and 23:59."))
            if start == end:
                raise ValidationError(_(
                    "The convalidation request period must open and close at different moments."))

    def get_current_course_or_raise(self):
        """The configured "Current course" (current_course_id), or a friendly ValidationError
        instead of the raw crash a caller would otherwise hit trying to use an empty course
        (e.g. 'ensure_one()'s "Expected singleton" on an empty recordset) — the setting is
        required by several features (the guard duty board, the working-schedule import
        wizard...) but nothing guarantees an admin has already set it on a freshly installed
        instance, or in a test DB that never configured one."""
        self.ensure_one()
        if not self.current_course_id:
            raise ValidationError(_(
                "No 'current course' has been setup. Please, select or create the current "
                "course within the EMS settings section."))
        return self.current_course_id

    def _sync_current_course_flag(self):
        """Keep ems.course.is_current in sync with the configured current course
        (the "Current course" setting, current_course_id). Selecting the course in the
        settings marks it as the operational one and clears the flag on any other course,
        so all the code that relies on is_current stays consistent with the setting."""
        Course = self.env['ems.course']
        for company in self:
            course = company.current_course_id
            (Course.search([('is_current', '=', True)]) - course).write({'is_current': False})
            if course and not course.is_current:
                course.is_current = True

    def _sync_enrollment_course_flag(self):
        """Keep ems.course.is_enrollment_default in sync with the configured enrollment
        course, exactly as _sync_current_course_flag does for is_current.

        The clear-then-set order is mandatory: ems.course guards uniqueness with a Python
        @api.constrains, so marking the new course while the old one is still marked
        raises. Doing it here is also what makes moving the mark a single action for the
        operator instead of an untick-then-tick dance."""
        Course = self.env['ems.course']
        for company in self:
            course = company.enrollment_course_id
            (Course.search([('is_enrollment_default', '=', True)]) - course).write(
                {'is_enrollment_default': False})
            if course and not course.is_enrollment_default:
                course.is_enrollment_default = True

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._sync_current_course_flag()
        companies._sync_enrollment_course_flag()
        return companies

    def write(self, vals):
        old_directors = {company: company.director_id for company in self}
        res = super().write(vals)
        if 'current_course_id' in vals:
            self._sync_current_course_flag()
            # Issue #453 - the current course is printed in every group's public schedule PDF title.
            self.env['ems.group'].sudo().search([])._mark_public_schedule_dirty()
        if 'enrollment_course_id' in vals:
            self._sync_enrollment_course_flag()
        if 'director_id' in vals:
            for company in self:
                old_director = old_directors[company]
                self.env['hr.department'].search([
                    ('is_top_level', '=', True), ('company_id', '=', company.id),
                ]).manager_id._compute_parent_id()
                # _compute_parent_id() only depends on department_id, so changing who the
                # Director is doesn't automatically re-trigger it for the (old|new) director
                # employee's own parent_id, even though the Director-immunity rule it applies
                # depends on director_id too - force it explicitly, same reasoning as the
                # is_top_level managers' recompute just above.
                (old_director | company.director_id)._compute_parent_id()
                (old_director | company.director_id).update_director_role()
        return res

    def _register_hook(self):
        """Warns once per server start if this database has never declared whether it's a
        development or a production environment (see 'ems.environment_type', set by
        install.sh/devel.sh/deploy.sh - CLAUDE.md's own 'Development vs. production environment
        declaration' section has the full picture). Skipped during automated test runs
        (config['test_enable']) - a throwaway test database never runs any of those scripts and
        never needs to."""
        super()._register_hook()
        self._ems_freeze_living_custom_data()
        if config['test_enable']:
            return
        if not self.env['ir.config_parameter'].sudo().get_param('ems.environment_type'):
            _logger.warning(
                "EMS: 'ems.environment_type' is not set on this database - neither install.sh, "
                "devel.sh nor deploy.sh has declared this environment yet. If this is a local "
                "development box, run devel.sh before interacting with any real data restored "
                "onto it (it redirects every stored email to your own inbox, avoiding accidental "
                "sends to real people); if this is a real deployment, run deploy.sh, or set "
                "ir.config_parameter 'ems.environment_type' to 'production' directly."
            )

    # Models under 'data/custom/' whose records are the centre's own *living* data - an admin
    # renames/relocates/archives them through the running app, not through this repo's git
    # history - and must therefore never be pushed back to their file-seeded value once created.
    # Extend this tuple as more 'data/custom/' models are confirmed living (not master) data -
    # see docs/en/developers/shared/data_loading.md's "'data/custom/' living data" section.
    _EMS_LIVING_CUSTOM_DATA_MODELS = ('ems.group',)

    def _ems_freeze_living_custom_data(self):
        """Freezes (ir.model.data.noupdate=True) every '__import__'-owned record of a model
        listed in '_EMS_LIVING_CUSTOM_DATA_MODELS', right after every module (re)load.

        CSV loaded via the manifest's plain 'data' key cannot itself carry noupdate=True in this
        Odoo build (odoo/modules/loading.py silently discards init_xml/update_xml - see
        docs/en/developers/shared/data_loading.md) - the only way to freeze such a record is to
        flip its own stored ir.model.data.noupdate flag directly, here. Doing it in
        '_register_hook()' (called once per server start, after all module data has already
        loaded - install and upgrade alike) rather than in a version-pinned migration means a
        brand-new row added to one of these CSVs in a future version still gets created normally
        (noupdate only blocks *updates* to an already-existing row) and is then frozen in turn
        the very next time the server starts - no per-PR migration bookkeeping needed.

        Deliberately NOT skipped under config['test_enable'] (unlike the environment_type check
        above): the test suite relies on this having already run so it can assert on it, and the
        query is cheap and idempotent either way.
        """
        self.env['ir.model.data'].sudo().search([
            ('module', '=', '__import__'),
            ('model', 'in', self._EMS_LIVING_CUSTOM_DATA_MODELS),
            ('noupdate', '=', False),
        ]).write({'noupdate': True})

    def _ems_convalidation_period_keys(self):
        """(month, day, minute of the day) of the convalidation request period's opening and
        closing: tuples in calendar order, whatever the year."""
        self.ensure_one()
        return tuple((int(month), day, round(time * 60)) for day, month, time in (
            (self.convalidation_start_day, self.convalidation_start_month, self.convalidation_start_time),
            (self.convalidation_end_day, self.convalidation_end_month, self.convalidation_end_time),
        ))

    def _ems_convalidation_datetime_utils(self):
        """ems.datetime_utils in the centre's own time zone, whoever is asking."""
        return self.env['ems.datetime_utils'].with_context(tz=self.partner_id.tz)

    def _ems_convalidation_now_key(self, now):
        local = self._ems_convalidation_datetime_utils().utc_datetime_to_local(
            (now or fields.Datetime.now()).replace(tzinfo=UTC))
        return local.year, (local.month, local.day, local.hour * 60 + local.minute)

    def _ems_convalidation_period_open(self, now=None):
        """Whether students and families can file convalidation requests from the portal at `now`
        (naive UTC, defaults to the current moment). The closing minute is still inside; a
        period whose opening comes after its closing in the calendar spans the new year."""
        self.ensure_one()
        start, end = self._ems_convalidation_period_keys()
        now_key = self._ems_convalidation_now_key(now)[1]
        if start < end:
            return start <= now_key <= end
        return now_key >= start or now_key <= end

    def _ems_convalidation_period_next_change(self, now=None):
        """The next time the period opens (while closed) or closes (while open), as naive UTC."""
        self.ensure_one()
        start, end = self._ems_convalidation_period_keys()
        year, now_key = self._ems_convalidation_now_key(now)
        month, day, minute = end if self._ems_convalidation_period_open(now) else start
        if (month, day, minute) < now_key:
            year += 1
        utils = self._ems_convalidation_datetime_utils()
        return utils.datetime_to_odoo(utils.time_float_to_utc_datetime(date(year, month, day), minute / 60))

    @api.model
    def _get_fernet_key(self):
        key = config.get('secret') 
        if not key:
            raise ValueError("Unable to locate a 'secret' value within odoo.conf")
        return key

    def _ems_full_day_hours(self):
        """Hours a whole-day absence is worth. Falls back to the field default rather than
        returning 0.0, which would make every absence worth nothing and, worse, divide by zero
        in 'hr.leave._get_durations'."""
        return self.ems_full_day_hours or self._fields['ems_full_day_hours'].default(self)

    def _ems_health_allowance_hours(self):
        """Yearly self-declared health absence allowance. Same fallback rationale as above,
        except a zero here would flag every single request as over the allowance."""
        return self.ems_health_allowance_hours or self._fields['ems_health_allowance_hours'].default(self)

    @api.depends('limesurvey_pwd_encrypted')
    def _compute_limesurvey_pwd(self):        
        key = self._get_fernet_key()
        f = Fernet(key)
        
        for company in self:
            if company.limesurvey_pwd_encrypted:
                try:
                    company.limesurvey_pwd = f.decrypt(company.limesurvey_pwd_encrypted.encode()).decode()
                except Exception:
                    company.limesurvey_pwd = False
            else:
                company.limesurvey_pwd = False

    def _inverse_limesurvey_pwd(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for company in self:
            if company.limesurvey_pwd:
                company.limesurvey_pwd_encrypted = f.encrypt(company.limesurvey_pwd.encode()).decode()
            else:
                company.limesurvey_pwd_encrypted = False

    @api.depends('google_ws_sa_json_encrypted')
    def _compute_google_ws_sa_json(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for company in self:
            if company.google_ws_sa_json_encrypted:
                try:
                    company.google_ws_sa_json = f.decrypt(company.google_ws_sa_json_encrypted.encode()).decode()
                except Exception:
                    company.google_ws_sa_json = False
            else:
                company.google_ws_sa_json = False

    def _inverse_google_ws_sa_json(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for company in self:
            if company.google_ws_sa_json:
                company.google_ws_sa_json_encrypted = f.encrypt(company.google_ws_sa_json.encode()).decode()
            else:
                company.google_ws_sa_json_encrypted = False
