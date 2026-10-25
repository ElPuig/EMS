# Brings the call documents created before the document records (dev database `ems`, calls of
# 2026-27) to what a new call gets by default (EmsErasmusCall._ems_preparation_documents):
#   - the European Health Insurance Card: confidential, in 01 Data and authorisations;
#   - the authorisations (family, minors travelling abroad) and the inclusion documentation: in 01;
#   - the tickets or boarding passes: in 03 During the mobility.
# Through the ORM, so the stored copy on each document line (confidential, file_category) is
# recomputed too: the record rules and the exports read it there.
# Dry run by default; APPLY=1 commits. Run with odoo shell on the database to fix, after a backup:
#   APPLY=1 odoo shell -d <db> -c <conf> --no-http < 2_corregir.py
import os

Document = env['ems.erasmus.call.document']
HEALTH = ['|', '|', ('name', 'ilike', 'sanit'), ('name', 'ilike', 'health'), ('name', 'ilike', 'salud')]
DATA = ['|', '|', '|', '|', '|', ('name', 'ilike', 'autoritz'), ('name', 'ilike', 'authoris'),
        ('name', 'ilike', 'autoriz'), ('name', 'ilike', 'inclusi'), ('name', 'ilike', 'sanit'),
        ('name', 'ilike', 'health')]
TRAVEL = ['|', '|', ('name', 'ilike', 'bitllet'), ('name', 'ilike', 'ticket'), ('name', 'ilike', 'billete')]

changes = [
    (Document.search([('confidential', '=', False)] + HEALTH), {'confidential': True}),
    (Document.search([('stage', '!=', 'application'), ('file_category', '=', False)] + DATA),
     {'file_category': '01_Dades_i_autoritzacions'}),
    (Document.search([('stage', '!=', 'application'), ('file_category', '=', False)] + TRAVEL),
     {'file_category': '03_Durant_la_mobilitat'}),
]
for documents, vals in changes:
    print('CHANGE', vals, [(document.id, document.call_id.id or document.group_mobility_id.id, document.name)
                           for document in documents])
    documents.write(vals)

health = Document.search(HEALTH)
lines = env['ems.erasmus.application.document'].search([('call_document_id', 'in', health.ids)])
print('HEALTH CARD documents confidential:', all(health.mapped('confidential')),
      '| lines:', len(lines), 'all confidential:', all(lines.mapped('confidential')))
if os.environ.get('APPLY') == '1':
    env.cr.commit()
    print('COMMITTED')
else:
    env.cr.rollback()
    print('DRY RUN: rolled back')
