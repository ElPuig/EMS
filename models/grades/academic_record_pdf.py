# -*- coding: utf-8 -*-

import re
import subprocess

# Reader of the "Expedient acadèmic" PDF that the Departament d'Educació's Esfera issues for a VET
# student (issue #585): the certificate a student brings when transferring from another centre.
# Odoo's own PyPDF2 glues the table's columns together ("10156_IC10_01RA": level 1 and the code),
# so the text is taken with poppler's pdftotext in layout mode (apt-requirements.txt), which keeps
# one table row per line with its columns apart.
#
# Only the data the academic history needs is read: the student's identifier (IDALU), the study,
# and, per course the certificate evaluates, the evaluating centre and the grade of every module
# (MP), learning outcome (RA) and work placement (EM). Everything is returned as plain data; the
# wizard maps it to EMS records and the user validates it before anything is written.

# A table row: the level, then the code. Continuation lines (a wrapped name, type or grade) do
# not start like this and are folded into the row above.
_ROW_RE = re.compile(r"^\s*(?P<level>\d)\s+(?P<code>[A-Z0-9][A-Z0-9_]*)\s{2,}(?P<rest>.*)$")
# The code of a learning outcome or of a work placement: "<module>_<NN>RA" / "<module>_<NN>EM".
_OUTCOME_CODE_RE = re.compile(r"^(?P<module>.+)_(?P<number>\d{2})(?P<kind>RA|EM)$")
# The qualification column, read from the type column onwards (the name may hold anything).
_TYPE_RE = re.compile(r"\s(?:MP|RA|EM)\S*\s+(?P<after>.*)$")
_QUALIFICATION_RE = re.compile(
    r"(?P<text>Assolit-\d+|No assolit|Pendent de qualificar|Pendent de|Pendent|No presentat"
    r"|Convalidat|Exempt|No apte|Apte|\d{1,2}(?:[.,]\d+)?)(?:\s|$)")
_COURSE_RE = re.compile(r"^\s*(?P<start>\d{4})/(?P<end>\d{4})\s+(?P<level>\d)\s{2,}(?P<study>.+?)\s*$")


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
        'study_label': ' '.join(study_tokens),
        # "CFPM IC10" -> "IC10": what the study's code in EMS ends with (CFGM_IC10).
        'study_code': study_tokens[-1] if study_tokens else '',
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
            centre_line = next((value for value in lines[index + 2:index + 4] if value.strip()), '')
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
        type_match = _TYPE_RE.search(' ' + match.group('rest'))
        qualification = _QUALIFICATION_RE.match(type_match.group('after')) if type_match else None
        text_value = qualification.group('text') if qualification else ''
        outcome_match = _OUTCOME_CODE_RE.match(code)
        if outcome_match and course['modules'] \
                and course['modules'][-1]['code'] == outcome_match.group('module'):
            score, is_scored = _grade(text_value)
            last_row = {'code': code, 'kind': outcome_match.group('kind').lower(),
                        'number': outcome_match.group('number'), 'text': text_value,
                        'score': score, 'is_scored': is_scored}
            course['modules'][-1]['outcomes'].append(last_row)
        else:
            name = re.split(r"\s{2,}", match.group('rest').strip(), maxsplit=1)[0]
            last_row = {'code': code, 'name': name, 'text': text_value, 'outcomes': []}
            course['modules'].append(last_row)
    for module in (module for course in record['courses'] for module in course['modules']):
        module['grade'], module['has_grade'] = _grade(module['text'])
    # A course block with no module (e.g. the course a transfer interrupted) holds nothing to import.
    record['courses'] = [course for course in record['courses'] if course['modules']]
    return record
