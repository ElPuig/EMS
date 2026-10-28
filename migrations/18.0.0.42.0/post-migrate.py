import base64
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.ems.models.employees.employee import write_photo

_logger = logging.getLogger(__name__)

# The activities that wait for the Head: Odoo's approval and EMS's document validation.
HEAD_ACTIVITY_XMLIDS = ('hr_holidays.mail_act_leave_approval', 'ems.mail_activity_absence_document_validate')


def migrate(cr, version):
    _hand_over_area_manager_absences(cr)
    _repair_text_plain_placeholders(cr)


def _hand_over_area_manager_absences(cr):
    """Issue #693: an Area Manager is now the Head of their own absence, instead of the Director.
    Their stored approver is recomputed, and the requests they have not validated yet pass to them
    with their activity and followers, without emailing anybody. post-migrate: it goes through the
    ORM. A clean install computes the approver from the start, so it needs no post_init_hook
    counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    managers = env['hr.department'].search([('is_top_level', '=', True)]).manager_id.with_context(
        active_test=False)
    managers._compute_leave_manager()
    managers.flush_recordset()

    leaves = env['hr.leave'].search([
        ('employee_id', 'in', managers.ids),
        ('ems_status', 'in', ['pending', 'pending_validation']),
    ])
    activity_types = [env.ref(xmlid).id for xmlid in HEAD_ACTIVITY_XMLIDS]
    for leave in leaves:
        approver = leave.employee_id.leave_manager_id
        activities = leave.activity_ids.filtered(
            lambda activity: activity.activity_type_id.id in activity_types and activity.user_id != approver)
        activities.with_context(mail_activity_quick_update=True).write({'user_id': approver.id})
    leaves._ems_sync_followers(announce=False)
    _logger.info("Issue #693: %s Area Managers are the Head of their own absence (%s open requests "
                 "handed over).", len(managers), len(leaves))


def _repair_text_plain_placeholders(cr):
    """Issue #714: the initials placeholder of a teacher whose EMS account a Head of Studies
    created was stored as text/plain, so it showed as "Binary file". Generate it again and write
    it as the superuser on every employee and contact whose photo is an SVG stored that way (or
    whose file is missing). The stored bytes are never trusted: an SVG that wasn't Odoo's own must
    not end up served as an image. post-migrate: it goes through the ORM. A clean install has no
    such photos, so it needs no post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT res_model, array_agg(res_id)
          FROM ir_attachment
         WHERE res_model IN ('hr.employee', 'res.partner')
           AND res_field = 'image_1920'
           AND mimetype = 'text/plain'
         GROUP BY res_model
    """)
    repaired = 0
    for model, ids in cr.fetchall():
        for record in env[model].with_context(active_test=False).browse(ids).exists():
            # A missing file (empty read) is just as broken, and a placeholder is better.
            raw = base64.b64decode(record.image_1920 or b'')
            if not raw or raw.lstrip().startswith(b'<'):
                write_photo(record, record._avatar_generate_svg())
                repaired += 1
    _logger.info("Issue #714: %s initials placeholders stored as text/plain rewritten.", repaired)
