# -*- coding: utf-8 -*-

import re
import subprocess
from collections import Counter

# Reader of the "Expedient acadèmic" PDF that the Departament d'Educació's Esfera issues for a VET
# student (issue #585): the certificate a student brings when transferring from another centre.
# Odoo's own PyPDF2 glues the table's columns together ("10156_IC10_01RA": level 1 and the code),
# so the text is taken with poppler's pdftotext in layout mode (apt-requirements.txt), which keeps
# one table row per line with its columns apart.
#
# Two layouts of the same record are read (issue #705): the PDF Esfera itself issues, and Esfera's
# record screen printed to PDF (what some private centres hand over). The printed one shows the
# grades as Esfera's short codes ("A8", "PQ"...), prints a learning outcome's code without its
# level and in the middle of its wrapped name, and has no study token in its heading.
#
# Only the data the academic history needs is read: the student's identifier (IDALU), the study,
# and, per course the certificate evaluates, the evaluating centre and the grade of every module
# (MP), learning outcome (RA) and work placement (EM). Everything is returned as plain data; the
# wizard maps it to EMS records and the user validates it before anything is written.

# A table row: the level (not printed on a printed record's outcome rows), then the code, which
# always holds an underscore ("0156_IC10", "M_OP_09", "0156_IC10_01RA"). Continuation lines (a
# wrapped name, type or grade) do not start like this and are folded into the row above.
_ROW_RE = re.compile(r"^\s*(?:(?P<level>\d)\s+)?(?P<code>[A-Z0-9]+(?:_[A-Z0-9]+)+)(?:\s{2,}(?P<rest>.*))?$")
# The code of a learning outcome or of a work placement: "<module>_<NN>RA" / "<module>_<NN>EM".
_OUTCOME_CODE_RE = re.compile(r"^(?P<module>.+)_(?P<number>\d{2})(?P<kind>RA|EM)$")
# The qualification column, read from the type column onwards (the name may hold anything).
# A module's type is "MP", or "MP_OP_CEN" (wrapped over three lines as "MP_" / "OP_C" / "EN") for
# an optional module of the centre that issued it.
_TYPE_RE = re.compile(r"\s(?P<type>(?:MP|RA|EM)\S*)\s+(?P<after>.*)$")
_TYPE_START_RE = re.compile(r"\s(?=(?:MP|RA|EM)\S*\s)")
_QUALIFICATION_RE = re.compile(
    r"(?P<text>Assolit-\d+|No assolit|Pendent de qualificar|Pendent de|Pendent|No presentat"
    r"|Convalidat|Exempt|No apte|Apte|A\d{1,2}|NA|PQ|PDT|NP|CV|EX|NAP|AP|\d{1,2}(?:[.,]\d+)?)(?:\s|$)")
# Esfera's short codes, as a printed record shows them, read as the issued PDF's own wording.
_SHORT_QUALIFICATIONS = {
    'NA': 'No assolit', 'PQ': 'Pendent de qualificar', 'PDT': 'Pendent', 'NP': 'No presentat',
    'CV': 'Convalidat', 'EX': 'Exempt', 'NAP': 'No apte', 'AP': 'Apte',
}
_COURSE_RE = re.compile(r"^\s*(?P<start>\d{4})[/-](?P<end>\d{4})\s+(?P<level>\d)\S*\s{2,}(?P<study>.+?)\s*$")
# A study token as the issued PDF's heading ends with it ("CFPM IC10"), and as every module code
# of the study ends with it ("0156_IC10").
_STUDY_TOKEN_RE = re.compile(r"^(?=.*[A-Z])[A-Z0-9]{3,6}$")


class AcademicRecordPdfError(Exception):
    """The file is not an academic record this reader understands."""


def pdf_to_text(pdf_bytes):
    """The PDF's text in layout mode (columns kept apart)."""
    try:
        result = subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', '-', '-'],
                                input=pdf_bytes, capture_output=True, timeout=60, check=True)
    except FileNotFoundError as error:
        raise AcademicRecordPdfError("pdftotext is not installed (poppler-utils).") from error
    except subprocess.SubprocessError as error:
        raise AcademicRecordPdfError("The file could not be read as a PDF.") from error
    return result.stdout.decode('utf-8', errors='replace')


def parse_academic_record(pdf_bytes):
    return parse_academic_record_text(pdf_to_text(pdf_bytes))


def _value_below(lines, header, label):
    """The value printed under `label` in the row that follows the header line `header`: layout
    mode aligns a value with its column title."""
    for index, line in enumerate(lines):
        if header in line and label in line:
            column = line.index(label)
            for value_line in lines[index + 1:index + 4]:
                if value_line.strip():
                    return value_line[column:].split('  ')[0].strip()
    return ''


def _qualification_text(text):
    """A qualification in the issued PDF's wording: "A8" -> "Assolit-8", "PQ" -> "Pendent de
    qualificar"."""
    if re.match(r"^A\d{1,2}$", text):
        return f"Assolit-{text[1:]}"
    return _SHORT_QUALIFICATIONS.get(text, text)


def _study_token(heading_tokens, modules):
    """The study token: the heading's last word on an issued PDF, else the one most module codes
    end with (a printed record's heading names no study)."""
    if heading_tokens and _STUDY_TOKEN_RE.match(heading_tokens[-1]):
        return heading_tokens[-1]
    tokens = Counter(module['code'].rsplit('_', 1)[-1] for module in modules)
    return next((token for token, _count in tokens.most_common() if _STUDY_TOKEN_RE.match(token)), '')


def _type_and_qualification(rest):
    """The type column and the qualification after it. On a printed record an outcome's name may
    share the line with its code, so the last type token followed by a qualification is the one."""
    text = ' ' + rest
    for start in reversed([match.start() for match in _TYPE_START_RE.finditer(text)]):
        type_match = _TYPE_RE.match(text, start)
        qualification = _QUALIFICATION_RE.match(type_match.group('after'))
        if qualification:
            return type_match, qualification
    return _TYPE_RE.search(text), None


def _grade(text):
    """(score, is_scored) of a qualification text. "Assolit-7" and a plain number are scored; a
    learning outcome "No assolit" carries no number and is left unscored (not passed)."""
    match = re.match(r"^(?:Assolit-)?(\d{1,2})(?:[.,]\d+)?$", text)
    if match:
        return int(match.group(1)), True
    return 0, False


def parse_academic_record_text(text):
    lines = text.splitlines()
    heading = next((line for line in lines if 'Expedient acadèmic' in line), None)
    if heading is None:
        raise AcademicRecordPdfError("This is not an academic record (Expedient acadèmic).")
    study_tokens = heading.split('Expedient acadèmic', 1)[1].split()
    record = {
        'student_identifier': _value_below(lines, 'Cognoms i nom', "Identificador de l'alumne/a"),
        'student_name': _value_below(lines, 'Cognoms i nom', 'Cognoms i nom'),
        'courses': [],
    }
    course = None
    in_results = False
    last_row = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('Centre que avalua'):
            # The first line under its "Codi  Nom" header (a printed record leaves blank lines).
            centre_line = next((value for value in lines[index + 1:index + 6]
                                if value.strip() and not value.strip().startswith('Codi')), '')
            parts = re.split(r"\s{2,}", centre_line.strip(), maxsplit=1)
            course = {'centre_code': parts[0], 'centre_name': parts[1] if len(parts) > 1 else '',
                      'course': '', 'level': '', 'study_name': '', 'modules': []}
            record['courses'].append(course)
            in_results = False
            continue
        if course is None:
            continue
        if not course['course']:
            match = _COURSE_RE.match(line)
            if match:
                course.update(course=f"{match.group('start')}-{match.group('end')}",
                              level=match.group('level'), study_name=match.group('study'))
                continue
        if stripped.startswith("Resultats de l'avaluació"):
            in_results = True
            continue
        if stripped.startswith(('Observacions', 'Qualificació final', 'Dades de sortida')):
            in_results = False
            last_row = None
            continue
        if not in_results:
            continue
        match = _ROW_RE.match(line)
        if not match:
            # A wrapped "Pendent de / qualificar" grade completes the row above.
            if last_row is not None and stripped == 'qualificar' and last_row['text'] == 'Pendent de':
                last_row['text'] = 'Pendent de qualificar'
            continue
        code = match.group('code')
        rest = match.group('rest') or ''
        type_match, qualification = _type_and_qualification(rest)
        text_value = _qualification_text(qualification.group('text')) if qualification else ''
        # After the qualification come the sitting (convocatòria) and, on a module, its hours.
        numbers = re.findall(r"\b\d+\b", type_match.group('after')[qualification.end():]) \
            if qualification else []
        outcome_match = _OUTCOME_CODE_RE.match(code)
        if outcome_match and course['modules'] \
                and course['modules'][-1]['code'] == outcome_match.group('module'):
            score, is_scored = _grade(text_value)
            last_row = {'code': code, 'kind': outcome_match.group('kind').lower(),
                        'number': outcome_match.group('number'), 'text': text_value,
                        'score': score, 'is_scored': is_scored}
            course['modules'][-1]['outcomes'].append(last_row)
        else:
            name = re.split(r"\s{2,}", rest.strip(), maxsplit=1)[0]
            last_row = {'code': code, 'name': name, 'text': text_value, 'outcomes': [],
                        'is_optional': type_match is not None and type_match.group('type').startswith('MP_'),
                        'hours': int(numbers[-1]) if len(numbers) > 1 else 0}
            course['modules'].append(last_row)
    for module in (module for course in record['courses'] for module in course['modules']):
        module['grade'], module['has_grade'] = _grade(module['text'])
    # A course block with no module (e.g. the course a transfer interrupted) holds nothing to import.
    record['courses'] = [course for course in record['courses'] if course['modules']]
    # "CFPM IC10" -> "IC10": what the study's code in EMS ends with (CFGM_IC10).
    record['study_code'] = _study_token(
        study_tokens, [module for course in record['courses'] for module in course['modules']])
    return record
