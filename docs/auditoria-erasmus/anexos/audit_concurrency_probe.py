# -*- coding: utf-8 -*-
"""Audit 2026-10-25: what two simultaneous requests do, with two real database transactions.

Sequential tests cannot show it: the second request's transaction takes its snapshot before the first
one commits, as two clicks at the same moment do. Cases: two first-payment requests for one mobility,
two acceptances of one place offer, two downloads of one export.

It COMMITS fictitious records, so it refuses to run on any database whose name does not contain
"concurrencia": run it on a throwaway copy and drop that copy afterwards, e.g.

    sudo -u postgres createdb -O odoo -T ems_integracion ems_concurrencia_antes
    odoo shell -d ems_concurrencia_antes -c <conf with the code to test> --no-http < audit_concurrency_probe.py
    sudo -u postgres dropdb ems_concurrencia_antes

Prints one CONCURRENCY line per case: what the second transaction got."""

import json

import psycopg2

from odoo import SUPERUSER_ID, api, fields

assert 'concurrencia' in env.cr.dbname, "Only on a throwaway copy named *concurrencia*: this script commits."  # noqa: F821
registry = env.registry  # noqa: F821
results = {}


def new_env(cursor):
    return api.Environment(cursor, SUPERUSER_ID, {'lang': 'en_US', 'tracking_disable': True})


def race(name, setup, first, second_read, second):
    """`setup` commits the records; `first` runs and commits in transaction 1, after transaction 2 has
    already read (`second_read`, which takes its snapshot); then `second` runs in transaction 2."""
    with registry.cursor() as cr0:
        ids = setup(new_env(cr0))
        cr0.commit()
    cr1, cr2 = registry.cursor(), registry.cursor()
    try:
        env1, env2 = new_env(cr1), new_env(cr2)
        second_read(env2, ids)
        first(env1, ids)
        cr1.commit()
        try:
            outcome = second(env2, ids)
            cr2.commit()
            results[name] = f"second transaction committed: {outcome}"
        except psycopg2.Error as error:
            cr2.rollback()
            results[name] = f"second transaction refused by PostgreSQL: {type(error).__name__} ({error.pgcode})"
        except Exception as error:  # an Odoo check (UserError, AccessError...)
            cr2.rollback()
            results[name] = f"second transaction refused by EMS: {type(error).__name__}: {error}"
    finally:
        cr1.close()
        cr2.close()


def application(env, state):
    call = env['ems.erasmus.call'].search([('audience', '=', 'student')], limit=1)
    partner = env['res.partner'].create({'name': 'Concurrency Test Student', 'email': 'concurrency@example.com'})
    application = env['ems.erasmus.application'].create({
        'call_id': call.id, 'partner_id': partner.id, 'modality_id': call.modality_ids[:1].id})
    application.with_context(ems_erasmus_state=True).write({'state': state})  # the audited code needs the flag
    return application


def payment_setup(env):
    mobility = env['ems.erasmus.mobility'].create({'application_id': application(env, 'accepted').id})
    mobility.write({'state': 'preparing', 'grant_amount': 1000})
    return {'mobility': mobility.id}


def count_payments(env, ids):
    env['ems.erasmus.mobility'].browse(ids['mobility']).payment_ids.mapped('amount')


race('two first-payment requests for one mobility', payment_setup,
     lambda env, ids: env['ems.erasmus.mobility'].browse(ids['mobility']).action_request_prefinancing(),
     count_payments,
     lambda env, ids: (env['ems.erasmus.mobility'].browse(ids['mobility']).action_request_prefinancing(),
                       f"{env['ems.erasmus.payment'].search_count([('mobility_id', '=', ids['mobility'])])} "
                       "payments in its snapshot")[1])


def offer_setup(env):
    offer = env['ems.erasmus.offer']._ems_offer(application(env, 'selected'),
                                                fields.Datetime.now().replace(year=2099), notify=False)
    return {'offer': offer.id}


race('two acceptances of one place offer', offer_setup,
     lambda env, ids: env['ems.erasmus.offer'].browse(ids['offer']).action_accept(),
     lambda env, ids: env['ems.erasmus.offer'].browse(ids['offer']).state,
     lambda env, ids: (env['ems.erasmus.offer'].browse(ids['offer']).action_accept(), "accepted twice")[1])


def export_setup(env):
    project = env['ems.erasmus.project'].create({'name': 'CONCURRENCY-TEST', 'kind': 'ka121_vet'})
    return {'export': env['ems.erasmus.export'].create({'scope': 'project', 'project_id': project.id}).id}


race('two downloads of one export', export_setup,
     lambda env, ids: env['ems.erasmus.export'].browse(ids['export'])._ems_zip().close(),
     lambda env, ids: env['ems.erasmus.export'].browse(ids['export']).state,
     lambda env, ids: (env['ems.erasmus.export'].browse(ids['export'])._ems_zip().close(), "downloaded twice")[1])

for name, outcome in results.items():
    print("CONCURRENCY", json.dumps({'case': name, 'outcome': outcome}))
