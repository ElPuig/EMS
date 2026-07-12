/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const PX_PER_HOUR = 48;
const DEFAULT_START = 8;
const DEFAULT_END = 20;
const WEEKDAYS = [0, 1, 2, 3, 4];

function dayLabels() {
    return [_t("Monday"), _t("Tuesday"), _t("Wednesday"), _t("Thursday"), _t("Friday")];
}

// Visual weekly grid (day columns x hourly rows) for a resource.calendar's weekly attendance slots
// (dayofweek/hour_from/hour_to — a recurring pattern, not real dates, so the native <calendar> view
// does not apply). Read-only by default; three actions turn it into an editable buffer (mirroring the
// grade matrix widget: nothing is written until "Save" is pressed, "Cancel" discards):
//   - "Edit": edit the teacher's current schedule in place (two dropdowns per period: subject+group, or
//     a non-teaching reason).
//   - "Import": opens the XML planner importer already scoped to this teacher (no email lookup needed).
//   - "New": seed the buffer from either a blank schedule framework (a level's period times, still
//     unassigned) or another teacher's current schedule (handy for substitutions) — replacing the whole
//     buffer, but only written to the server on "Save".
// Saving replaces the whole weekday schedule in one server call (which also re-derives 'teaching_ids'
// and 'ems.attendance_template' from it), so the buffer is always the single source of truth for what
// gets written. Edit mode's rows are the DISTINCT real periods found in whatever was loaded (own
// schedule, a framework, a colleague's schedule) — not fixed hourly slots — so saving always writes the
// exact (possibly non-hour-aligned) hour_from/hour_to of that period, never a rounded one. A cell with
// no subject/non-teaching but backed by a real source row ('blank') is still written as a placeholder
// period instead of being dropped like a truly empty cell.
export class ScheduleGridField extends Component {
    static template = "ems.ScheduleGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.editing = useState({ value: false });
        this.buffer = useState({});
        this.dirty = useState({ value: false });
        this.periods = useState({ list: [] });
        this._nextPeriodId = 1;
        this.newPanel = useState({ open: false, value: "", frameworks: [], teachers: [] });
        this.catalog = useState({ subjects: [], groups: [], nonTeaching: [] });
        onWillStart(async () => {
            const [subjects, groups, attendanceFields] = await Promise.all([
                this.orm.searchRead("ems.subject", [], ["id", "display_name"]),
                this.orm.searchRead("ems.group", [], ["id", "display_name"]),
                this.orm.call("resource.calendar.attendance", "fields_get", [["non_teaching"], ["selection"]]),
            ]);
            this.catalog.subjects = subjects;
            this.catalog.groups = groups;
            this.catalog.nonTeaching = attendanceFields.non_teaching.selection.filter((item) => item[0]);
        });
    }

    get calendarId() {
        const value = this.props.record.data.resource_calendar_id;
        return value ? value[0] : false;
    }

    get entries() {
        return this.props.record.data[this.props.name].records;
    }

    get days() {
        return dayLabels().map((label, index) => ({ index, label }));
    }

    get bounds() {
        let start = DEFAULT_START;
        let end = DEFAULT_END;
        for (const entry of this.entries) {
            start = Math.min(start, Math.floor(entry.data.hour_from));
            end = Math.max(end, Math.ceil(entry.data.hour_to));
        }
        return { start, end };
    }

    get hours() {
        const { start, end } = this.bounds;
        const hours = [];
        for (let h = start; h < end; h++) {
            hours.push(h);
        }
        return hours;
    }

    columnStyle() {
        const { start, end } = this.bounds;
        return `height:${(end - start) * PX_PER_HOUR}px`;
    }

    formatHour(hour) {
        return `${String(hour).padStart(2, "0")}:00`;
    }

    // ── View mode (read-only visual blocks) ──────────────────────────────────

    // Blank/unassigned periods (patio, still-unassigned template slots...) are kept as real rows so
    // the exact times survive for the next edit, but are not worth a visible "Free" block here — the
    // row/gap structure already makes it clear something is expected there.
    entriesForDay(dayIndex) {
        return this.entries.filter((entry) => Number(entry.data.dayofweek) === dayIndex && !this.entryIsBlank(entry));
    }

    entryStyle(entry) {
        const { start } = this.bounds;
        const top = (entry.data.hour_from - start) * PX_PER_HOUR;
        const height = Math.max(34, (entry.data.hour_to - entry.data.hour_from) * PX_PER_HOUR);
        return `top:${top}px;height:${height}px`;
    }

    entryIsBlank(entry) {
        return !entry.data.subject_id && !entry.data.non_teaching;
    }

    entryLabel(entry) {
        return entry.data.name || "";
    }

    entryRoom(entry) {
        return entry.data.space_id ? entry.data.space_id[1] : "";
    }

    // Exact start-end time, since slots are not always hour-aligned (e.g. 08:00-08:55).
    entryTime(entry) {
        return `${this.formatHourMinutes(entry.data.hour_from)}-${this.formatHourMinutes(entry.data.hour_to)}`;
    }

    formatHourMinutes(value) {
        const hour = Math.floor(value);
        const minutes = Math.round((value - hour) * 60);
        return `${String(hour).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
    }

    // ── Edit mode (two dropdowns per real period, buffered) ──────────────────

    get subjectOptions() {
        return [
            { key: "", label: "—" },
            ...this.catalog.nonTeaching.map(([value, label]) => ({ key: `n_${value}`, label, group: _t("Non-teaching") })),
            ...this.catalog.subjects.map((subject) => ({ key: `s_${subject.id}`, label: subject.display_name, group: _t("Subjects") })),
        ];
    }

    get sortedPeriods() {
        return [...this.periods.list].sort((a, b) => a.hour_from - b.hour_from);
    }

    periodLabel(period) {
        return `${this.formatHourMinutes(period.hour_from)}-${this.formatHourMinutes(period.hour_to)}`;
    }

    _timeToHour(value) {
        const [h, m] = value.split(":").map(Number);
        return h + m / 60;
    }

    hourToTimeInput(value) {
        const hour = Math.floor(value);
        const minutes = Math.round((value - hour) * 60);
        return `${String(hour).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
    }

    // Periods are identified by a stable id, never by their (sorted) display position — editing a
    // period's time, or inserting a new one, must never shift what the buffer's existing cells point to.
    _cellKey(dayIndex, periodId) {
        return `${dayIndex}_${periodId}`;
    }

    _emptyCell() {
        return { kind: "empty", subjectId: false, groupId: false, nonTeaching: false };
    }

    // Normalizes either an Odoo record (has '.data', many2one as [id, label], x2many as a StaticList) or
    // a plain search_read dict (many2one as [id, label] too, many2many as a plain array of ids) into a
    // common shape.
    _normalizeEntry(raw) {
        const data = raw.data || raw;
        const groupIds = data.group_ids && data.group_ids.currentIds ? data.group_ids.currentIds : (data.group_ids || []);
        return {
            dayofweek: Number(data.dayofweek),
            hour_from: data.hour_from,
            hour_to: data.hour_to,
            non_teaching: data.non_teaching || false,
            subjectId: data.subject_id ? data.subject_id[0] : false,
            groupId: groupIds.length ? groupIds[0] : false,
        };
    }

    // A real attendance row with no subject/non-teaching is a 'blank' (still-unassigned) period, not an
    // 'empty' cell — it must stay written on save so its exact (possibly non-hour-aligned) time survives.
    _stateFromNormalized(norm) {
        if (norm.non_teaching) {
            return { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: norm.non_teaching };
        }
        if (norm.subjectId) {
            return { kind: "subject", subjectId: norm.subjectId, groupId: norm.groupId, nonTeaching: false };
        }
        return { kind: "blank", subjectId: false, groupId: false, nonTeaching: false };
    }

    // Rebuilds the whole buffer from a list of raw entries (own current entries, a framework's periods,
    // or another teacher's schedule). The edit grid's rows are the DISTINCT (hour_from, hour_to) pairs
    // found across every entry (any weekday) — a school's bell schedule is one fixed set of periods
    // repeated each day, with some days skipping or adding one (e.g. a Wednesday-only meeting) — so this
    // naturally reproduces the real timetable instead of an hour-rounded approximation.
    _seedBufferFromEntries(rawEntries) {
        const normalized = rawEntries.map((raw) => this._normalizeEntry(raw)).filter((n) => WEEKDAYS.includes(n.dayofweek));

        this._nextPeriodId = 1;
        const periodKey = (n) => `${n.hour_from}_${n.hour_to}`;
        const periodIdByKey = new Map();
        const periods = [];
        for (const n of normalized) {
            const key = periodKey(n);
            if (!periodIdByKey.has(key)) {
                const id = this._nextPeriodId++;
                periodIdByKey.set(key, id);
                periods.push({ id, hour_from: n.hour_from, hour_to: n.hour_to });
            }
        }

        const buffer = {};
        for (const dayIndex of WEEKDAYS) {
            for (const period of periods) {
                buffer[this._cellKey(dayIndex, period.id)] = this._emptyCell();
            }
        }
        for (const n of normalized) {
            const periodId = periodIdByKey.get(periodKey(n));
            buffer[this._cellKey(n.dayofweek, periodId)] = this._stateFromNormalized(n);
        }

        for (const key of Object.keys(this.buffer)) {
            delete this.buffer[key];
        }
        Object.assign(this.buffer, buffer);
        this.periods.list = periods;
    }

    // Lets the admin build a period the loaded source didn't have (e.g. a teacher mixing two levels'
    // bell schedules by hand) instead of being limited to whatever was already there.
    addPeriod() {
        const last = this.sortedPeriods[this.sortedPeriods.length - 1];
        const hour_from = last ? last.hour_to : DEFAULT_START;
        const id = this._nextPeriodId++;
        this.periods.list.push({ id, hour_from, hour_to: hour_from + 1 });
        for (const dayIndex of WEEKDAYS) {
            this.buffer[this._cellKey(dayIndex, id)] = this._emptyCell();
        }
        this.dirty.value = true;
    }

    removePeriod(periodId) {
        const index = this.periods.list.findIndex((period) => period.id === periodId);
        if (index !== -1) {
            this.periods.list.splice(index, 1);
        }
        for (const dayIndex of WEEKDAYS) {
            delete this.buffer[this._cellKey(dayIndex, periodId)];
        }
        this.dirty.value = true;
    }

    onPeriodTimeChange(periodId, field, ev) {
        const period = this.periods.list.find((p) => p.id === periodId);
        if (!period) {
            return;
        }
        const value = this._timeToHour(ev.target.value);
        if (field === "hour_from") {
            // Moving the start moves the whole block, keeping its original duration — otherwise
            // dragging the start later/earlier while the end stays put can silently balloon the
            // block into one spanning most of the day, overlapping (and auto-clearing) everything.
            const duration = period.hour_to - period.hour_from;
            period.hour_from = value;
            period.hour_to = value + duration;
        } else {
            period.hour_to = value;
        }
        for (const dayIndex of WEEKDAYS) {
            this._clearOverlappingCells(dayIndex, periodId);
        }
        this.dirty.value = true;
    }

    // A period that looks empty in the grid can still be a real row inherited from whatever was
    // loaded (a framework's own hourly blocks, a colleague's schedule...) — assigning a genuinely
    // different time elsewhere on the same day must not silently leave that old row in place, or
    // saving fails server-side with "Attendances can't overlap" for a conflict the admin never saw.
    _periodsOverlap(a, b) {
        return a.hour_from < b.hour_to && b.hour_from < a.hour_to;
    }

    _clearOverlappingCells(dayIndex, periodId) {
        const period = this.periods.list.find((p) => p.id === periodId);
        if (!period) {
            return;
        }
        for (const other of this.periods.list) {
            if (other.id === periodId || !this._periodsOverlap(period, other)) {
                continue;
            }
            const key = this._cellKey(dayIndex, other.id);
            if (this.buffer[key] && this.buffer[key].kind !== "empty") {
                this.buffer[key] = this._emptyCell();
            }
        }
    }

    startEdit() {
        this._seedBufferFromEntries(this.entries);
        this.dirty.value = false;
        this.editing.value = true;
    }

    cancelEdit() {
        this.editing.value = false;
        this.dirty.value = false;
        this.newPanel.open = false;
    }

    cellState(dayIndex, periodId) {
        return this.buffer[this._cellKey(dayIndex, periodId)] || this._emptyCell();
    }

    onSubjectChange(dayIndex, periodId, ev) {
        const key = this._cellKey(dayIndex, periodId);
        const value = ev.target.value;
        if (value.startsWith("n_")) {
            this.buffer[key] = { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: value.slice(2) };
            this._clearOverlappingCells(dayIndex, periodId);
        } else if (value.startsWith("s_")) {
            const previous = this.cellState(dayIndex, periodId);
            this.buffer[key] = { kind: "subject", subjectId: Number(value.slice(2)), groupId: previous.groupId, nonTeaching: false };
            this._clearOverlappingCells(dayIndex, periodId);
        } else {
            this.buffer[key] = this._emptyCell();
        }
        this.dirty.value = true;
    }

    onGroupChange(dayIndex, periodId, ev) {
        const key = this._cellKey(dayIndex, periodId);
        const previous = this.cellState(dayIndex, periodId);
        this.buffer[key] = { ...previous, groupId: ev.target.value ? Number(ev.target.value) : false };
        this.dirty.value = true;
    }

    subjectSelectValue(state) {
        if (state.kind === "non_teaching") {
            return `n_${state.nonTeaching}`;
        }
        if (state.kind === "subject") {
            return `s_${state.subjectId}`;
        }
        return ""; // 'empty' and 'blank' both show as "—" until the admin picks something
    }

    // ── Import (opens the XML importer already scoped to this teacher) ───────

    async onImportClick() {
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ems.working_schedules_import_wizard",
                views: [[false, "form"]],
                target: "new",
                context: { default_teacher_id: this.props.record.resId },
            },
            { onClose: () => this.props.record.load() }
        );
    }

    // ── New (blank framework or copy from another teacher) ───────────────────

    async openNewPanel() {
        if (!this.newPanel.frameworks.length && !this.newPanel.teachers.length) {
            const [frameworks, teachers] = await Promise.all([
                this.orm.searchRead("resource.calendar", [["is_framework", "=", true]], ["id", "display_name"]),
                this.orm.searchRead(
                    "hr.employee",
                    [
                        ["id", "!=", this.props.record.resId],
                        ["employee_type", "=", "teacher"],
                        ["resource_calendar_id", "!=", false],
                    ],
                    ["id", "display_name", "resource_calendar_id"]
                ),
            ]);
            this.newPanel.frameworks = frameworks;
            this.newPanel.teachers = teachers;
        }
        this.newPanel.value = "";
        this.newPanel.open = true;
    }

    onNewSourceChange(ev) {
        this.newPanel.value = ev.target.value;
    }

    cancelNewPanel() {
        this.newPanel.open = false;
    }

    async loadNewSource() {
        if (!this.newPanel.value) {
            return;
        }
        const calendarId = Number(this.newPanel.value.slice(2));
        this.newPanel.open = false;
        const rawEntries = await this.orm.searchRead(
            "resource.calendar.attendance",
            [["calendar_id", "=", calendarId]],
            ["dayofweek", "hour_from", "hour_to", "non_teaching", "subject_id", "group_ids"]
        );
        this._seedBufferFromEntries(rawEntries);
        this.dirty.value = true;
        this.editing.value = true;
    }

    // ── Apply (buffer -> records -> save) ─────────────────────────────────────

    async save() {
        if (!this.dirty.value) {
            this.editing.value = false;
            return;
        }
        const subjectById = new Map(this.catalog.subjects.map((s) => [s.id, s.display_name]));
        const groupById = new Map(this.catalog.groups.map((g) => [g.id, g.display_name]));
        const nonTeachingByCode = new Map(this.catalog.nonTeaching);
        const cells = [];
        for (const dayIndex of WEEKDAYS) {
            for (const period of this.periods.list) {
                const state = this.buffer[this._cellKey(dayIndex, period.id)];
                if (!state || state.kind === "empty") {
                    continue;
                }
                const cell = {
                    dayofweek: String(dayIndex),
                    hour_from: period.hour_from,
                    hour_to: period.hour_to,
                    day_period: period.hour_from < 13 ? "morning" : "afternoon",
                };
                if (state.kind === "subject" && state.subjectId && state.groupId) {
                    cell.subject_id = state.subjectId;
                    cell.group_ids = [state.groupId];
                    cell.name = `${subjectById.get(state.subjectId)}: ${groupById.get(state.groupId)}`;
                } else if (state.kind === "non_teaching") {
                    cell.non_teaching = state.nonTeaching;
                    cell.name = nonTeachingByCode.get(state.nonTeaching) || state.nonTeaching;
                } else if (state.kind === "blank") {
                    cell.name = "Free";
                } else {
                    continue; // a subject was picked but no group yet: skip until both are set
                }
                cells.push(cell);
            }
        }
        await this.orm.call("resource.calendar", "apply_schedule_changes", [[this.calendarId], cells]);
        await this.props.record.load();
        this.editing.value = false;
        this.dirty.value = false;
    }
}

export const scheduleGridField = {
    component: ScheduleGridField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("schedule_grid", scheduleGridField);
