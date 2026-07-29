# -*- coding: utf-8 -*-

import base64
import csv
import io
import logging
import re
from datetime import datetime

from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .grade_session import grade_round_selection

_logger = logging.getLogger(__name__)

# Columns of the "Notes Flat" sheet, in order.
_FLAT_HEADERS = ["idAlumne", "nom Alumne", "Codi Mòdul", "Nom Mòdul", "Codi", "Nom", "Tipus", "Subtipus", "Nota"]

# Header cells of the pivoted "Notes" sheet that are not grade columns.
_PIVOT_SKIP_HEADERS = {"idalumne", "nom", "n. convocatoria", "n. convocatòria", "provisional"}

# A grade column header in the pivoted "Notes" sheet: "<module>_<NN><RA|EM>".
_PIVOT_OUTCOME_RE = re.compile(r"^(?P<mod>.+)_(?P<sub>\d{2})(?P<kind>RA|EM)$")

# Aggregate "module" codes that Esfera exports for higher cycles (overall final grade and
# university-access grade). They are not real subjects, so they are skipped instead of reported
# as errors. Add any other export-only aggregate codes here.
_SKIP_MODULE_CODES = {"QFINAL", "QUNIVERSITAT"}


class EmsGradeImportWizard(models.TransientModel):
    _name = "ems.grade_import_wizard"
    _description = "Grade import wizard (Esfera xlsx)"

    round = fields.Selection(string="Evaluation", selection=grade_round_selection, required=True)
    file = fields.Binary(string="Esfera xlsx file", required=True)
    file_name = fields.Char()
    result_html = fields.Html(string="Import result", readonly=True)
    log_file = fields.Binary(string="Import log (CSV)", readonly=True)
    log_file_name = fields.Char()

    def action_import(self):
        self.ensure_one()
        try:
            import openpyxl
        except ImportError:
            raise UserError(_("openpyxl is required to import xlsx files."))

        raw = base64.b64decode(self.file)
        wb = openpyxl.load_workbook(filename=io.BytesIO(raw), read_only=True, data_only=True)

        rows = self._read_rows(wb)
        if not rows:
            raise UserError(_("The file has no gradeable rows. Expected a 'Notes Flat' or 'Notes' sheet."))

        stats = {
            "ra": 0, "em": 0, "mp": 0, "locked": 0,
            "warnings": [], "errors": [], "log": [],
        }

        context = self._build_context(rows, stats)
        self._apply_rows(rows, context, stats)

        self.log_file = self._build_log_csv(stats["log"])
        self.log_file_name = "import_grades_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result_html = self._build_result_html(stats)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # --- Reading: both sheets are normalised to (idalu, codi_modul, tipus, subtipus, nota) tuples ---

    def _read_rows(self, wb):
        if "Notes Flat" in wb.sheetnames:
            return self._read_flat(wb["Notes Flat"])
        if "Notes" in wb.sheetnames:
            return self._read_pivot(wb["Notes"])
        return []

    def _read_flat(self, ws):
        rows = []
        it = ws.iter_rows(values_only=True)
        header = next(it, None)  # first row is the header
        if not header:
            return rows
        # Map the expected flat headers to their column index (tolerant to ordering).
        idx = {str(cell or "").strip(): i for i, cell in enumerate(header)}
        c_idalu = idx.get("idAlumne")
        c_mod = idx.get("Codi Mòdul")
        c_tipus = idx.get("Tipus")
        c_sub = idx.get("Subtipus")
        c_nota = idx.get("Nota")
        if None in (c_idalu, c_mod, c_tipus, c_sub, c_nota):
            raise UserError(_("The 'Notes Flat' sheet is missing required columns (idAlumne, Codi Mòdul, Tipus, Subtipus, Nota)."))
        for row in it:
            if not row or row[c_idalu] in (None, ""):
                continue
            rows.append((
                self._clean_idalu(row[c_idalu]),
                str(row[c_mod] or "").strip(),
                str(row[c_tipus] or "").strip(),
                str(row[c_sub] or "").strip(),
                row[c_nota],
            ))
        return rows

    def _read_pivot(self, ws):
        # The header row is the one containing "idAlumne"; columns before it may be a merged title row.
        grid = list(ws.iter_rows(values_only=True))
        header_idx = None
        for i, row in enumerate(grid[:20]):
            if row and any(str(c or "").strip().lower() == "idalumne" for c in row):
                header_idx = i
                break
        if header_idx is None:
            return []
        header = grid[header_idx]
        # Classify each column: (kind, codi_modul, subtipus) or None to skip.
        col_spec = {}
        id_col = None
        for i, cell in enumerate(header):
            label = str(cell or "").strip()
            low = label.lower()
            if low == "idalumne":
                id_col = i
                continue
            if not label or low in _PIVOT_SKIP_HEADERS:
                continue
            match = _PIVOT_OUTCOME_RE.match(label)
            if match:
                col_spec[i] = (match.group("kind"), match.group("mod"), match.group("sub"))
            else:
                # A bare module code column is the module's final grade (MP).
                col_spec[i] = ("MP", label, "MP")
        if id_col is None:
            return []
        rows = []
        for row in grid[header_idx + 1:]:
            if not row or id_col >= len(row) or row[id_col] in (None, ""):
                continue
            idalu = self._clean_idalu(row[id_col])
            for i, (kind, mod, sub) in col_spec.items():
                if i >= len(row):
                    continue
                rows.append((idalu, mod, kind, sub, row[i]))
        return rows

    @api.model
    def _clean_idalu(self, value):
        # idAlumne comes as an integer in xlsx; res.partner.student_id is a Char.
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value).strip()

    # --- Preprocessing: resolve students, derive group(s), load sessions and build indexes ---

    def _build_context(self, rows, stats):
        idalus = {row[0] for row in rows if row[0]}
        partners = self.env["res.partner"].search([
            ("contact_type", "=", "student"),
            ("student_id", "in", list(idalus)),
        ])
        student_by_idalu = {p.student_id: p for p in partners}

        groups = partners.mapped("main_group_id")
        if len(groups) > 1:
            stats["warnings"].append(_("The file spans several groups: %s.") % ", ".join(groups.mapped("name")))

        sessions = self.env["ems.grade_session"].search([
            ("group_id", "in", groups.ids),
            ("round", "=", self.round),
        ])
        # Candidate subjects for module matching, and O(1) line indexes.
        subject_by_code = {}
        outcome_by_code = {}
        outcome_line = {}
        subject_line = {}
        # Optional modules ("MP OPTx") are named/coded differently in each centre, so their Esfera code
        # never matches the EMS code (e.g. Esfera "OPT2" vs EMS "OPT1" for the same cycle). They are
        # resolved by the optional subject the student is actually enrolled in (one per study).
        optional_by_student = {}
        for session in sessions:
            subject = session.subject_id
            subject_by_code.setdefault(subject.code, subject)
            is_optional = subject.code.upper().startswith("OPT")
            for outcome in subject.outcome_ids:
                outcome_by_code[outcome.code] = outcome
            for line in session.grade_outcome_line_ids:
                outcome_line[(line.student_id.id, line.outcome_id.id)] = line
            for line in session.grade_subject_line_ids:
                subject_line[(line.student_id.id, subject.id)] = line
                if is_optional:
                    optional_by_student[line.student_id.id] = subject
        return {
            "student_by_idalu": student_by_idalu,
            "subject_by_code": subject_by_code,
            "outcome_by_code": outcome_by_code,
            "outcome_line": outcome_line,
            "subject_line": subject_line,
            "optional_by_student": optional_by_student,
        }

    def _resolve_subject(self, codi_modul, student, ctx):
        # Optional modules: the Esfera and EMS codes differ by design, so map straight to the optional
        # subject the student is enrolled in, ignoring the code.
        if codi_modul.upper().startswith("OPT"):
            return ctx["optional_by_student"].get(student.id)
        by_code = ctx["subject_by_code"]
        if codi_modul in by_code:
            return by_code[codi_modul]
        # Strip the trailing cycle token (e.g. "0156_IC10" -> "0156").
        stripped = codi_modul.rsplit("_", 1)[0]
        return by_code.get(stripped)

    # --- Applying: two passes (RA/EM first so MP can read the recomputed final) ---

    def _apply_rows(self, rows, ctx, stats):
        mp_rows = []
        for idalu, codi_modul, tipus, subtipus, nota in rows:
            # Skip export-only aggregate columns (overall / university-access final grade): they are not
            # subjects, so they must not be reported as missing sessions.
            if codi_modul.upper() in _SKIP_MODULE_CODES:
                continue
            student = ctx["student_by_idalu"].get(idalu)
            if not student:
                self._log_error(stats, idalu, codi_modul, tipus, _("Student not found (idAlumne %s).") % idalu)
                continue
            subject = self._resolve_subject(codi_modul, student, ctx)
            if not subject:
                self._log_error(stats, idalu, codi_modul, tipus,
                    _("No evaluation session for module '%s' in this evaluation.") % codi_modul)
                continue

            if tipus == "RA":
                self._apply_ra(student, subject, subtipus, nota, ctx, stats)
            elif tipus == "EM":
                self._apply_em(student, subject, nota, ctx, stats)
            elif tipus == "MP":
                mp_rows.append((student, subject, nota))
            # Unknown Tipus values are ignored silently.

        for student, subject, nota in mp_rows:
            self._apply_mp(student, subject, nota, ctx, stats)

    def _apply_ra(self, student, subject, subtipus, nota, ctx, stats):
        code = "%s_%s%s" % (subject.code, subtipus, "RA")
        outcome = ctx["outcome_by_code"].get(code)
        if not outcome:
            self._log_error(stats, student.student_id, subject.code, "RA",
                _("Outcome '%s' not found for subject '%s'.") % (code, subject.code))
            return
        line = ctx["outcome_line"].get((student.id, outcome.id))
        if not line:
            self._log_error(stats, student.student_id, subject.code, "RA",
                _("No grade line for student in outcome '%s' (not enrolled or session not filled).") % code)
            return
        score, scored = self._coerce_score(nota)
        vals = {"is_scored": scored}
        if scored:
            vals["score"] = score
        if line.is_locked:
            # The official grade overwrites a locked outcome: release the lock on this line only, so the
            # imported grade is shown without the padlock. Earlier rounds are left intact (their history
            # is preserved); the lock recomputes from them again for any future round.
            stats["locked"] += 1
            vals["is_lock_released"] = True
        line.with_context(ems_grade_import_bypass_lock=True).write(vals)
        stats["ra"] += 1
        self._log(stats, "RA", student, subject, code, nota)

    def _apply_em(self, student, subject, nota, ctx, stats):
        line = ctx["subject_line"].get((student.id, subject.id))
        if not line:
            self._log_error(stats, student.student_id, subject.code, "EM",
                _("No subject grade line for student (not enrolled or session not filled)."))
            return
        score, scored = self._coerce_score(nota)
        vals = {"external_is_scored": scored}
        if scored:
            vals["external_score"] = score
        line.write(vals)
        stats["em"] += 1
        self._log(stats, "EM", student, subject, subject.code, nota)

    def _apply_mp(self, student, subject, nota, ctx, stats):
        score, scored = self._coerce_score(nota)
        if not scored:
            # Textual MP (PQ/NP/...) has no official final to store; the state emerges on its own.
            return
        line = ctx["subject_line"].get((student.id, subject.id))
        if not line:
            self._log_error(stats, student.student_id, subject.code, "MP",
                _("No subject grade line for student (not enrolled or session not filled)."))
            return
        external_ponderation = line.grade_session_id.planning_id.external_ponderation
        if not external_ponderation:
            # No work placement: final == internal, so the official MP is stored exactly as an override.
            line.write({"is_overridden": True, "internal_score": score})
            stats["mp"] += 1
            self._log(stats, "MP", student, subject, subject.code, nota)
        else:
            # With work placement, EMS recomputes the final from RA + EM; only warn if it diverges.
            line.invalidate_recordset(["final_score"])
            if line.final_score != score:
                stats["warnings"].append(
                    _("Module final mismatch for %s / %s: file says %s, EMS computes %s.")
                    % (student.display_name, subject.code, score, line.final_score))
            self._log(stats, "MP", student, subject, subject.code, nota)

    @api.model
    def _coerce_score(self, value):
        # Returns (score, is_scored). Non-numeric notes (PDT/NA/NP/PQ) are "not scored".
        if value is None or value == "":
            return 0, False
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            return 0, False
        return max(0, min(10, score)), True

    # --- Logging and result ---

    def _log(self, stats, tipus, student, subject, code, nota):
        stats["log"].append({
            "tipus": tipus, "accio": "OK", "idalu": student.student_id,
            "alumne": student.display_name, "modul": subject.code, "codi": code,
            "nota": "" if nota is None else str(nota),
        })

    def _log_error(self, stats, idalu, modul, tipus, message):
        stats["errors"].append(message)
        stats["log"].append({
            "tipus": tipus, "accio": "ERROR", "idalu": idalu or "",
            "alumne": "", "modul": modul or "", "codi": "", "nota": message,
        })

    def _build_log_csv(self, log_entries):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["tipus", "accio", "idAlumne", "alumne", "modul", "codi", "nota / missatge"])
        for entry in log_entries:
            writer.writerow([
                entry["tipus"], entry["accio"], entry["idalu"], entry["alumne"],
                entry["modul"], entry["codi"], entry["nota"],
            ])
        return base64.b64encode(output.getvalue().encode("utf-8-sig")).decode()

    def _build_result_html(self, stats):
        # Warnings/errors can embed raw content from the uploaded file (e.g. idAlumne cell
        # values in a "Student not found" error) — build_html_list() (ems.base) handles the
        # escaping safely.
        warnings_html = Markup("")
        if stats["warnings"]:
            warnings_html = Markup("<p><strong>{} ({}):</strong></p>{}").format(
                _("Warnings"), len(stats["warnings"]), self.env['ems.base'].build_html_list(stats["warnings"]))
        errors_html = Markup("")
        if stats["errors"]:
            errors_html = Markup("<p><strong>{} ({}):</strong></p>{}").format(
                _("Errors"), len(stats["errors"]), self.env['ems.base'].build_html_list(stats["errors"]))
        return Markup(
            "<p>✅ <strong>{}:</strong> {}</p>"
            "<p>🏢 <strong>{}:</strong> {}</p>"
            "<p>📊 <strong>{}:</strong> {}</p>"
            "<p>🔓 <strong>{}:</strong> {}</p>"
            "{}{}"
        ).format(
            _("Learning outcome grades applied"), stats["ra"],
            _("Work placement grades applied"), stats["em"],
            _("Module final grades overridden"), stats["mp"],
            _("Locked outcomes overwritten"), stats["locked"],
            warnings_html, errors_html,
        )
