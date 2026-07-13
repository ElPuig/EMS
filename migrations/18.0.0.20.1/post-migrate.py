# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Activity types whose recipients used to be derived from a security group, now
# configured in Academic Management > Configuration > Task Assignment.
SEEDED_ASSIGNMENTS = [
    ('mail_activity_student_document_review', 'group_secretary'),
    ('mail_activity_enrollment_comment', 'group_secretary'),
]


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Seed the new recipient lists with whoever receives these tasks today, so nobody
    # silently stops being notified on upgrade. Members of the source group include the
    # administrators, who are in it only through the implied_ids chain
    # (group_academic_admin -> group_secretary_admin -> group_secretary) — they are kept
    # here on purpose so the behaviour does not change under anyone's feet; the centre
    # removes them from the new screen when it sees fit.
    #
    # OdooBot is the one exception: it is the system user behind crons and imports, its
    # inbox is read by nobody, and it only ever landed in the group through that same
    # chain. Seeding it would just create tasks nobody will ever see.
    for type_xmlid, group_xmlid in SEEDED_ASSIGNMENTS:
        activity_type = env.ref(f'ems.{type_xmlid}', raise_if_not_found=False)
        group = env.ref(f'ems.{group_xmlid}', raise_if_not_found=False)
        if not activity_type or not group:
            _logger.warning(
                "Task Assignment: could not seed %s from %s (record not found).",
                type_xmlid, group_xmlid)
            continue

        # data/main/ems.mail_activity_type.xml declares the flag, but that file is
        # noupdate="1" and these records already exist here, so Odoo skips it: the
        # flag has to be set by hand on an existing database.
        activity_type.ems_task_assignment = True

        # Idempotent: never overwrite a list the centre has already configured.
        if activity_type.ems_assignee_ids:
            continue

        users = group.users.filtered(lambda user: user.id != SUPERUSER_ID)
        activity_type.ems_assignee_ids = [(6, 0, users.ids)]
        _logger.info(
            "Task Assignment: seeded %s with %d user(s): %s",
            type_xmlid, len(users), ', '.join(users.mapped('login')) or '-')
