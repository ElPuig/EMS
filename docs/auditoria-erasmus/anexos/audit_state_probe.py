# Probe (rolled back): can the Erasmus technician write a state or a frozen value directly (RPC-like
# ORM write as that user), skipping the actions' checks? Run with odoo shell on ems_auditoria only.
from odoo.exceptions import AccessError, UserError, ValidationError
env = env(context=dict(env.context, lang='en_US'))
tech = env['res.users'].with_context(no_reset_password=True).create({
    'name': 'Probe Technician', 'login': 'probe_tech_state_x',
    'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('ems.group_erasmus').id])]})
def attempt(label, record, vals):
    if not record:
        print('PROBE', label, 'NO RECORD'); return
    try:
        with env.cr.savepoint():
            record.with_user(tech).write(vals)
            env.flush_all()
            print('PROBE', label, 'ALLOWED')
            raise RuntimeError('rollback')
    except RuntimeError:
        pass
    except (AccessError, UserError, ValidationError) as error:
        print('PROBE', label, 'REFUSED', type(error).__name__)
    env.invalidate_all()
M = lambda model, domain: env[model].search(domain, limit=1)
attempt('call.state', M('ems.erasmus.call', [('state', '=', 'published')]) or M('ems.erasmus.call', []), {'state': 'closed'})
attempt('application.state', M('ems.erasmus.application', []), {'state': 'accepted'})
attempt('application.grade_average_ems', M('ems.erasmus.application', [('scoring_frozen_date', '!=', False)]), {'grade_average_ems': 9.99})
attempt('mobility.state', M('ems.erasmus.mobility', [('state', '=', 'preparing')]) or M('ems.erasmus.mobility', []), {'state': 'done'})
attempt('group_mobility.state', M('ems.erasmus.group.mobility', []), {'state': 'done'})
attempt('group_registration.result', M('ems.erasmus.group.registration', []), {'result': 'selected'})
attempt('offer.state', M('ems.erasmus.offer', []), {'state': 'accepted'})
attempt('interview.state', M('ems.erasmus.interview', []), {'state': 'submitted'})
attempt('claim.state', M('ems.erasmus.claim', []), {'state': 'resolved'})
attempt('payment.state', M('ems.erasmus.payment', []), {'state': 'paid'})
attempt('resolution(draft).state', M('ems.erasmus.resolution', [('state', '=', 'draft')]), {'state': 'published'})
env.cr.rollback()
