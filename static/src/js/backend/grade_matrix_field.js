/** @odoo-module **/

import { Component, useState, useRef, onPatched, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useSetupAction } from "@web/search/action_hook";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

// Spreadsheet-like matrix widget for grade_outcome_line_ids: one row per student, one column per
// learning outcome, plus the external grade and the subject-level columns (internal / computed / final /
// notes). All editing happens in a LOCAL BUFFER: typing, block paste, delete, arrows, the override
// checkbox, the manual internal grade and the notes only touch the buffer, never the records. The
// subject grades stay as computed by the model; while there are pending edits they are shown greyed and
// the "Apply changes" button is enabled. Applying writes the whole buffer to the records and saves, so
// the model recomputes everything server-side (the single source of truth for the calculations).
export class GradeMatrixField extends Component {
    static template = "ems.GradeMatrixField";
    static props = { ...standardFieldProps };

    setup() {
        this.sort = useState({ field: "lastname", dir: "asc" });
        this.widths = useState({ first: 150, last: 150 });
        // Selection as index ranges into the current rows/columns; (r1,c1) is the anchor.
        this.sel = useState({ r1: null, c1: null, r2: null, c2: null });
        this.edit = useState({ active: false, value: "", selectAll: false });
        // Local edit buffer (see class comment) and whether it differs from the applied values.
        this.buffer = useState({ outcomes: {}, subjects: {} });
        this.dirty = useState({ value: false });
        // Whether an apply (write + save) is in progress, to show a processing overlay.
        this.applying = useState({ value: false });
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        // Warn before leaving (in-app navigation and browser unload) with unapplied buffer changes.
        useSetupAction({
            beforeLeave: () => this._beforeLeave(),
            beforeUnload: (ev) => this._beforeUnload(ev),
        });
        this.rootRef = useRef("root");
        this.editRef = useRef("editInput");
        this._dragging = false;
        // Whether the grid is the active interaction target. Paste is captured at the document level
        // (a non-editable <div> does not reliably receive paste events until an <input> has been used),
        // so we only act on paste when the grid is active.
        this._active = false;
        this._onDocMouseDown = (ev) => {
            this._active = !!(this.rootRef.el && this.rootRef.el.contains(ev.target));
        };
        this._onDocPaste = (ev) => this.onPaste(ev);
        this._syncBuffer();
        onMounted(() => {
            document.addEventListener("mousedown", this._onDocMouseDown, true);
            document.addEventListener("paste", this._onDocPaste);
        });
        onWillUnmount(() => {
            document.removeEventListener("mousedown", this._onDocMouseDown, true);
            document.removeEventListener("paste", this._onDocPaste);
        });
        onPatched(() => {
            if (this.edit.active && this.editRef.el && document.activeElement !== this.editRef.el) {
                this.editRef.el.focus();
                if (this.edit.selectAll) {
                    this.editRef.el.select();
                }
            }
        });
    }

    // ── Records / buffer ─────────────────────────────────────────────────────

    get lines() {
        return this.props.record.data[this.props.name].records;
    }

    get subjectLines() {
        const field = this.props.record.data.grade_subject_line_ids;
        return field ? field.records : [];
    }

    // Copy the current record values into the buffer and mark it clean. Called on setup and after each
    // apply (the records are reloaded with the freshly computed grades).
    _syncBuffer() {
        const outcomes = {};
        for (const line of this.lines) {
            outcomes[line.id] = { score: line.data.score, is_scored: line.data.is_scored, is_locked: line.data.is_locked };
        }
        const subjects = {};
        for (const line of this.subjectLines) {
            subjects[line.id] = {
                external_score: line.data.external_score,
                external_is_scored: line.data.external_is_scored,
                is_overridden: line.data.is_overridden,
                internal_score: line.data.internal_score,
                notes: line.data.notes || "",
            };
        }
        this.buffer.outcomes = outcomes;
        this.buffer.subjects = subjects;
        this.dirty.value = false;
    }

    _outcomeBuf(row, col) {
        const rec = row.cells[col.id];
        return rec ? this.buffer.outcomes[rec.id] : null;
    }

    _subjectBuf(row) {
        return row.subject ? this.buffer.subjects[row.subject.id] : null;
    }

    // {score, is_scored} for a grid cell, read from the buffer (the external column maps to the subject
    // line's external fields, every other column to its outcome line).
    _cellGet(row, col) {
        if (col.isExternal) {
            const b = this._subjectBuf(row);
            return { score: b ? b.external_score : 0, is_scored: b ? b.external_is_scored : false };
        }
        const b = this._outcomeBuf(row, col);
        return { score: b ? b.score : 0, is_scored: b ? b.is_scored : false };
    }

    // Whether a cell is locked (an outcome already passed in an earlier round). Locked cells show the
    // carried-over value but cannot be edited, cleared or pasted over. The external column is never locked.
    _cellLocked(row, col) {
        if (col.isExternal) {
            return false;
        }
        const b = this._outcomeBuf(row, col);
        return b ? !!b.is_locked : false;
    }

    _cellSet(row, col, score, is_scored) {
        if (this._cellLocked(row, col)) {
            return;  // a passed outcome from an earlier round is final
        }
        if (col.isExternal) {
            const b = this._subjectBuf(row);
            if (b) {
                b.external_score = score;
                b.external_is_scored = is_scored;
            }
        } else {
            const b = this._outcomeBuf(row, col);
            if (b) {
                b.score = score;
                b.is_scored = is_scored;
            }
        }
        this.dirty.value = true;
    }

    // ── Columns / rows ───────────────────────────────────────────────────────

    get columns() {
        const columns = new Map();
        for (const line of this.lines) {
            const outcomeId = line.data.outcome_id[0];
            if (!columns.has(outcomeId)) {
                columns.set(outcomeId, {
                    id: outcomeId,
                    label: line.data.outcome_acronym || line.data.outcome_id[1] || "",
                    ponderation: line.data.ponderation,
                });
            }
        }
        const cols = [...columns.values()].sort((a, b) => a.label.localeCompare(b.label));
        // The external grade behaves like an RA column (selectable, pasteable): it is the last column of
        // the grid but maps to the subject line's external_score / external_is_scored.
        const externalPond = this.subjectLines.length ? this.subjectLines[0].data.external_ponderation : 0;
        cols.push({ id: "external", label: "External", ponderation: externalPond, isExternal: true });
        return cols;
    }

    get rows() {
        const subjectByStudent = new Map();
        for (const line of this.subjectLines) {
            subjectByStudent.set(line.data.student_id[0], line);
        }
        const rows = new Map();
        for (const line of this.lines) {
            const studentId = line.data.student_id[0];
            if (!rows.has(studentId)) {
                rows.set(studentId, {
                    id: studentId,
                    firstname: line.data.student_firstname || "",
                    lastname: line.data.student_lastname || "",
                    cells: {},
                    subject: subjectByStudent.get(studentId) || null,
                });
            }
            rows.get(studentId).cells[line.data.outcome_id[0]] = line;
        }
        const result = [...rows.values()];
        const { field, dir } = this.sort;
        const other = field === "lastname" ? "firstname" : "lastname";
        const sign = dir === "asc" ? 1 : -1;
        const opts = { sensitivity: "base" };
        return result.sort((a, b) => {
            const primary = a[field].localeCompare(b[field], undefined, opts);
            if (primary !== 0) {
                return sign * primary;
            }
            return sign * a[other].localeCompare(b[other], undefined, opts);
        });
    }

    // ── Sorting ──────────────────────────────────────────────────────────────

    onSort(field) {
        if (this.sort.field === field) {
            this.sort.dir = this.sort.dir === "asc" ? "desc" : "asc";
        } else {
            this.sort.field = field;
            this.sort.dir = "asc";
        }
        this.sel.r1 = this.sel.c1 = this.sel.r2 = this.sel.c2 = null;  // order changed
    }

    sortIndicator(field) {
        if (this.sort.field !== field) {
            return "";
        }
        return this.sort.dir === "asc" ? " ▲" : " ▼";
    }

    // ── Column resizing ──────────────────────────────────────────────────────

    colStyle(key) {
        if (key === "notes") {
            return `width:${this.notesColWidth}px`;
        }
        const width = this.widths[key];
        if (width) {
            return `width:${width}px`;
        }
        if (key.startsWith("ra_")) {
            return "width:70px";
        }
        const fixed = { internal: 72, check: 108, final: 72 };
        return fixed[key] ? `width:${fixed[key]}px` : "";
    }

    get notesColWidth() {
        if (this.widths.notes) {
            return this.widths.notes;
        }
        let maxLen = 10;
        for (const row of this.rows) {
            maxLen = Math.max(maxLen, this.notesValue(row).length);
        }
        return Math.min(800, Math.max(160, maxLen * 8 + 20));
    }

    onResizeStart(key, ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const th = ev.target.closest("th");
        const startX = ev.clientX;
        const startWidth = this.widths[key] || (th ? th.offsetWidth : 100);
        const onMove = (moveEv) => {
            this.widths[key] = Math.max(40, startWidth + (moveEv.clientX - startX));
        };
        const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    }

    // ── Rendering helpers ────────────────────────────────────────────────────

    avatarUrl(studentId) {
        return `/web/image/res.partner/${studentId}/image_128`;
    }

    formatPonderation(ponderation) {
        return (Math.round(ponderation * 100) / 100).toString();
    }

    formatScore(value) {
        return (Math.round((value || 0) * 100) / 100).toString();
    }

    get internalHeader() {
        const pond = this.subjectLines.length ? this.subjectLines[0].data.internal_ponderation : 0;
        return pond ? `Internal-${this.formatPonderation(pond)}%` : "Internal";
    }

    // RA / external cells (from the buffer).
    cellValue(row, col) {
        const { score, is_scored } = this._cellGet(row, col);
        return is_scored ? score : "";
    }

    cellClass(row, col, rowIndex, colIndex) {
        const { score, is_scored } = this._cellGet(row, col);
        let cls = "";
        if (is_scored) {
            cls = score >= 5 ? "o_grade_cell_pass" : "o_grade_cell_fail";
        }
        if (this._cellLocked(row, col)) {
            cls += " o_grade_cell_locked";
        }
        if (col.isExternal) {
            cls += " o_grade_matrix_sep";
        }
        if (this._inSelection(rowIndex, colIndex)) {
            cls += " o_grade_cell_selected";
        }
        if (rowIndex === this.sel.r1 && colIndex === this.sel.c1) {
            cls += " o_grade_cell_anchor";
        }
        return cls;
    }

    // Subject columns. The internal grade is editable (from the buffer) when overridden, otherwise it is
    // the model's computed value; computed and final are always the model's values. The computed values
    // are shown greyed while there are pending edits (they refresh on apply).
    staleClass() {
        return this.dirty.value ? "o_grade_cell_stale" : "";
    }

    isOverridden(row) {
        const b = this._subjectBuf(row);
        return b ? b.is_overridden : false;
    }

    // A provisional grade: the internal grade is informed but not every outcome has been evaluated yet
    // (an overridden grade is never provisional). Shown in italics with a trailing "*".
    isProvisional(row) {
        return !!(row.subject && row.subject.data.internal_is_scored && !row.subject.data.internal_is_complete);
    }

    provisionalMark(row) {
        return this.isProvisional(row) ? "*" : "";
    }

    provisionalTitle(row) {
        return this.isProvisional(row) ? _t("Provisional grade: some outcomes are still pending.") : "";
    }

    internalEditable(row) {
        return !this.props.readonly && this.isOverridden(row);
    }

    internalScore(row) {
        const b = this._subjectBuf(row);
        if (b && b.is_overridden) {
            return this.formatScore(b.internal_score);
        }
        return row.subject && row.subject.data.internal_is_scored
            ? this.formatScore(row.subject.data.internal_score) + this.provisionalMark(row)
            : "";
    }

    internalCellClass(row) {
        if (this.isOverridden(row)) {
            return "o_grade_matrix_overridden";
        }
        let cls = this.staleClass();
        if (this.isProvisional(row)) {
            cls += " o_grade_matrix_provisional";
        }
        return cls;
    }

    computedScore(row) {
        return row.subject && row.subject.data.computed_is_scored
            ? this.formatScore(row.subject.data.computed_score)
            : "";
    }

    hasFinal(row) {
        return row.subject ? row.subject.data.has_final : false;
    }

    finalScore(row) {
        return this.hasFinal(row) ? this.formatScore(row.subject.data.final_score) + this.provisionalMark(row) : "";
    }

    finalCellClass(row) {
        let cls = "o_grade_matrix_final";
        if (this.hasFinal(row)) {
            cls += row.subject.data.final_score >= 5 ? " o_grade_cell_pass" : " o_grade_cell_fail";
        }
        if (this.isProvisional(row)) {
            cls += " o_grade_matrix_provisional";
        }
        if (this.dirty.value) {
            cls += " o_grade_cell_stale";
        }
        return cls;
    }

    notesValue(row) {
        const b = this._subjectBuf(row);
        return b ? b.notes || "" : "";
    }

    // ── Subject-cell handlers (buffer only) ──────────────────────────────────

    _parseScore(raw) {
        const value = (raw || "").trim().replace(",", ".");
        if (value === "") {
            return 0;
        }
        const parsed = parseFloat(value);
        if (Number.isNaN(parsed)) {
            return null;
        }
        return Math.max(0, Math.min(10, Math.round(parsed)));
    }

    onToggleOverride(row, ev) {
        const b = this._subjectBuf(row);
        if (b) {
            b.is_overridden = ev.target.checked;
            this.dirty.value = true;
        }
    }

    onInternalChange(row, ev) {
        const b = this._subjectBuf(row);
        if (!b) {
            return;
        }
        const value = this._parseScore(ev.target.value);
        if (value !== null) {
            b.internal_score = value;
            this.dirty.value = true;
        }
    }

    onNotesChange(row, ev) {
        const b = this._subjectBuf(row);
        if (b) {
            b.notes = ev.target.value;
            this.dirty.value = true;
        }
    }

    // Enter and the up/down arrows commit and move to the adjacent row's input; Tab and left/right keep
    // their native behaviour.
    onSubjectInputKeydown(ev, row, field) {
        ev.stopPropagation();
        let direction = 0;
        if (ev.key === "Enter" || ev.key === "ArrowDown") {
            direction = 1;
        } else if (ev.key === "ArrowUp") {
            direction = -1;
        } else {
            return;
        }
        ev.preventDefault();
        const input = ev.target;
        if (field === "internal") {
            this.onInternalChange(row, { target: input });
        } else if (field === "notes") {
            this.onNotesChange(row, { target: input });
        }
        const td = input.closest("td");
        const tr = td && td.closest("tr");
        if (!tr) {
            return;
        }
        const colIndex = [...tr.children].indexOf(td);
        let sibling = direction === 1 ? tr.nextElementSibling : tr.previousElementSibling;
        while (sibling) {
            const nextInput = sibling.children[colIndex] && sibling.children[colIndex].querySelector("input");
            if (nextInput) {
                nextInput.focus();
                if (nextInput.select) {
                    nextInput.select();
                }
                return;
            }
            sibling = direction === 1 ? sibling.nextElementSibling : sibling.previousElementSibling;
        }
    }

    // ── Selection / grid state ───────────────────────────────────────────────

    isEditingAt(rowIndex, colIndex) {
        return this.edit.active && rowIndex === this.sel.r1 && colIndex === this.sel.c1;
    }

    _inSelection(rowIndex, colIndex) {
        if (this.sel.r1 === null) {
            return false;
        }
        const rMin = Math.min(this.sel.r1, this.sel.r2);
        const rMax = Math.max(this.sel.r1, this.sel.r2);
        const cMin = Math.min(this.sel.c1, this.sel.c2);
        const cMax = Math.max(this.sel.c1, this.sel.c2);
        return rowIndex >= rMin && rowIndex <= rMax && colIndex >= cMin && colIndex <= cMax;
    }

    _changesFor(raw) {
        const value = (raw || "").trim().replace(",", ".");
        if (value === "") {
            return { score: 0, is_scored: false };
        }
        let parsed = Math.round(parseFloat(value));
        if (Number.isNaN(parsed)) {
            return null;
        }
        parsed = Math.max(0, Math.min(10, parsed));
        return { score: parsed, is_scored: true };
    }

    _applyOne(row, col, raw) {
        const changes = this._changesFor(raw);
        if (changes) {
            this._cellSet(row, col, changes.score, changes.is_scored);
        }
    }

    _applyMany(entries) {
        for (const { row, col, raw } of entries) {
            const changes = this._changesFor(raw);
            if (changes) {
                this._cellSet(row, col, changes.score, changes.is_scored);
            }
        }
    }

    // ── Mouse selection ──────────────────────────────────────────────────────

    onCellMouseDown(rowIndex, colIndex, ev) {
        ev.preventDefault();  // avoid native text selection while dragging
        this.edit.active = false;
        if (ev.shiftKey && this.sel.r1 !== null) {
            this.sel.r2 = rowIndex;
            this.sel.c2 = colIndex;
        } else {
            this.sel.r1 = this.sel.r2 = rowIndex;
            this.sel.c1 = this.sel.c2 = colIndex;
        }
        this._dragging = true;
        const onUp = () => {
            this._dragging = false;
            // Focus on mouseup too: a focus() during a mousedown that ran preventDefault() is not
            // reliably applied in some browsers, which would break paste until a cell had been edited.
            if (this.rootRef.el) {
                this.rootRef.el.focus();
            }
            document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mouseup", onUp);
        if (this.rootRef.el) {
            this.rootRef.el.focus();
        }
    }

    onCellMouseEnter(rowIndex, colIndex) {
        if (this._dragging) {
            this.sel.r2 = rowIndex;
            this.sel.c2 = colIndex;
        }
    }

    onCellDblClick(rowIndex, colIndex) {
        this.sel.r1 = this.sel.r2 = rowIndex;
        this.sel.c1 = this.sel.c2 = colIndex;
        this._startEdit();
    }

    // ── Editing (floating input over the anchor cell) ────────────────────────

    _startEdit(initial) {
        if (this.props.readonly) {
            return;
        }
        const row = this.rows[this.sel.r1];
        const col = this.columns[this.sel.c1];
        if (row && col && this._cellLocked(row, col)) {
            return;  // a passed outcome from an earlier round cannot be edited
        }
        this.edit.selectAll = initial === undefined;
        if (initial === undefined) {
            const { score, is_scored } = row && col ? this._cellGet(row, col) : {};
            initial = is_scored ? String(score) : "";
        }
        this.edit.value = initial;
        this.edit.active = true;
    }

    onEditInput(ev) {
        this.edit.value = ev.target.value;
    }

    commitEdit() {
        if (!this.edit.active) {
            return;
        }
        const row = this.rows[this.sel.r1];
        const col = this.columns[this.sel.c1];
        this.edit.active = false;
        if (row && col) {
            this._applyOne(row, col, this.edit.value);
        }
    }

    onEditKeydown(ev) {
        ev.stopPropagation();
        if (ev.key === "Enter" || ev.key === "Tab") {
            ev.preventDefault();
            this.commitEdit();
            this._moveTo(this.sel.r1 + (ev.key === "Enter" ? 1 : 0), this.sel.c1 + (ev.key === "Tab" ? 1 : 0), false);
            if (this.rootRef.el) {
                this.rootRef.el.focus();
            }
        } else if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") {
            const input = ev.target;
            const goingRight = ev.key === "ArrowRight";
            const atEnd = input.selectionStart === input.value.length && input.selectionEnd === input.value.length;
            const atStart = input.selectionStart === 0 && input.selectionEnd === 0;
            if ((goingRight && atEnd) || (!goingRight && atStart)) {
                ev.preventDefault();
                this.commitEdit();
                this._moveTo(this.sel.r1, this.sel.c1 + (goingRight ? 1 : -1), false);
                if (this.rootRef.el) {
                    this.rootRef.el.focus();
                }
            }
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.edit.active = false;
            if (this.rootRef.el) {
                this.rootRef.el.focus();
            }
        }
    }

    // ── Keyboard on the grid ─────────────────────────────────────────────────

    _moveTo(rowIndex, colIndex, extend) {
        const rows = this.rows;
        const cols = this.columns;
        const r = Math.max(0, Math.min(rows.length - 1, rowIndex));
        const c = Math.max(0, Math.min(cols.length - 1, colIndex));
        this.sel.r2 = r;
        this.sel.c2 = c;
        if (!extend) {
            this.sel.r1 = r;
            this.sel.c1 = c;
        }
    }

    onRootKeydown(ev) {
        if (this.edit.active || this.props.readonly || this.sel.r1 === null) {
            return;
        }
        const extend = ev.shiftKey;
        const baseR = extend ? this.sel.r2 : this.sel.r1;
        const baseC = extend ? this.sel.c2 : this.sel.c1;
        switch (ev.key) {
            case "ArrowDown": ev.preventDefault(); this._moveTo(baseR + 1, baseC, extend); return;
            case "ArrowUp": ev.preventDefault(); this._moveTo(baseR - 1, baseC, extend); return;
            case "ArrowLeft": ev.preventDefault(); this._moveTo(baseR, baseC - 1, extend); return;
            case "ArrowRight": ev.preventDefault(); this._moveTo(baseR, baseC + 1, extend); return;
            case "Enter": ev.preventDefault(); this._startEdit(); return;
            case "Backspace":
            case "Delete": ev.preventDefault(); this._clearSelection(); return;
            default:
                if (/^[0-9]$/.test(ev.key)) {
                    ev.preventDefault();
                    this._moveTo(this.sel.r1, this.sel.c1, false);  // collapse to anchor
                    this._startEdit(ev.key);
                }
        }
    }

    _clearSelection() {
        const rows = this.rows;
        const cols = this.columns;
        const rMin = Math.min(this.sel.r1, this.sel.r2);
        const rMax = Math.max(this.sel.r1, this.sel.r2);
        const cMin = Math.min(this.sel.c1, this.sel.c2);
        const cMax = Math.max(this.sel.c1, this.sel.c2);
        const entries = [];
        for (let r = rMin; r <= rMax; r++) {
            for (let c = cMin; c <= cMax; c++) {
                if (rows[r] && cols[c]) {
                    entries.push({ row: rows[r], col: cols[c], raw: "" });
                }
            }
        }
        this._applyMany(entries);
    }

    // ── Block paste ──────────────────────────────────────────────────────────

    onPaste(ev) {
        if (this.props.readonly || this.sel.r1 === null || !this._active || this.edit.active) {
            return;
        }
        const active = document.activeElement;
        if (
            active &&
            (active.tagName === "INPUT" || active.tagName === "TEXTAREA") &&
            this.rootRef.el &&
            this.rootRef.el.contains(active)
        ) {
            return;  // a subject input is focused; let it paste normally
        }
        const text = ev.clipboardData && ev.clipboardData.getData("text");
        if (!text) {
            return;
        }
        ev.preventDefault();
        this.edit.active = false;

        const rows = this.rows;
        const cols = this.columns;
        const startRow = Math.min(this.sel.r1, this.sel.r2);
        const startCol = Math.min(this.sel.c1, this.sel.c2);

        const pasted = text.replace(/\r/g, "").split("\n");
        while (pasted.length && pasted[pasted.length - 1] === "") {
            pasted.pop();
        }

        let lastRow = startRow;
        let lastCol = startCol;
        const entries = [];
        for (let i = 0; i < pasted.length; i++) {
            const targetRow = rows[startRow + i];
            if (!targetRow) {
                break;
            }
            const values = pasted[i].split("\t");
            for (let j = 0; j < values.length; j++) {
                const targetCol = cols[startCol + j];
                if (!targetCol) {
                    break;
                }
                entries.push({ row: targetRow, col: targetCol, raw: values[j] });
                lastRow = startRow + i;
                lastCol = startCol + j;
            }
        }
        this._applyMany(entries);
        this.sel.r1 = startRow;
        this.sel.c1 = startCol;
        this.sel.r2 = lastRow;
        this.sel.c2 = lastCol;
    }

    // ── Leaving with unapplied changes ───────────────────────────────────────

    // Returning false blocks the in-app navigation (see clearUncommittedChanges).
    _beforeLeave() {
        if (!this.dirty.value) {
            return;
        }
        return new Promise((resolve) => {
            this.dialog.add(
                ConfirmationDialog,
                {
                    title: _t("Unapplied grade changes"),
                    body: _t(
                        "You have grade changes that have not been applied. If you leave now they will be lost."
                    ),
                    confirmLabel: _t("Leave and discard"),
                    confirm: () => resolve(true),
                    cancelLabel: _t("Stay"),
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            );
        });
    }

    _beforeUnload(ev) {
        if (this.dirty.value) {
            ev.preventDefault();
            ev.returnValue = "Unapplied changes";
        }
    }

    // ── Apply (buffer -> records -> save -> recompute) ───────────────────────

    async applyChanges() {
        if (!this.dirty.value || this.props.readonly || this.applying.value) {
            return;
        }
        this.applying.value = true;
        try {
            await this._applyChanges();
        } finally {
            this.applying.value = false;
        }
    }

    async _applyChanges() {
        // Push the whole buffer to the server in a SINGLE request, then reload the record once. Writing
        // the lines one by one through the record (line._update) re-rendered the matrix after every cell
        // (each awaited update flushed a render), which looked like the grades appearing cell by cell and
        // was slow for big pastes. The header fields are read-only on a saved session, so the form record
        // is never dirty here and going straight to the ORM is safe.
        const outcomeVals = {};
        for (const line of this.lines) {
            const b = this.buffer.outcomes[line.id];
            if (b && (b.score !== line.data.score || b.is_scored !== line.data.is_scored)) {
                outcomeVals[line.resId] = { score: b.score, is_scored: b.is_scored };
            }
        }
        const subjectVals = {};
        for (const line of this.subjectLines) {
            const b = this.buffer.subjects[line.id];
            if (!b) {
                continue;
            }
            const changes = {};
            if (b.external_score !== line.data.external_score) {
                changes.external_score = b.external_score;
            }
            if (b.external_is_scored !== line.data.external_is_scored) {
                changes.external_is_scored = b.external_is_scored;
            }
            if (b.is_overridden !== line.data.is_overridden) {
                changes.is_overridden = b.is_overridden;
            }
            if ((b.notes || "") !== (line.data.notes || "")) {
                changes.notes = b.notes;
            }
            // The manual internal grade is only meaningful (and written) while overridden.
            if (b.is_overridden && b.internal_score !== line.data.internal_score) {
                changes.internal_score = b.internal_score;
            }
            if (Object.keys(changes).length) {
                subjectVals[line.resId] = changes;
            }
        }
        if (Object.keys(outcomeVals).length || Object.keys(subjectVals).length) {
            await this.orm.call("ems.grade_session", "apply_grade_changes", [outcomeVals, subjectVals]);
            await this.props.record.load();
        }
        this._syncBuffer();
    }
}

export const gradeMatrixField = {
    component: GradeMatrixField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("grade_matrix", gradeMatrixField);
