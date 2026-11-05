# -*- coding: utf-8 -*-
"""The document records of Erasmus+ (a project, its mobilities and each participant's record): the
categories they are organised in and the checks on the files that go in and out of them. Plain
constants and helpers, imported by the models; see docs/en/developers/erasmus/records.md."""

import os
import re

from odoo import _
from odoo.exceptions import UserError

# The categories of an Erasmus+ project's documents: the code is its folder name in the exported ZIP.
PROJECT_CATEGORIES = [
    ('01_Projecte', "01 Project"),
    ('02_Mobilitats', "02 Mobilities"),
    ('03_Economia', "03 Finances"),
    ('04_Impacte_i_difusio', "04 Impact and dissemination"),
    ('05_Informe_final_i_auditoria', "05 Final report and audit"),
]
# The four categories of every participant's record, the same for everyone; what each holds depends
# on the call's documents (the only list of what is required).
PARTICIPANT_CATEGORIES = [
    ('01_Dades_i_autoritzacions', "01 Data and authorisations"),
    ('02_Abans_de_la_mobilitat', "02 Before the mobility"),
    ('03_Durant_la_mobilitat', "03 During the mobility"),
    ('04_Despres_de_la_mobilitat', "04 After the mobility"),
]
# Where a call document goes in the record when it says nothing.
STAGE_CATEGORIES = {'application': '01_Dades_i_autoritzacions', 'preparation': '02_Abans_de_la_mobilitat',
                    'return': '04_Despres_de_la_mobilitat'}
# The SEPIE folders a call document had before the records (never released): the category each one
# goes to, run once by EmsErasmusCallDocument._auto_init where the old column is still there. The rest
# stay empty, so their stage decides, as for a new call. A group mobility's common documents in
# "link with the centre" (the group learning agreement) are prepared before leaving, by their stage.
LEGACY_FOLDER_SQL = """
    UPDATE ems_erasmus_call_document
       SET file_category = CASE
               WHEN sepie_folder = '07_Viajes' THEN '03_Durant_la_mobilitat'
               WHEN sepie_folder = '13_EvaluacionImpactoDifusion' AND group_audience = 'collective'
                   THEN '03_Durant_la_mobilitat'
               WHEN sepie_folder = '11_ApoyoInclusion' THEN '01_Dades_i_autoritzacions'
               WHEN sepie_folder = '03_Vinculacion' AND group_audience IS DISTINCT FROM 'collective'
                   THEN '01_Dades_i_autoritzacions'
               WHEN sepie_folder = '05_Seguros' AND handled_by IS DISTINCT FROM 'team'
                   THEN '01_Dades_i_autoritzacions'
           END,
           confidential = COALESCE(confidential, FALSE)
               OR (sepie_folder = '05_Seguros' AND handled_by IS DISTINCT FROM 'team')
     WHERE file_category IS NULL AND sepie_folder IS NOT NULL
"""
# Files the participants never upload: programs and scripts, and pages that would run in the browser.
FORBIDDEN_EXTENSIONS = {
    '.apk', '.app', '.bat', '.bin', '.cmd', '.com', '.cpl', '.dll', '.dmg', '.exe', '.hta', '.htm', '.html', '.jar',
    '.js', '.jse', '.lnk', '.msi', '.php', '.pif', '.ps1', '.py', '.reg', '.scr', '.sh', '.svg', '.vbe', '.vbs',
    '.wsf', '.xhtml',
}
MAX_NAME = 150


def safe_name(name):
    """A file or folder name that works on every system and can never climb out of its folder in a
    ZIP: no separators, control characters or reserved characters, no leading dots, accents kept."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]+', '_', (name or '').strip())
    name = re.sub(r'\.{2,}', '.', name).strip('. ')
    if len(name) > MAX_NAME:
        stem, extension = os.path.splitext(name)
        name = stem[:MAX_NAME - len(extension)].rstrip('. ') + extension
    return name or '_'


def check_upload(name):
    """The name an uploaded file is kept with: only its own name (never a path), checked against the
    files never accepted."""
    name = safe_name(os.path.basename((name or '').replace('\\', '/')))
    if os.path.splitext(name)[1].lower() in FORBIDDEN_EXTENSIONS:
        raise UserError(_("This kind of file cannot be uploaded: %s", name))
    return name
