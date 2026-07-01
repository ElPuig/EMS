/** @odoo-module **/

import { Component, useState, useRef, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Spreadsheet-like matrix widget for grade_outcome_line_ids: one row per student,
// one column per learning outcome (ponderation in the header). Cells show the score
// as plain text; a rectangular range can be selected freely (drag, shift-click,
// shift-arrows), cleared (Delete) or pasted onto (Ctrl+V). Editing happens in a
// single floating input at the anchor cell. Reuses the attendance-view avatar
// mechanism. Changes persist with the form's Save button.
export class GradeMatrixField extends Component {
    static template = "ems.GradeMatrixField";
    static props = { ...standardFieldProps };

    setup() {
        this.sort = useState({ field: "lastname", dir: "asc" });
        this.widths = useState({ first: 150, last: 150 });
        // Selection as index ranges into the current rows/columns; (r1,c1) is the anchor.
        this.sel = useState({ r1: null, c1: null, r2: null, c2: null });
        this.edit = useState({ active: false, value: "" });
        this.rootRef = useRef("root");
        this.editRef = useRef("editInput");
        this._dragging = false;
        onPatched(() => {
            if (this.edit.active && this.editRef.el && document.activeElement !== this.editRef.el) {
                this.editRef.el.focus();
                this.editRef.el.select();
            }
        });
    }

    get lines() {
        return this.props.record.data[this.props.name].records;
    }

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
        return [...columns.values()].sort((a, b) => a.label.localeCompare(b.label));
    }

    get rows() {
        const rows = new Map();
        for (const line of this.lines) {
            const studentId = line.data.student_id[0];
            if (!rows.has(studentId)) {
                rows.set(studentId, {
                    id: studentId,
                    firstname: line.data.student_firstname || "",
                    lastname: line.data.student_lastname || "",
                    cells: {},
                });
            }
            rows.get(studentId).cells[line.data.outcome_id[0]] = line;
        }
        const { field, dir } = this.sort;
        const other = field === "lastname" ? "firstname" : "lastname";
        const sign = dir === "asc" ? 1 : -1;
        const opts = { sensitivity: "base" };
        return [...rows.values()].sort((a, b) => {
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
        const width = this.widths[key];
        if (width) {
            return `width:${width}px`;
        }
        return key.startsWith("ra_") ? "width:70px" : "";
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

    cellValue(row, col) {
        const line = row.cells[col.id];
        return line && line.data.is_scored ? line.data.score : "";
    }

    cellClass(row, col, rowIndex, colIndex) {
        const line = row.cells[col.id];
        let cls = "";
        if (line && line.data.is_scored) {
            cls = line.data.score >= 5 ? "o_grade_cell_pass" : "o_grade_cell_fail";
        }
        if (this._inSelection(rowIndex, colIndex)) {
            cls += " o_grade_cell_selected";
        }
        if (rowIndex === this.sel.r1 && colIndex === this.sel.c1) {
            cls += " o_grade_cell_anchor";
        }
        return cls;
    }

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

    _lineAt(rowIndex, colIndex) {
        const rows = this.rows;
        const cols = this.columns;
        const row = rows[rowIndex];
        const col = cols[colIndex];
        return row && col ? row.cells[col.id] : null;
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

    // Single cell: normal update so the subject grades refresh live.
    _applyOne(line, raw) {
        const changes = this._changesFor(raw);
        if (changes) {
            line.update(changes);
        }
    }

    // Block (paste / clear): apply every cell in a single batch, without a per-cell
    // onchange round-trip and updating the parent (re-render) only once at the end.
    // The subject grades recompute on the server when saving.
    async _applyMany(entries) {
        const changes = [];
        for (const { line, raw } of entries) {
            const values = this._changesFor(raw);
            if (values) {
                changes.push({ line, values });
            }
        }
        if (!changes.length) {
            return;
        }
        const model = this.props.record.model;
        await model.mutex.exec(async () => {
            for (let i = 0; i < changes.length; i++) {
                const last = i === changes.length - 1;
                await changes[i].line._update(changes[i].values, {
                    withoutOnchange: true,
                    withoutParentUpdate: !last,
                });
            }
        });
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

    // ── Editing ──────────────────────────────────────────────────────────────

    _startEdit(initial) {
        if (this.props.readonly) {
            return;
        }
        const line = this._lineAt(this.sel.r1, this.sel.c1);
        if (initial === undefined) {
            initial = line && line.data.is_scored ? String(line.data.score) : "";
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
        const line = this._lineAt(this.sel.r1, this.sel.c1);
        this.edit.active = false;
        if (line) {
            this._applyOne(line, this.edit.value);
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
                const line = rows[r] && cols[c] ? rows[r].cells[cols[c].id] : null;
                if (line) {
                    entries.push({ line, raw: "" });
                }
            }
        }
        this._applyMany(entries);
    }

    // ── Block paste ──────────────────────────────────────────────────────────

    async onPaste(ev) {
        if (this.props.readonly || this.sel.r1 === null) {
            return;
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
                const line = targetRow.cells[targetCol.id];
                if (line) {
                    entries.push({ line, raw: values[j] });
                }
                lastRow = startRow + i;
                lastCol = startCol + j;
            }
        }
        await this._applyMany(entries);
        // Select the pasted block.
        this.sel.r1 = startRow;
        this.sel.c1 = startCol;
        this.sel.r2 = lastRow;
        this.sel.c2 = lastCol;
    }
}

export const gradeMatrixField = {
    component: GradeMatrixField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("grade_matrix", gradeMatrixField);
