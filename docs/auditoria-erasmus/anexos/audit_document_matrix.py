# Prints the default documents and checklist of a new students' call, staff call and group mobility, as the
# code creates them (EmsErasmusCall._ems_preparation_documents, _ems_staff_documents, ...). Rolled back.
# Run with odoo shell on ems_auditoria only, in English.
import json
from datetime import timedelta
from odoo import fields
env = env(context=dict(env.context, lang='en_US'))
now = fields.Datetime.now()
out = {}
fields_doc = ['stage', 'name', 'requirement', 'handled_by', 'project', 'confidential', 'file_category', 'due_basis',
              'due_days', 'open_days', 'signers', 'panel_visible']
for audience in ('student', 'staff'):
    call = env['ems.erasmus.call'].create({'name': f'Audit {audience}', 'audience': audience,
                                          'date_open': now, 'date_close': now + timedelta(days=5)})
    docs = (call.document_ids | call.preparation_document_ids).sorted(lambda d: ({'application': 0, 'preparation': 1, 'return': 2}[d.stage], d.sequence))
    out[audience] = {
        'documents': [{name: doc[name] for name in fields_doc} for doc in docs],
        'tasks': [{'stage': t.stage, 'name': t.name, 'requirement': t.requirement, 'project': t.project} for t in call.task_ids],
        'questions': [(q.name, q.kind) for q in call.self_assessment_question_ids],
        'modalities': [(m.name, m.project) for m in call.modality_ids],
        'min_score': call.min_score, 'has_commitment_text': bool(call.commitment_text),
    }
reqs = env['ems.erasmus.group.mobility']._ems_default_requirements()
out['group'] = [{k: v for k, v in vals.items()} for _cmd, _id, vals in reqs]
for vals in out['group']:
    doc = env['ems.erasmus.call.document'].new(vals)
    vals['signers'] = doc.signers
print('AUDIT_DOCS ' + json.dumps(out, default=str, ensure_ascii=False))
env.cr.rollback()
