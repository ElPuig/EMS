/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { PX_PER_HOUR, DEFAULT_START, WEEKDAYS, MIN_ENTRY_HEIGHT, dayLabels, computeBounds, formatHour, formatHourMinutes, buildColorMap } from "./schedule_grid_geometry";

const ATTENDANCE_FIELDS = ["dayofweek", "hour_from", "hour_to", "non_teaching", "subject_id", "group_ids"];

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
// Unassigned slots are NEVER stored as real attendance rows — only what the teacher actually teaches
// (or a real non-teaching commitment, e.g. patio/meeting) gets written. So the blank/gap structure the
// grid shows while editing comes from TWO merged sources: the calendar's reference framework
// ('source_framework_id', fetched live every time — its periods, including its own patio/meeting rows,
// seed the buffer as a baseline) and the teacher's own real saved entries (which always win over that
// baseline for the same day+period, and can add entirely new periods the framework never had). Saving
// always writes the exact (possibly non-hour-aligned) hour_from/hour_to of each real period, never a
// rounded one, and records which framework was used so the next "Edit" keeps showing the right gaps.
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
        this._pendingSourceFrameworkId = false;
        this.newPanel = useState({ open: false, value: "", frameworks: [], teachers: [] });
        this.catalog = useState({ subjects: [], groups: [], nonTeaching: [] });
        this.summary = useState({ teaching: { rows: [], total: 0 }, fixed: { rows: [], total: 0 }, total: 0 });
        this.derivedBreaks = useState({ list: [] });
        onWillStart(async () => {
            const [subjects, groups, nonTeachingTypes] = await Promise.all([
                this.orm.searchRead("ems.subject", [], ["id", "display_name"]),
                this.orm.searchRead("ems.group", [], ["id", "display_name"]),
                this.orm.searchRead("ems.non_teaching_type", [], ["id", "name"]),
                this._loadSummary(),
                this._loadDerivedBreaks(),
            ]);
            this.catalog.subjects = subjects;
            this.catalog.groups = groups;
            this.catalog.nonTeaching = nonTeachingTypes.map((item) => [item.id, item.name]);
        });
    }

    // Weekly hours summary table (below the grid, view mode only) — always reflects the last SAVED
    // schedule, never the in-progress edit buffer (see the class comment on 'apply_schedule_changes'
    // for why unsaved state shouldn't drive server-computed aggregates).
    async _loadSummary() {
        if (!this.calendarId) {
            return;
        }
        const result = await this.orm.call("resource.calendar", "get_schedule_hours_summary", [[this.calendarId]]);
        this.summary.teaching = result.teaching;
        this.summary.fixed = result.fixed;
        this.summary.total = result.total;
    }

    get calendarId() {
        const value = this.props.record.data.resource_calendar_id;
        return value ? value[0] : false;
    }

    // Fetched explicitly (orm.call), not read off the record as a form field — see
    // hr.employee.get_derived_break_attendance_data()'s own docstring for why a hidden Many2many
    // field with its own embedded <list> turned out not to reliably load its sub-fields
    // client-side, despite computing correctly server-side (the PDF report proved that). '.read()'
    // returns Many2one fields as a (id, name) array, matching what entryLabel/entryRoom already
    // expect from a real x2many record's own data.
    async _loadDerivedBreaks() {
        if (!this.props.record.resId) {
            return;
        }
        const rows = await this.orm.call("hr.employee", "get_derived_break_attendance_data", [[this.props.record.resId]]);
        this.derivedBreaks.list = rows.map((row) => ({ id: row.id, data: row }));
    }

    // Edit/Import/New require 'ems.group_department_chief' or above (see hr.employee's
    // 'can_edit_schedule' compute) — enforced server-side via ir.model.access.csv, this getter only
    // drives the toolbar's own visibility. 'PDF' is deliberately NOT gated by it: every role that
    // can already read a schedule may also export it.
    get canEdit() {
        return !!this.props.record.data.can_edit_schedule;
    }

    get entries() {
        return this.props.record.data[this.props.name].records;
    }

    // Gap-filled break(s) this teacher has no real saved row for yet (see
    // hr.employee._get_derived_break_entries(), fetched via _loadDerivedBreaks()) —
    // deliberately a SEPARATE list from 'entries', merged in only by 'entriesForDay' (view mode)
    // below, never by anything the Edit buffer reads, so a derived break can never get silently
    // "adopted" as real on Save.
    get derivedBreakEntries() {
        return this.derivedBreaks.list;
    }

    get days() {
        return dayLabels().map((label, index) => ({ index, label }));
    }

    // Guards against a zero/invalid-duration entry (hour_to <= hour_from, or a missing value)
    // ever widening the axis or rendering as a degenerate block — never legitimate schedule data.
    _hasValidDuration(entry) {
        return Number.isFinite(entry.data.hour_from) && Number.isFinite(entry.data.hour_to) && entry.data.hour_to > entry.data.hour_from;
    }

    get bounds() {
        return computeBounds(
            [...this.entries, ...this.derivedBreakEntries]
                .filter((entry) => this._hasValidDuration(entry))
                .map((entry) => ({ hour_from: entry.data.hour_from, hour_to: entry.data.hour_to }))
        );
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
        return formatHour(hour);
    }

    // ── View mode (read-only visual blocks) ──────────────────────────────────

    // Blank/unassigned periods are never saved (see the class comment), so in practice every real
    // entry here already has a subject or a non-teaching reason — this filter is just a safety net.
    // A derived break only fills in a slot no real entry already occupies (a real, explicitly
    // saved break always wins).
    entriesForDay(dayIndex) {
        const real = this.entries.filter(
            (entry) => Number(entry.data.dayofweek) === dayIndex && !this.entryIsBlank(entry) && this._hasValidDuration(entry)
        );
        const occupied = new Set(real.map((entry) => `${entry.data.hour_from}_${entry.data.hour_to}`));
        const derived = this.derivedBreakEntries.filter((entry) =>
            Number(entry.data.dayofweek) === dayIndex && this._hasValidDuration(entry) && !occupied.has(`${entry.data.hour_from}_${entry.data.hour_to}`));
        return [...real, ...derived];
    }

    entryStyle(entry) {
        const { start } = this.bounds;
        const top = (entry.data.hour_from - start) * PX_PER_HOUR;
        const naturalHeight = (entry.data.hour_to - entry.data.hour_from) * PX_PER_HOUR;
        // A break specifically (not every non-teaching activity — a 1h guard duty or meeting has
        // plenty of room already) is kept at its true, exact duration — stretching it past that
        // would visually bleed into whatever comes right after it and hide it (MIN_ENTRY_HEIGHT
        // only helps a block that isn't sharing its vertical space with a neighbour).
        const height = entry.data.non_teaching_is_break ? naturalHeight : Math.max(MIN_ENTRY_HEIGHT, naturalHeight);
        const color = this.entryColor(entry);
        return `top:${top}px;height:${height}px${color ? `;background-color:${color}` : ""}`;
    }

    entryIsBlank(entry) {
        return !entry.data.subject_id && !entry.data.non_teaching;
    }

    // A subject or non-teaching *reason* (a meeting, a guard duty...) gets its own colour, distinct
    // from every other one appearing in this same schedule — but not a break specifically, which
    // already has its own fixed, distinctive look (a brown stripe, see .o_schedule_grid_entry_break
    // in schedule_grid.css) precisely so it never blends in as "just another activity".
    _colorKey(entry) {
        if (entry.data.non_teaching_is_break) {
            return null;
        }
        if (entry.data.non_teaching) {
            return `n_${entry.data.non_teaching[0]}`;
        }
        if (entry.data.subject_id) {
            return `s_${entry.data.subject_id[0]}`;
        }
        return null;
    }

    // Colours are assigned across every entry currently shown (real + derived breaks, though
    // breaks opt out via _colorKey), not the whole subject/activity catalogue — see buildColorMap.
    get colorByKey() {
        const items = [];
        for (const entry of [...this.entries, ...this.derivedBreakEntries]) {
            if (!this._hasValidDuration(entry)) {
                continue;
            }
            const key = this._colorKey(entry);
            if (key) {
                items.push({ key, dayofweek: Number(entry.data.dayofweek), hour_from: entry.data.hour_from });
            }
        }
        return buildColorMap(items);
    }

    entryColor(entry) {
        const key = this._colorKey(entry);
        return key ? this.colorByKey.get(key) : null;
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
        return formatHourMinutes(value);
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
            non_teaching: data.non_teaching ? data.non_teaching[0] : false,
            subjectId: data.subject_id ? data.subject_id[0] : false,
            groupId: groupIds.length ? groupIds[0] : false,
        };
    }

    // A framework/baseline row with no subject/non-teaching is a 'blank' (still-unassigned) period —
    // shown so the admin can fill it in, but never written on save (see the class comment).
    _stateFromNormalized(norm) {
        if (norm.non_teaching) {
            return { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: norm.non_teaching };
        }
        if (norm.subjectId) {
            return { kind: "subject", subjectId: norm.subjectId, groupId: norm.groupId, nonTeaching: false };
        }
        return { kind: "blank", subjectId: false, groupId: false, nonTeaching: false };
    }

    // Rebuilds the whole buffer by merging a baseline (a reference framework's own periods — some
    // blank, some real non-teaching commitments like patio/meetings) with the teacher's real saved
    // entries, which always win for the same day+period and can introduce entirely new periods the
    // baseline never had (e.g. a custom "Add period" block from a previous save). The edit grid's rows
    // are the DISTINCT (hour_from, hour_to) pairs found across everything (any weekday) — a school's
    // bell schedule is one fixed set of periods repeated each day, with some days skipping or adding
    // one (e.g. a Wednesday-only meeting) — so this naturally reproduces the real timetable instead of
    // an hour-rounded approximation.
    _seedBufferFromEntries(baselineEntries, realEntries = []) {
        const baseline = baselineEntries.map((raw) => this._normalizeEntry(raw)).filter((n) => WEEKDAYS.includes(n.dayofweek));
        const real = realEntries.map((raw) => this._normalizeEntry(raw)).filter((n) => WEEKDAYS.includes(n.dayofweek));

        this._nextPeriodId = 1;
        const periodKey = (n) => `${n.hour_from}_${n.hour_to}`;
        const periodIdByKey = new Map();
        const periods = [];
        const ensurePeriod = (n) => {
            const key = periodKey(n);
            if (!periodIdByKey.has(key)) {
                const id = this._nextPeriodId++;
                periodIdByKey.set(key, id);
                periods.push({ id, hour_from: n.hour_from, hour_to: n.hour_to });
            }
            return periodIdByKey.get(key);
        };

        const buffer = {};
        for (const n of baseline) {
            buffer[this._cellKey(n.dayofweek, ensurePeriod(n))] = this._stateFromNormalized(n);
        }
        for (const n of real) {
            buffer[this._cellKey(n.dayofweek, ensurePeriod(n))] = this._stateFromNormalized(n);
        }
        for (const dayIndex of WEEKDAYS) {
            for (const period of periods) {
                const key = this._cellKey(dayIndex, period.id);
                if (!(key in buffer)) {
                    buffer[key] = this._emptyCell();
                }
            }
        }

        for (const key of Object.keys(this.buffer)) {
            delete this.buffer[key];
        }
        Object.assign(this.buffer, buffer);
        this.periods.list = periods;
    }

    async _fetchFrameworkAttendances(frameworkId) {
        if (!frameworkId) {
            return [];
        }
        return this.orm.searchRead("resource.calendar.attendance", [["calendar_id", "=", frameworkId]], ATTENDANCE_FIELDS);
    }

    async _readSourceFrameworkId(calendarId) {
        const [record] = await this.orm.read("resource.calendar", [calendarId], ["source_framework_id"]);
        return record.source_framework_id ? record.source_framework_id[0] : false;
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
            // dragging the start later/earlier while the end stays put can silently balloon the block
            // into one spanning most of the day.
            const duration = period.hour_to - period.hour_from;
            period.hour_from = value;
            period.hour_to = value + duration;
        } else {
            period.hour_to = value;
        }
        this.dirty.value = true;
    }

    async startEdit() {
        const frameworkId = this.calendarId ? await this._readSourceFrameworkId(this.calendarId) : false;
        const baseline = await this._fetchFrameworkAttendances(frameworkId);
        this._seedBufferFromEntries(baseline, this.entries);
        this._pendingSourceFrameworkId = frameworkId;
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
            this.buffer[key] = { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: Number(value.slice(2)) };
        } else if (value.startsWith("s_")) {
            const previous = this.cellState(dayIndex, periodId);
            this.buffer[key] = { kind: "subject", subjectId: Number(value.slice(2)), groupId: previous.groupId, nonTeaching: false };
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

    // ── PDF (downloads the printable weekly schedule for this employee) ──────

    async onPdfClick() {
        await this.actionService.doAction("ems.action_report_working_schedule", {
            additionalContext: { active_ids: [this.props.record.resId] },
        });
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
        const kind = this.newPanel.value[0];
        const calendarId = Number(this.newPanel.value.slice(2));
        this.newPanel.open = false;

        // A framework IS the reference (its own periods become the baseline, nothing pre-assigned
        // yet); copying a colleague uses THEIR reference framework as the baseline and their real
        // schedule as the overlay, so the substitute inherits the same future blank slots too.
        let frameworkId = kind === "f" ? calendarId : await this._readSourceFrameworkId(calendarId);
        const realEntries = kind === "c" ? await this._fetchFrameworkAttendances(calendarId) : [];
        const baseline = await this._fetchFrameworkAttendances(frameworkId);

        this._seedBufferFromEntries(baseline, realEntries);
        this._pendingSourceFrameworkId = frameworkId;
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
        const nonTeachingById = new Map(this.catalog.nonTeaching);
        const cells = [];
        for (const dayIndex of WEEKDAYS) {
            for (const period of this.periods.list) {
                const state = this.buffer[this._cellKey(dayIndex, period.id)];
                // Blank/unassigned slots are never written — only a real subject or non-teaching
                // commitment is (see the class comment).
                if (!state || state.kind === "empty" || state.kind === "blank") {
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
                    cell.name = nonTeachingById.get(state.nonTeaching) || state.nonTeaching;
                } else {
                    continue; // a subject was picked but no group yet: skip until both are set
                }
                cells.push(cell);
            }
        }
        await this.orm.call("resource.calendar", "apply_schedule_changes", [[this.calendarId], cells, this._pendingSourceFrameworkId || false]);
        await this.props.record.load();
        await this._loadSummary();
        // A saved schedule change can open or close gaps, so the derived breaks may have changed too.
        await this._loadDerivedBreaks();
        this.editing.value = false;
        this.dirty.value = false;
    }
}

export const scheduleGridField = {
    component: ScheduleGridField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("schedule_grid", scheduleGridField);
