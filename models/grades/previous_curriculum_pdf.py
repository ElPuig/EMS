# -*- coding: utf-8 -*-

import re

from .academic_record_pdf import AcademicRecordPdfError, _value_below, pdf_to_text

# Reader of the "Historial acadèmic" PDF of a VET student who studied a previous curriculum (issue
# #672): the LOE cycles organised in units (UF) instead of learning outcomes, which the Departament
# d'Educació kept in SAGA before Esfera. Their modules do not map onto the current curriculum, so
# everything is returned as printed, to be kept as text: the student's identifier (IDALU), the
# centre, the curriculum, the academic years and every module and unit with its hours, grade and
# sitting (convocatòria).
#
# The grades table has two halves side by side - the module (code, name, hours, grade, sitting) and
# its units (code, name, hours, grade, sitting) - and both names wrap over several lines. Each line
# is split where its unit code starts, near the column of the header's "Unitat Formativa", and each
# half is read on its own: a half starting with a code opens a row, any other half continues the
# name of the row above.

_HEADING = 'unitats formatives'
_TABLE_HEADER = 'Unitat Formativa'
# "001 MP1. Sistemes informàtics   198   6   Ext." - hours, grade and sitting only once graded.
_MODULE_RE = re.compile(
    r"^(?P<code>\d{3})\s+(?P<name>.+?)"
    r"(?:\s{2,}(?P<hours>\d+)(?:\s+(?P<grade>(?!Ord\.|Ext\.)\S+))?(?:\s+(?P<sitting>Ord\.|Ext\.))?)?\s*$")
# "00101 UF1. Instal·lació, configuració i   71   7   1" - an ungraded unit has no sitting.
_UNIT_RE = re.compile(
    r"^(?P<code>\d{5})\s+(?P<name>.+?)\s{2,}(?P<hours>\d+)(?:\s+(?P<grade>\S+))?(?:\s+(?P<sitting>\d+))?\s*$")
_UNIT_CODE_RE = re.compile(r"(?<!\S)\d{5}\s")
_YEARS_RE = re.compile(r"(?P<start>\d{4})\D+(?P<end>\d{4})")
# Where the grades of a page end: the signatures, or the record's closing sections.
_TABLE_END = ('Observacions', 'Signatura del secretari', 'Diligència de validesa')
# Passing grades as SAGA prints them: a number from 5, "Ap" (apte, the work placement), and a
# module or unit convalidated or exempted.
_PASSED_TEXTS = {'AP', 'A', 'APTE', 'CV', 'CONV', 'CONVALIDAT', 'EX', 'EXEMPT'}


def grade_passes(grade):
    """Whether a grade as printed by SAGA is a pass."""
    text = (grade or '').strip().upper()
    match = re.match(r"^(\d{1,2})(?:[.,]\d+)?$", text)
    if match:
        return int(match.group(1)) >= 5
    return text in _PASSED_TEXTS


def parse_previous_curriculum_record(pdf_bytes):
    return parse_previous_curriculum_record_text(pdf_to_text(pdf_bytes))


def _int(value):
    return int(value) if value else 0


def _row(match, kind):
    return {'kind': kind, 'code': match.group('code'), 'name': match.group('name').strip(),
            'hours': _int(match.group('hours')), 'grade': match.group('grade') or '',
            'sitting': match.group('sitting') or '', 'units': []}


def _halves(line, split):
    """The module and unit halves of a table line, split where the unit code starts: a few
    characters right of the "Unitat Formativa" title, which the module's sitting ("Ext.") reaches
    under. A line with no unit code (a wrapped name) is split a little right of the title too."""
    code = _UNIT_CODE_RE.search(line, max(split - 4, 0))
    split = code.start() if code else split + 3
    return line[:split].strip(), line[split:].strip()


def _join(name, continuation):
    """A wrapped name: a word cut at its hyphen ("objecte-" / "relacionals") is joined as is."""
    return f"{name}{continuation}" if name.endswith('-') else f"{name} {continuation}"


def _observations(lines):
    """The text of the "Observacions" box, if any."""
    for index, line in enumerate(lines):
        if line.strip() == 'Observacions':
            text = []
            for value in lines[index + 1:]:
                if value.strip().startswith('Diligència'):
                    break
                if value.strip():
                    text.append(value.strip())
            return '\n'.join(text)
    return ''


def parse_previous_curriculum_record_text(text):
    lines = text.splitlines()
    if not any(_HEADING in line for line in lines):
        raise AcademicRecordPdfError("This is not a previous curriculum academic history.")
    years = _YEARS_RE.search(_value_below(lines, 'Codi del centre', 'Anys acadèmics'))
    record = {
        'student_identifier': _value_below(lines, 'Cognoms i nom', "Identificador de l'alumne/a"),
        'student_name': _value_below(lines, 'Cognoms i nom', 'Cognoms i nom'),
        'centre_code': _value_below(lines, 'Municipi', 'Codi'),
        'centre_name': _value_below(lines, 'Municipi', 'Nom'),
        'curriculum_code': _value_below(lines, 'Nom del cicle formatiu', 'Codi'),
        'curriculum_name': _value_below(lines, 'Nom del cicle formatiu', 'Nom del cicle formatiu'),
        'start_year': int(years.group('start')) if years else 0,
        'end_year': int(years.group('end')) if years else 0,
        'notes': _observations(lines),
        'modules': [],
    }
    split = None
    module = unit = None
    for line in lines:
        if _TABLE_HEADER in line and 'Mòdul' in line:
            split = line.index(_TABLE_HEADER)
            continue
        if split is None:
            continue
        if line.strip().startswith(_TABLE_END):
            split = None
            continue
        left, right = _halves(line, split)
        if left:
            match = _MODULE_RE.match(left)
            if match:
                module = _row(match, 'module')
                record['modules'].append(module)
                unit = None
            elif module is not None:
                module['name'] = _join(module['name'], left)
        if right and module is not None:
            match = _UNIT_RE.match(right)
            if match:
                unit = _row(match, 'unit')
                module['units'].append(unit)
            elif unit is not None:
                unit['name'] = _join(unit['name'], right)
    if not record['modules']:
        raise AcademicRecordPdfError("No module could be read from the academic history.")
    return record
