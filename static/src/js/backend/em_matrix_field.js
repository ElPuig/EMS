/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Spreadsheet-like matrix for the work placement (EM) grades of a group: one row per student,
// then the single EM grade (the normal case: the same grade for every module of that student),
// the "Grade per module" checkbox and one column per module of the group carrying a placement
// weight, editable only when that checkbox is ticked.
//
// The widget edits the wizard's own transient lines (student_line_ids for the single grade,
// line_ids for the per-module detail): no buffer of its own, no RPC. The form's "Apply EM grade"
// button saves the record and lets the server write the grades, which keeps the whole decision
// logic (which line wins, EM < 5, live vs archived destination) in one place on the server.
export class EmMatrixField extends Component {
    static template = "ems.EmMatrixField";
    static props = { ...standardFieldProps };

    setup() {
        this.rootRef = useRef("root");
        // The cell the keyboard/paste operations start from (set on focus).
        this.anchor = null;
        // Paste is captured at the document level (a table of plain <input> cells does not
        // reliably receive the event otherwise), so we only act on it when the grid is the
        // active interaction target — same approach as the group/subject evaluation matrix.
        this._active = false;
        this._onDocMouseDown = (ev) => {
            this._active = !!(this.rootRef.el && this.rootRef.el.contains(ev.target));
        };
        this._onDocPaste = (ev) => this.onPaste(ev);
        onMounted(() => {
            document.addEventListener("mousedown", this._onDocMouseDown, true);
            document.addEventListener("paste", this._onDocPaste);
        });
        onWillUnmount(() => {
            document.removeEventListener("mousedown", this._onDocMouseDown, true);
            document.removeEventListener("paste", this._onDocPaste);
        });
    }

    // The column headers. They live here, not as literals in the template: Odoo only picks
    // up the translatable terms of a widget through _t() in the JS.
    get labels() {
        return {
            firstname: _t("First name"),
            lastname: _t("Last name"),
            score: _t("EM grade"),
            perModule: _t("Grade per module"),
        };
    }

    onCellFocus(ev) {
        this._active = true;
        this.anchor = {
            row: Number(ev.target.dataset.row),
            column: Number(ev.target.dataset.column),
        };
    }

    // The rows: one student line each.
    get rows() {
        return this.props.record.data[this.props.name].records;
    }

    // The module lines of every student, carried by the companion (hidden) o2m field.
    get moduleLines() {
        const field = this.props.record.data.line_ids;
        return field ? field.records : [];
    }

    // One column per module present in the group, ordered by code. The header carries the
    // module code (the columns stay narrow) with its truncated name underneath; a module of
    // a previous course (a pending final) also shows that course, so it is not mistaken for
    // a module of the course in progress.
    get columns() {
        const columns = new Map();
        for (const line of this.moduleLines) {
            const id = line.data.subject_id[0];
            if (!columns.has(id)) {
                const name = line.data.subject_name || "";
                columns.set(id, {
                    id,
                    code: line.data.subject_acronym || line.data.subject_id[1] || "",
                    name: name.length > 15 ? `${name.slice(0, 15)}…` : name,
                    title: name,
                    course: line.data.source === "history" ? line.data.course_name : "",
                });
            }
        }
        return [...columns.values()].sort((a, b) => a.code.localeCompare(b.code));
    }

    avatarUrl(row) {
        return `/web/image/res.partner/${row.data.student_id[0]}/image_128`;
    }

    moduleLine(row, column) {
        const studentId = row.data.student_id[0];
        return this.moduleLines.find(
            (line) => line.data.student_id[0] === studentId && line.data.subject_id[0] === column.id
        );
    }

    // A cell only shows a grade once there is one: an empty cell means "no placement grade
    // yet", never a 0 (which is a real grade).
    cellValue(record) {
        if (!record || !(record.data.already_scored || record.data.to_apply)) {
            return "";
        }
        return record.data.score;
    }

    studentValue(row) {
        return row.data.to_apply ? row.data.score : "";
    }

    // Empty input: undo the edit (the line goes back to "not graded here") instead of writing a 0.
    _parse(value) {
        const trimmed = (value || "").trim();
        if (trimmed === "") {
            return null;
        }
        const score = Number.parseInt(trimmed, 10);
        return Number.isNaN(score) ? null : Math.min(Math.max(score, 0), 10);
    }

    onStudentScore(row, ev) {
        const score = this._parse(ev.target.value);
        row.update(score === null ? { score: 0, to_apply: false } : { score, to_apply: true });
    }

    onPerModule(row, ev) {
        // Switching to per-module grading drops the single grade, so the two can never disagree.
        row.update({ per_module: ev.target.checked, score: 0, to_apply: false });
    }

    onModuleScore(row, column, ev) {
        const record = this.moduleLine(row, column);
        if (!record) {
            return;
        }
        const score = this._parse(ev.target.value);
        record.update(score === null ? { score: 0, to_apply: false } : { score, to_apply: true });
    }

    // ── Keyboard navigation ──────────────────────────────────────────────────
    // Same feel as the group/subject evaluation matrix: the arrows, Enter and Tab commit the
    // cell and move to the next one. Tab is left to the browser (it already skips the
    // disabled cells of the students graded with a single EM grade).
    onCellKeydown(ev) {
        const moves = {
            ArrowUp: [-1, 0],
            ArrowDown: [1, 0],
            Enter: [1, 0],
            ArrowLeft: [0, -1],
            ArrowRight: [0, 1],
        };
        const move = moves[ev.key];
        if (!move) {
            return;
        }
        ev.preventDefault();
        // Commit what was typed before leaving the cell (change only fires on blur).
        ev.target.dispatchEvent(new Event("change", { bubbles: true }));
        const [rowStep, columnStep] = move;
        let row = Number(ev.target.dataset.row);
        let column = Number(ev.target.dataset.column);
        // Walk on in the same direction over the cells that cannot be edited (a module the
        // student does not take, or the columns disabled by the per-module switch).
        for (let step = 0; step < 100; step++) {
            row += rowStep;
            column += columnStep;
            const next = this.rootRef.el.querySelector(
                `input[data-row="${row}"][data-column="${column}"]:not([disabled])`
            );
            if (next) {
                next.focus();
                next.select();
                return;
            }
            if (!this._inGrid(row, column)) {
                return;
            }
        }
    }

    _inGrid(row, column) {
        return row >= 0 && row < this.rows.length
            && column >= 0 && column <= this.columns.length;
    }

    // ── Paste ────────────────────────────────────────────────────────────────
    // A block of cells copied from a spreadsheet (rows separated by newlines, columns by
    // tabs) is written from the focused cell on: the usual case is one column of EM grades
    // pasted on the EM grade column, in the order the students are listed on screen.
    onPaste(ev) {
        if (!this._active || !this.anchor) {
            return;
        }
        const text = (ev.clipboardData || window.clipboardData).getData("text");
        if (!text) {
            return;
        }
        ev.preventDefault();
        const block = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n")
            .map((line) => line.split("\t"));
        block.forEach((cells, rowOffset) => {
            cells.forEach((cell, columnOffset) => {
                const row = this.rows[this.anchor.row + rowOffset];
                const column = this.anchor.column + columnOffset;
                if (!row || !this._inGrid(this.anchor.row + rowOffset, column)) {
                    return;
                }
                this._setCell(row, column, this._parse(cell));
            });
        });
    }

    // Write a value into a cell of the grid, honouring what that cell may hold: the single
    // EM grade only when the student is not graded per module, and the other way round.
    _setCell(row, column, score) {
        const values = score === null
            ? { score: 0, to_apply: false }
            : { score, to_apply: true };
        if (column === 0) {
            if (!row.data.per_module) {
                row.update(values);
            }
            return;
        }
        if (!row.data.per_module) {
            return;
        }
        const record = this.moduleLine(row, this.columns[column - 1]);
        if (record) {
            record.update(values);
        }
    }
}

export const emMatrixField = {
    component: EmMatrixField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("em_matrix", emMatrixField);
