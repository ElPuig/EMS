# -*- coding: utf-8 -*-

import logging

from markupsafe import Markup

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _staff_places_per_project(env):
    """Issue #772: a staff call no longer has modalities. Each staff modality's places go to the
    project that pays them (the one its mobilities already use, or the only active project of its
    kind), the mobilities without a project get it, and the modalities are removed. Places that
    cannot be resolved are left for the Erasmus team, with a note on the call."""
    cr = env.cr
    cr.execute("""
        SELECT modality.id, modality.call_id, modality.project, COALESCE(modality.places, 0),
               COALESCE(modality.name->>'ca_ES', modality.name->>'en_US')
          FROM ems_erasmus_call_modality modality
          JOIN ems_erasmus_call call ON call.id = modality.call_id
         WHERE call.audience = 'staff'
         ORDER BY modality.call_id, modality.sequence, modality.id
    """)
    modalities = cr.fetchall()
    if not modalities:
        return
    Line = env['ems.erasmus.call.project']
    Project = env['ems.erasmus.project']
    for modality_id, call_id, kind, places, name in modalities:
        cr.execute("""SELECT DISTINCT project_id FROM ems_erasmus_mobility
                       WHERE modality_id = %s AND project_id IS NOT NULL""", [modality_id])
        used = [row[0] for row in cr.fetchall()]
        candidates = used or (Project.search([('kind', '=', kind)]).ids if kind else [])
        project_id = candidates[0] if len(candidates) == 1 else None
        # Every project already used keeps a line, so its mobilities stay valid.
        for used_id in set(used) | ({project_id} if project_id else set()):
            line = Line.search([('call_id', '=', call_id), ('project_id', '=', used_id)])
            add = places if used_id == project_id else 0
            if line:
                line.places += add
            else:
                Line.create({'call_id': call_id, 'project_id': used_id, 'places': add})
        if project_id:
            cr.execute("""UPDATE ems_erasmus_mobility SET project_id = %s
                           WHERE modality_id = %s AND project_id IS NULL""", [project_id, modality_id])
        elif places:
            # In Catalan, the centre's language: a one-off note for the Erasmus team.
            env['ems.erasmus.call'].browse(call_id).message_post(body=Markup(
                "<p>Places per projecte (#772): les %s places de <b>%s</b> no s'han pogut donar a un sol "
                "projecte. Afegiu-les a la pestanya «Places per projecte».</p>") % (places, name))
            _logger.warning("Staff call %s: %s places of modality %s left without a project.", call_id, places, name)
    ids = [row[0] for row in modalities]
    for table in ('ems_erasmus_application', 'ems_erasmus_mobility', 'ems_erasmus_offer',
                  'ems_erasmus_resolution_line'):
        cr.execute(f"UPDATE {table} SET modality_id = NULL WHERE modality_id = ANY(%s)", [ids])
    env.invalidate_all()
    env['ems.erasmus.call.modality'].browse(ids).unlink()
    _logger.info("Issue #772: %s staff modalities turned into places per project.", len(ids))


def _keep_group_rankings_by_average(cr):
    """Issue #773: a group mobility ranked before the score keeps its ranking by the record average
    (its selection criteria were published so): no recomputation."""
    cr.execute("UPDATE ems_erasmus_group_mobility SET rank_by_score = FALSE WHERE ranking_date IS NOT NULL")
    _logger.info("Issue #773: %s group mobilities keep their ranking by the average.", cr.rowcount)


def _drop_minute_annex_links(cr):
    """Issue #803: a minute's annexes are uploaded files now, so the field that linked controlled
    documents (annex_document_ids) is gone. Odoo leaves the relation table of a removed field
    behind: drop it (empty in production when checked, 2026-11-10; a new installation never
    creates it)."""
    cr.execute("DROP TABLE IF EXISTS ems_minute_annex_rel")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _staff_places_per_project(env)
    _keep_group_rankings_by_average(cr)
    _drop_minute_annex_links(cr)
