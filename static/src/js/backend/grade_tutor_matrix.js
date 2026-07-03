/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

const ROUND_LABELS = { "1": "1a", "2": "2a", "3": "3a", "4": "4a" };

// Client action for the tutor's evaluation view: it aggregates the non-closed grade sessions of the
// tutored group (a single open/board round) and shows, one STUDENT at a time, a grid with one row per
// enrolled subject and the learning-outcome scores laid out positionally (RA 1..N, N = the largest RA
// count among the student's subjects; cells a subject does not have are disabled), plus the same subject
// columns as the per-subject view (External / Override Internal / Internal / Final / Notes). Editing goes
// to a LOCAL BUFFER; "Apply changes" writes it to the records via the ORM and the model recomputes
// everything (the single source of truth). Single-cell editing only (no block paste): navigate with the
// arrows / Enter / Tab, edit in place, clear with Delete.
export class GradeTutorMatrix extends Component {
    static template = "ems.GradeTutorMatrix";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.state = useState({ loading: true, empty: false, studentIdx: 0, groupId: null });
        this.data = useState({ groupName: "", round: null, students: [], groups: [] });
        // Buffers keyed by record id (persist across students until applied).
        this.buffer = useState({ outcomes: {}, subjects: {} });
        this.dirty = useState({ value: false });
        this.applying = useState({ value: false });
        // Single selected cell (anchor) as indices into the current student's rows/columns.
        this.sel = useState({ r: null, c: null });
        this.edit = useState({ active: false, value: "", selectAll: false });
        this.widths = useState({ subject: 200 });

        this.rootRef = useRef("root");
        this.editRef = useRef("editInput");
        // Snapshots of the applied values, to diff on apply.
        this._outRaw = {};
        this._subRaw = {};

        useSetupAction({
            beforeLeave: () => this._beforeLeave(),
            beforeUnload: (ev) => this._beforeUnload(ev),
        });
        onWillStart(async () => this._load());
        onPatched(() => {
            if (this.edit.active && this.editRef.el && document.activeElement !== this.editRef.el) {
                this.editRef.el.focus();
                if (this.edit.selectAll) {
                    this.editRef.el.select();
                }
            }
        });
    }

    // ── Data loading ─────────────────────────────────────────────────────────

    async _load() {
        this.state.loading = true;
        const sessions = await this.orm.searchRead(
            "ems.grade_session",
            [["group_id.tutor_id.user_id", "=", user.userId], ["state", "!=", "final"]],
            ["group_id", "subject_id", "round", "state"]
        );
        if (!sessions.length) {
            this.data.students = [];
            this.data.groups = [];
            this.state.empty = true;
            this.state.loading = false;
            return;
        }
        // Distinct tutored groups that have an open (non-final) evaluation.
        const groupsMap = new Map();
        for (const s of sessions) {
            if (!groupsMap.has(s.group_id[0])) {
                groupsMap.set(s.group_id[0], s.group_id[1] || "");
            }
        }
        this.data.groups = [...groupsMap.entries()]
            .map(([id, name]) => ({ id, name }))
            .sort((a, b) => a.name.localeCompare(b.name));
        // Keep the current group selection if still valid, otherwise take the first.
        if (!this.data.groups.some((g) => g.id === this.state.groupId)) {
            this.state.groupId = this.data.groups[0].id;
        }
        const groupSessions = sessions.filter((s) => s.group_id[0] === this.state.groupId);
        const sessionIds = groupSessions.map((s) => s.id);
        this.data.groupName = groupSessions[0].group_id[1] || "";
        this.data.round = groupSessions[0].round;

        const subjectLines = await this.orm.searchRead(
            "ems.grade_subject_line",
            [["grade_session_id", "in", sessionIds]],
            [
                "subject_id", "subject_name", "student_id", "student_firstname", "student_lastname",
                "internal_ponderation", "external_ponderation", "internal_score", "internal_is_scored",
                "external_score", "external_is_scored", "computed_score", "computed_is_scored",
                "is_overridden", "final_score", "has_final", "notes",
            ]
        );
        const outcomeLines = await this.orm.searchRead(
            "ems.grade_outcome_line",
            [["grade_session_id", "in", sessionIds]],
            ["subject_id", "student_id", "outcome_id", "outcome_acronym", "ponderation", "score", "is_scored"]
        );

        // Outcome lines grouped by (student, subject).
        const outcomesByKey = {};
        for (const ol of outcomeLines) {
            const key = ol.student_id[0] + "|" + ol.subject_id[0];
            (outcomesByKey[key] || (outcomesByKey[key] = [])).push(ol);
        }

        const studentsMap = new Map();
        const outBuf = {}, subBuf = {}, outRaw = {}, subRaw = {};
        for (const ol of outcomeLines) {
            outBuf[ol.id] = { score: ol.score, is_scored: ol.is_scored };
            outRaw[ol.id] = { score: ol.score, is_scored: ol.is_scored };
        }
        for (const sl of subjectLines) {
            const v = {
                external_score: sl.external_score,
                external_is_scored: sl.external_is_scored,
                is_overridden: sl.is_overridden,
                internal_score: sl.internal_score,
                notes: sl.notes || "",
            };
            subBuf[sl.id] = { ...v };
            subRaw[sl.id] = { ...v };

            const sid = sl.student_id[0];
            if (!studentsMap.has(sid)) {
                studentsMap.set(sid, {
                    id: sid,
                    firstname: sl.student_firstname || "",
                    lastname: sl.student_lastname || "",
                    subjectRows: [],
                });
            }
            const key = sid + "|" + sl.subject_id[0];
            const outcomes = (outcomesByKey[key] || []).slice().sort(
                (a, b) => (a.outcome_acronym || "").localeCompare(b.outcome_acronym || "")
            );
            studentsMap.get(sid).subjectRows.push({
                subjectLineId: sl.id,
                subjectId: sl.subject_id[0],
                subjectName: sl.subject_name || (sl.subject_id[1] || ""),
                internal_ponderation: sl.internal_ponderation,
                external_ponderation: sl.external_ponderation,
                outcomes,
                // Model-computed values (shown greyed while there are pending edits).
                model: {
                    internal_score: sl.internal_score,
                    internal_is_scored: sl.internal_is_scored,
                    computed_score: sl.computed_score,
                    computed_is_scored: sl.computed_is_scored,
                    final_score: sl.final_score,
                    has_final: sl.has_final,
                },
            });
        }

        const students = [...studentsMap.values()];
        const opts = { sensitivity: "base" };
        for (const st of students) {
            st.subjectRows.sort((a, b) => a.subjectName.localeCompare(b.subjectName, undefined, opts));
            st.maxRA = st.subjectRows.reduce((m, r) => Math.max(m, r.outcomes.length), 0);
        }
        students.sort(
            (a, b) =>
                a.lastname.localeCompare(b.lastname, undefined, opts) ||
                a.firstname.localeCompare(b.firstname, undefined, opts)
        );

        this.data.students = students;
        this.buffer.outcomes = outBuf;
        this.buffer.subjects = subBuf;
        this._outRaw = outRaw;
        this._subRaw = subRaw;
        this.dirty.value = false;
        if (this.state.studentIdx >= students.length) {
            this.state.studentIdx = 0;
        }
        this._resetSel();
        this.state.empty = false;
        this.state.loading = false;
    }

    // ── Student pagination ───────────────────────────────────────────────────

    get currentStudent() {
        return this.data.students[this.state.studentIdx] || null;
    }

    get studentCount() {
        return this.data.students.length;
    }

    prevStudent() {
        if (this.state.studentIdx > 0) {
            this.state.studentIdx--;
            this._resetSel();
        }
    }

    nextStudent() {
        if (this.state.studentIdx < this.studentCount - 1) {
            this.state.studentIdx++;
            this._resetSel();
        }
    }

    onStudentSelect(ev) {
        const idx = Number(ev.target.value);
        if (!Number.isNaN(idx)) {
            this.state.studentIdx = idx;
            this._resetSel();
        }
    }

    studentLabel(student) {
        return `${student.lastname}, ${student.firstname}`;
    }

    roundLabel() {
        return ROUND_LABELS[this.data.round] || "";
    }

    avatarUrl(studentId) {
        return `/web/image/res.partner/${studentId}/image_128`;
    }

    _resetSel() {
        this.sel.r = this.sel.c = null;
        this.edit.active = false;
    }

    // Switching group reloads a different set of sessions, so unapplied buffer changes would be lost:
    // ask for confirmation first (same dialog as leaving the view).
    async onGroupChange(ev) {
        const groupId = Number(ev.target.value);
        if (groupId === this.state.groupId) {
            return;
        }
        if (this.dirty.value && !(await this._confirmDiscard())) {
            ev.target.value = String(this.state.groupId);
            return;
        }
        this.state.groupId = groupId;
        this.state.studentIdx = 0;
        await this._load();
    }

    // ── Rows / columns of the current student ────────────────────────────────

    get rows() {
        return this.currentStudent ? this.currentStudent.subjectRows : [];
    }

    get columns() {
        const st = this.currentStudent;
        if (!st) {
            return [];
        }
        const cols = [];
        for (let j = 0; j < st.maxRA; j++) {
            cols.push({ kind: "ra", pos: j, id: "ra" + j, label: "RA " + (j + 1) });
        }
        cols.push({ kind: "external", id: "external", label: "External" });
        return cols;
    }

    // ── Buffer access ────────────────────────────────────────────────────────

    _cellGet(row, col) {
        if (col.kind === "external") {
            const b = this.buffer.subjects[row.subjectLineId];
            return { score: b ? b.external_score : 0, is_scored: b ? b.external_is_scored : false, disabled: false };
        }
        const ol = row.outcomes[col.pos];
        if (!ol) {
            return { disabled: true };
        }
        const b = this.buffer.outcomes[ol.id];
        return { score: b ? b.score : 0, is_scored: b ? b.is_scored : false, disabled: false, outcome: ol };
    }

    _cellSet(row, col, score, is_scored) {
        if (col.kind === "external") {
            const b = this.buffer.subjects[row.subjectLineId];
            if (b) {
                b.external_score = score;
                b.external_is_scored = is_scored;
                this.dirty.value = true;
            }
            return;
        }
        const ol = row.outcomes[col.pos];
        if (!ol) {
            return;  // disabled cell
        }
        const b = this.buffer.outcomes[ol.id];
        if (b) {
            b.score = score;
            b.is_scored = is_scored;
            this.dirty.value = true;
        }
    }

    // ── Rendering helpers ────────────────────────────────────────────────────

    formatPonderation(ponderation) {
        return (Math.round((ponderation || 0) * 100) / 100).toString();
    }

    formatScore(value) {
        return (Math.round((value || 0) * 100) / 100).toString();
    }

    subjectColStyle() {
        return `width:${this.widths.subject}px`;
    }

    onResizeStart(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const startX = ev.clientX;
        const startWidth = this.widths.subject;
        const onMove = (moveEv) => {
            this.widths.subject = Math.max(90, startWidth + (moveEv.clientX - startX));
        };
        const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    }

    cellValue(row, col) {
        const { score, is_scored, disabled } = this._cellGet(row, col);
        if (disabled) {
            return "";
        }
        return is_scored ? score : "";
    }

    cellTitle(row, col) {
        if (col.kind === "external") {
            return `External · ${this.formatPonderation(row.external_ponderation)}%`;
        }
        const ol = row.outcomes[col.pos];
        return ol ? `${ol.outcome_acronym || ""} · ${this.formatPonderation(ol.ponderation)}%` : "";
    }

    cellClass(row, col, rowIndex, colIndex) {
        const { score, is_scored, disabled } = this._cellGet(row, col);
        if (disabled) {
            return "o_grade_cell_disabled";
        }
        let cls = "";
        if (is_scored) {
            cls = score >= 5 ? "o_grade_cell_pass" : "o_grade_cell_fail";
        }
        if (col.kind === "external") {
            cls += " o_grade_matrix_sep";
        }
        if (rowIndex === this.sel.r && colIndex === this.sel.c) {
            cls += " o_grade_cell_anchor";
        }
        return cls;
    }

    staleClass() {
        return this.dirty.value ? "o_grade_cell_stale" : "";
    }

    // Subject columns (read the editable state from the buffer, computed values from the model snapshot).
    isOverridden(row) {
        const b = this.buffer.subjects[row.subjectLineId];
        return b ? b.is_overridden : false;
    }

    internalScore(row) {
        const b = this.buffer.subjects[row.subjectLineId];
        if (b && b.is_overridden) {
            return this.formatScore(b.internal_score);
        }
        return row.model.internal_is_scored ? this.formatScore(row.model.internal_score) : "";
    }

    internalCellClass(row) {
        return this.isOverridden(row) ? "o_grade_matrix_overridden" : this.staleClass();
    }

    finalScore(row) {
        return row.model.has_final ? this.formatScore(row.model.final_score) : "";
    }

    finalCellClass(row) {
        let cls = "o_grade_matrix_final";
        if (row.model.has_final) {
            cls += row.model.final_score >= 5 ? " o_grade_cell_pass" : " o_grade_cell_fail";
        }
        if (this.dirty.value) {
            cls += " o_grade_cell_stale";
        }
        return cls;
    }

    notesValue(row) {
        const b = this.buffer.subjects[row.subjectLineId];
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
        const b = this.buffer.subjects[row.subjectLineId];
        if (b) {
            b.is_overridden = ev.target.checked;
            this.dirty.value = true;
        }
    }

    onInternalChange(row, ev) {
        const b = this.buffer.subjects[row.subjectLineId];
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
        const b = this.buffer.subjects[row.subjectLineId];
        if (b) {
            b.notes = ev.target.value;
            this.dirty.value = true;
        }
    }

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

    // ── Selection / editing (single cell) ────────────────────────────────────

    isEditingAt(rowIndex, colIndex) {
        return this.edit.active && rowIndex === this.sel.r && colIndex === this.sel.c;
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

    onCellMouseDown(rowIndex, colIndex, ev) {
        const row = this.rows[rowIndex];
        const col = this.columns[colIndex];
        if (!row || !col || this._cellGet(row, col).disabled) {
            return;  // disabled cell is inert
        }
        ev.preventDefault();
        this.edit.active = false;
        this.sel.r = rowIndex;
        this.sel.c = colIndex;
        if (this.rootRef.el) {
            this.rootRef.el.focus();
        }
    }

    onCellDblClick(rowIndex, colIndex) {
        const row = this.rows[rowIndex];
        const col = this.columns[colIndex];
        if (!row || !col || this._cellGet(row, col).disabled) {
            return;
        }
        this.sel.r = rowIndex;
        this.sel.c = colIndex;
        this._startEdit();
    }

    // ── Editing (floating input over the selected cell) ──────────────────────

    _startEdit(initial) {
        const row = this.rows[this.sel.r];
        const col = this.columns[this.sel.c];
        if (!row || !col || this._cellGet(row, col).disabled) {
            return;
        }
        this.edit.selectAll = initial === undefined;
        if (initial === undefined) {
            const { score, is_scored } = this._cellGet(row, col);
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
        const row = this.rows[this.sel.r];
        const col = this.columns[this.sel.c];
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
            this._moveTo(this.sel.r + (ev.key === "Enter" ? 1 : 0), this.sel.c + (ev.key === "Tab" ? 1 : 0));
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
                this._moveTo(this.sel.r, this.sel.c + (goingRight ? 1 : -1));
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

    // Move the selection, skipping disabled cells: from the target, keep moving in the same horizontal
    // direction until a non-disabled cell is found (or an edge).
    _moveTo(rowIndex, colIndex) {
        const rows = this.rows;
        const cols = this.columns;
        let r = Math.max(0, Math.min(rows.length - 1, rowIndex));
        let c = Math.max(0, Math.min(cols.length - 1, colIndex));
        const dc = this.sel.c === null ? 0 : Math.sign(c - this.sel.c);
        while (rows[r] && cols[c] && this._cellGet(rows[r], cols[c]).disabled) {
            if (dc !== 0 && c + dc >= 0 && c + dc < cols.length) {
                c += dc;
            } else {
                break;
            }
        }
        if (rows[r] && cols[c] && this._cellGet(rows[r], cols[c]).disabled) {
            return;  // no editable target in that direction
        }
        this.sel.r = r;
        this.sel.c = c;
    }

    onRootKeydown(ev) {
        if (ev.key === "PageUp") {
            ev.preventDefault();
            this.prevStudent();
            return;
        }
        if (ev.key === "PageDown") {
            ev.preventDefault();
            this.nextStudent();
            return;
        }
        // With no cell selected, the left/right arrows page through students (like the ◀ ▶ buttons).
        if (!this.edit.active && this.sel.r === null) {
            if (ev.key === "ArrowLeft") {
                ev.preventDefault();
                this.prevStudent();
                return;
            }
            if (ev.key === "ArrowRight") {
                ev.preventDefault();
                this.nextStudent();
                return;
            }
        }
        if (this.edit.active || this.sel.r === null) {
            return;
        }
        switch (ev.key) {
            case "ArrowDown": ev.preventDefault(); this._moveTo(this.sel.r + 1, this.sel.c); return;
            case "ArrowUp": ev.preventDefault(); this._moveTo(this.sel.r - 1, this.sel.c); return;
            case "ArrowLeft": ev.preventDefault(); this._moveTo(this.sel.r, this.sel.c - 1); return;
            case "ArrowRight": ev.preventDefault(); this._moveTo(this.sel.r, this.sel.c + 1); return;
            case "Enter": ev.preventDefault(); this._startEdit(); return;
            case "Backspace":
            case "Delete": ev.preventDefault(); this._clearCell(); return;
            default:
                if (/^[0-9]$/.test(ev.key)) {
                    ev.preventDefault();
                    this._startEdit(ev.key);
                }
        }
    }

    _clearCell() {
        const row = this.rows[this.sel.r];
        const col = this.columns[this.sel.c];
        if (row && col && !this._cellGet(row, col).disabled) {
            this._cellSet(row, col, 0, false);
        }
    }

    // ── Leaving / switching with unapplied changes ───────────────────────────

    _confirmDiscard() {
        return new Promise((resolve) => {
            this.dialog.add(
                ConfirmationDialog,
                {
                    title: _t("Unapplied grade changes"),
                    body: _t("You have grade changes that have not been applied. If you leave now they will be lost."),
                    confirmLabel: _t("Leave and discard"),
                    confirm: () => resolve(true),
                    cancelLabel: _t("Stay"),
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            );
        });
    }

    _beforeLeave() {
        if (!this.dirty.value) {
            return;
        }
        return this._confirmDiscard();
    }

    _beforeUnload(ev) {
        if (this.dirty.value) {
            ev.preventDefault();
            ev.returnValue = "Unapplied changes";
        }
    }

    // ── Apply (buffer -> records -> reload) ──────────────────────────────────

    async applyChanges() {
        if (!this.dirty.value || this.applying.value) {
            return;
        }
        this.applying.value = true;
        try {
            await this._applyChanges();
        } catch (e) {
            this.notification.add(e.data && e.data.message ? e.data.message : (e.message || String(e)), {
                type: "danger",
                sticky: true,
            });
        } finally {
            this.applying.value = false;
        }
    }

    async _applyChanges() {
        for (const [id, b] of Object.entries(this.buffer.outcomes)) {
            const raw = this._outRaw[id];
            if (raw && (b.score !== raw.score || b.is_scored !== raw.is_scored)) {
                await this.orm.write("ems.grade_outcome_line", [Number(id)], {
                    score: b.score,
                    is_scored: b.is_scored,
                });
            }
        }
        for (const [id, b] of Object.entries(this.buffer.subjects)) {
            const raw = this._subRaw[id];
            if (!raw) {
                continue;
            }
            const vals = {};
            if (b.external_score !== raw.external_score) {
                vals.external_score = b.external_score;
            }
            if (b.external_is_scored !== raw.external_is_scored) {
                vals.external_is_scored = b.external_is_scored;
            }
            if (b.is_overridden !== raw.is_overridden) {
                vals.is_overridden = b.is_overridden;
            }
            if ((b.notes || "") !== (raw.notes || "")) {
                vals.notes = b.notes;
            }
            // The manual internal grade is only meaningful (and written) while overridden.
            if (b.is_overridden && b.internal_score !== raw.internal_score) {
                vals.internal_score = b.internal_score;
            }
            if (Object.keys(vals).length) {
                await this.orm.write("ems.grade_subject_line", [Number(id)], vals);
            }
        }
        await this._load();
    }
}

registry.category("actions").add("ems.grade_tutor_matrix", GradeTutorMatrix);
