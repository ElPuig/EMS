# -*- coding: utf-8 -*-

import re

from .academic_record_pdf import AcademicRecordPdfError, _value_below, pdf_to_text

# Reader of the documents of a VET student who studied a previous curriculum (issue #672): the LOE
# cycles organised in units (UF) instead of learning outcomes, which the Departament d'Educació kept
# in SAGA before Esfera. Two documents are read (issue #732): the "Historial acadèmic" and the
# "Certificat de qualificacions de mòduls i unitats formatives". Their modules do not map onto the
# current curriculum, so everything is returned as printed, to be kept as text: who the student is
# (the IDALU on the academic history, the DNI/NIE on the certificate), the centre, the curriculum,
# the academic years (only on the academic history) and every module and unit with its hours, grade
# and sitting (convocatòria).
#
# Both documents print the same grades table, with two halves side by side - the module (code,
# name, hours, grade, sitting) and its units (code, name, hours, grade, sitting) - and both names
# wrap over several lines. Each line is split where its unit code starts, near the column of the
# header's "Unitat formativa", and each half is read on its own: a half starting with a code opens
# a row, any other half continues the name of the row above.

_HEADING = 'unitats formatives'
_CERTIFICATE_HEADING = 'Certificat de qualificacions'
_TABLE_HEADER = 'unitat formativa'
# Codes are digits ("001", "00101"), or letters for a module of the centre's own ("AOC", "AOCOA"),
# then told apart from a wrapped name by the "MP"/"UF" that follows them.
_MODULE_CODE = r"(?:\d{3}|[0-9A-Z]{3}(?=\s+MP\d))"
_UNIT_CODE = r"(?:\d{5}|[0-9A-Z]{5}(?=\s+UF\d))"
# "001 MP1. Sistemes informàtics   198   6   Ext." - hours, grade and sitting only once graded.
_MODULE_RE = re.compile(
    rf"^(?P<code>{_MODULE_CODE})\s+(?P<name>.+?)"
    r"(?:\s{2,}(?P<hours>\d+)(?:\s+(?P<grade>(?!Ord\.|Ext\.)\S+))?(?:\s+(?P<sitting>Ord\.|Ext\.))?)?\s*$")
# "00101 UF1. Instal·lació, configuració i   71   7   1" - an ungraded unit has no sitting.
_UNIT_RE = re.compile(
    rf"^(?P<code>{_UNIT_CODE})\s+(?P<name>.+?)\s{{2,}}(?P<hours>\d+)(?:\s+(?P<grade>\S+))?(?:\s+(?P<sitting>\d+))?\s*$")
_UNIT_CODE_RE = re.compile(rf"(?<!\S){_UNIT_CODE}\s")
# Where a wrapped name starts in a line with no code: after a gap, in the units' column.
_TEXT_START_RE = re.compile(r"(?:^|(?<=\s\s))\S")
_YEARS_RE = re.compile(r"(?P<start>\d{4})\D+(?P<end>\d{4})")
# Where the grades of a page end: the signatures, the record's closing sections, or the page's
# footer (the document's form code, "Y508-002/06-10"), as a certificate's page has no signatures.
_TABLE_END = ('Observacions', 'Signatura del secretari', 'Diligència de validesa', 'I, perquè consti')
_FOOTER_RE = re.compile(r"^[A-Z]\d{3}-\d{3}/")
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
    characters right of the "Unitat formativa" title, which the module's sitting ("Ext.") reaches
    under. A line with no unit code (a wrapped name) is split where text starts in the units'
    column, which is the codes' own column; else a little right of the title."""
    code = _UNIT_CODE_RE.search(line, max(split - 4, 0))
    if code:
        split = code.start()
    else:
        starts = [match.start() for match in _TEXT_START_RE.finditer(line) if split - 1 <= match.start() <= split + 8]
        split = starts[0] if starts else split + 3
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


def _value_after(lines, header, label):
    """The text printed from `label`'s column to the end of the row that follows the header line
    `header`: for a value not aligned with its title's start, like the certificate's DNI/NIE."""
    for index, line in enumerate(lines):
        if header in line and label in line:
            column = line.index(label)
            for value_line in lines[index + 1:index + 4]:
                if value_line.strip():
                    return value_line[column:].strip()
    return ''


def _after(lines, anchor):
    """The lines from the first one holding `anchor` on: to read a block whose titles repeat."""
    for index, line in enumerate(lines):
        if anchor in line:
            return lines[index:]
    return []


def _history_header(lines):
    years = _YEARS_RE.search(_value_below(lines, 'Codi del centre', 'Anys acadèmics'))
    return {
        'student_identifier': _value_below(lines, 'Cognoms i nom', "Identificador de l'alumne/a"),
        'student_document_id': '',
        'student_name': _value_below(lines, 'Cognoms i nom', 'Cognoms i nom'),
        'centre_code': _value_below(lines, 'Municipi', 'Codi'),
        'centre_name': _value_below(lines, 'Municipi', 'Nom'),
        'curriculum_code': _value_below(lines, 'Nom del cicle formatiu', 'Codi'),
        'curriculum_name': _value_below(lines, 'Nom del cicle formatiu', 'Nom del cicle formatiu'),
        'start_year': int(years.group('start')) if years else 0,
        'end_year': int(years.group('end')) if years else 0,
        'notes': _observations(lines),
    }


def _certificate_header(lines):
    """The certificate names the student with their DNI/NIE (no IDALU) and gives no years."""
    centre = _after(lines, 'Dades del centre')
    curriculum = _after(lines, 'Matriculat al cicle formatiu')
    student = "Nom i cognoms de l'alumn"
    document_id = _value_after(lines, student, 'DNI').split()
    return {
        'student_identifier': '',
        'student_document_id': document_id[-1] if document_id else '',
        'student_name': _value_below(lines, student, student),
        'centre_code': _value_below(centre, 'Nom', 'Codi'),
        'centre_name': _value_below(centre, 'Codi', 'Nom'),
        'curriculum_code': _value_below(curriculum, 'Nom', 'Codi'),
        'curriculum_name': _value_below(curriculum, 'Codi', 'Nom'),
        'start_year': 0,
        'end_year': 0,
        'notes': '',
    }


def parse_previous_curriculum_record_text(text):
    lines = text.splitlines()
    if any(_CERTIFICATE_HEADING in line for line in lines):
        record = {'is_certificate': True, **_certificate_header(lines)}
    elif any(_HEADING in line for line in lines):
        record = {'is_certificate': False, **_history_header(lines)}
    else:
        raise AcademicRecordPdfError("This is not a previous curriculum academic history or grades certificate.")
    record['modules'] = []
    split = None
    module = unit = None
    for line in lines:
        if _TABLE_HEADER in line.lower() and 'Mòdul' in line:
            split = line.lower().index(_TABLE_HEADER)
            continue
        if split is None:
            continue
        if line.strip().startswith(_TABLE_END) or _FOOTER_RE.match(line.strip()):
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
        raise AcademicRecordPdfError("No module could be read from the document.")
    return record
