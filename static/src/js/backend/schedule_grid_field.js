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
// does not apply). Read-only by default; "Edit" turns every hourly cell into two dropdowns (subject and
// group, or a non-teaching reason) backed by a LOCAL BUFFER, mirroring the grade matrix widget: nothing
// is written until "Save" is pressed. Saving replaces the whole weekday schedule in one server call
// (which also re-derives 'teaching_ids' from it — see 'ems.teaching.sync_from_schedule'), so the buffer
// (seeded from every existing entry) is always the single source of truth for what gets written.
export class ScheduleGridField extends Component {
    static template = "ems.ScheduleGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.editing = useState({ value: false });
        this.buffer = useState({});
        this.dirty = useState({ value: false });
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

    entriesForDay(dayIndex) {
        return this.entries.filter((entry) => Number(entry.data.dayofweek) === dayIndex);
    }

    entryStyle(entry) {
        const { start } = this.bounds;
        const top = (entry.data.hour_from - start) * PX_PER_HOUR;
        const height = Math.max(34, (entry.data.hour_to - entry.data.hour_from) * PX_PER_HOUR);
        return `top:${top}px;height:${height}px`;
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

    // ── Edit mode (two dropdowns per hour, buffered) ─────────────────────────

    get subjectOptions() {
        return [
            { key: "", label: "—" },
            ...this.catalog.nonTeaching.map(([value, label]) => ({ key: `n_${value}`, label, group: _t("Non-teaching") })),
            ...this.catalog.subjects.map((subject) => ({ key: `s_${subject.id}`, label: subject.display_name, group: _t("Subjects") })),
        ];
    }

    get groupOptions() {
        return [{ key: "", label: "—" }, ...this.catalog.groups.map((group) => ({ key: String(group.id), label: group.display_name }))];
    }

    _cellKey(dayIndex, hour) {
        return `${dayIndex}_${hour}`;
    }

    _emptyCell() {
        return { kind: "empty", subjectId: false, groupId: false, nonTeaching: false };
    }

    _cellStateForEntry(entry) {
        if (entry.data.non_teaching) {
            return { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: entry.data.non_teaching };
        }
        const subjectId = entry.data.subject_id ? entry.data.subject_id[0] : false;
        const groupIds = entry.data.group_ids ? entry.data.group_ids.currentIds : [];
        if (subjectId) {
            return { kind: "subject", subjectId, groupId: groupIds.length ? groupIds[0] : false, nonTeaching: false };
        }
        return this._emptyCell();
    }

    startEdit() {
        const buffer = {};
        for (const dayIndex of WEEKDAYS) {
            for (const hour of this.hours) {
                buffer[this._cellKey(dayIndex, hour)] = this._emptyCell();
            }
        }
        for (const entry of this.entries) {
            const dayIndex = Number(entry.data.dayofweek);
            if (!WEEKDAYS.includes(dayIndex)) {
                continue;
            }
            const state = this._cellStateForEntry(entry);
            for (let hour = Math.floor(entry.data.hour_from); hour < Math.ceil(entry.data.hour_to); hour++) {
                buffer[this._cellKey(dayIndex, hour)] = state;
            }
        }
        for (const key of Object.keys(this.buffer)) {
            delete this.buffer[key];
        }
        Object.assign(this.buffer, buffer);
        this.dirty.value = false;
        this.editing.value = true;
    }

    cancelEdit() {
        this.editing.value = false;
        this.dirty.value = false;
    }

    cellState(dayIndex, hour) {
        return this.buffer[this._cellKey(dayIndex, hour)] || this._emptyCell();
    }

    onSubjectChange(dayIndex, hour, ev) {
        const key = this._cellKey(dayIndex, hour);
        const value = ev.target.value;
        if (value.startsWith("n_")) {
            this.buffer[key] = { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: value.slice(2) };
        } else if (value.startsWith("s_")) {
            const previous = this.cellState(dayIndex, hour);
            this.buffer[key] = { kind: "subject", subjectId: Number(value.slice(2)), groupId: previous.groupId, nonTeaching: false };
        } else {
            this.buffer[key] = this._emptyCell();
        }
        this.dirty.value = true;
    }

    onGroupChange(dayIndex, hour, ev) {
        const key = this._cellKey(dayIndex, hour);
        const previous = this.cellState(dayIndex, hour);
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
        return "";
    }

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
            for (const hour of this.hours) {
                const state = this.buffer[this._cellKey(dayIndex, hour)];
                if (!state || state.kind === "empty") {
                    continue;
                }
                const cell = {
                    dayofweek: String(dayIndex),
                    hour_from: hour,
                    hour_to: hour + 1,
                    day_period: hour < 13 ? "morning" : "afternoon",
                };
                if (state.kind === "subject" && state.subjectId && state.groupId) {
                    cell.subject_id = state.subjectId;
                    cell.group_ids = [state.groupId];
                    cell.name = `${subjectById.get(state.subjectId)}: ${groupById.get(state.groupId)}`;
                } else if (state.kind === "non_teaching") {
                    cell.non_teaching = state.nonTeaching;
                    cell.name = nonTeachingByCode.get(state.nonTeaching) || state.nonTeaching;
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
