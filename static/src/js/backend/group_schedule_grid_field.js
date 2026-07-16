/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { PX_PER_HOUR, MIN_ENTRY_HEIGHT, dayLabels, computeBounds, formatHour, formatHourMinutes } from "./schedule_grid_geometry";

// Read-only weekly grid for a GROUP's schedule (day columns x hourly rows), built client-side from
// this group's own 'schedule_attendance_ids' — an aggregation, across every teacher's calendar that
// includes this group, of real teaching slots plus (when derivable) the group's break period — see
// ems.group._compute_schedule_attendance_ids. Unlike the teacher's own 'schedule_grid' widget this
// has no edit buffer/toolbar beyond 'PDF' — editing always happens from the relevant teacher's own
// Schedule tab. Co-teaching (two teachers, same subject, same slot) collapses into ONE block here
// (never one per teacher) — see who teaches what in the "Subject -> Teacher(s)" table below the grid.
export class GroupScheduleGridField extends Component {
    static template = "ems.GroupScheduleGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.actionService = useService("action");
    }

    get entries() {
        return this.props.record.data[this.props.name].records;
    }

    get days() {
        return dayLabels().map((label, index) => ({ index, label }));
    }

    get bounds() {
        return computeBounds(this.entries.map((entry) => ({ hour_from: entry.data.hour_from, hour_to: entry.data.hour_to })));
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

    entriesForDay(dayIndex) {
        return this.entries.filter((entry) => Number(entry.data.dayofweek) === dayIndex);
    }

    // Groups a day's entries into visual blocks: entries sharing the same (hour_from, hour_to) AND
    // the same subject/non-teaching reason collapse into ONE block — co-teaching never repeats a
    // block per teacher (see the class comment above).
    blocksForDay(dayIndex) {
        const blocks = new Map();
        for (const entry of this.entriesForDay(dayIndex)) {
            const key = `${entry.data.hour_from}_${entry.data.hour_to}_${this._blockKey(entry)}`;
            if (!blocks.has(key)) {
                blocks.set(key, { hour_from: entry.data.hour_from, hour_to: entry.data.hour_to, entries: [] });
            }
            blocks.get(key).entries.push(entry);
        }
        return [...blocks.values()];
    }

    _blockKey(entry) {
        return entry.data.non_teaching ? `n_${entry.data.non_teaching[0]}` : `s_${entry.data.subject_id[0]}`;
    }

    blockStyle(block) {
        const { start } = this.bounds;
        const top = (block.hour_from - start) * PX_PER_HOUR;
        const naturalHeight = (block.hour_to - block.hour_from) * PX_PER_HOUR;
        // A break block is kept at its true, exact duration — stretching it past that would
        // visually bleed into whatever comes right after it (a group's schedule, unlike a single
        // teacher's, can genuinely have several simultaneous entries — electives, co-teaching —
        // right around the break, so an oversized break block is especially likely to bury one of
        // them; see also the CSS z-index rule that keeps teaching blocks on top regardless).
        const height = this.blockIsBreak(block) ? naturalHeight : Math.max(MIN_ENTRY_HEIGHT, naturalHeight);
        return `top:${top}px;height:${height}px`;
    }

    blockIsBreak(block) {
        return !!block.entries[0].data.non_teaching_is_break;
    }

    // A break block is too short to fit a time line + a label line (see MIN_ENTRY_HEIGHT's own
    // comment in blockStyle) — time and label are shown together on one compact line instead.
    blockCompactText(block) {
        return `${this.blockTime(block)} ${this.blockLabel(block)}`;
    }

    // Never 'entry.data.name': that Char is frozen in whatever language was active when the row was
    // saved (see resource.calendar.attendance.get_report_label()'s own reasoning) — subject_id/
    // non_teaching's own labels resolve to the current UI language for free.
    blockLabel(block) {
        const entry = block.entries[0].data;
        return entry.non_teaching ? entry.non_teaching[1] : entry.subject_id[1];
    }

    blockRoom(block) {
        const space = block.entries[0].data.space_id;
        return space ? space[1] : "";
    }

    blockTime(block) {
        return `${formatHourMinutes(block.hour_from)}-${formatHourMinutes(block.hour_to)}`;
    }

    // "Subject -> Teacher(s)" summary table, below the grid: one row per distinct subject taught to
    // this group, with the sorted, de-duplicated teacher names — this is where co-teaching becomes
    // visible (more than one name in a row), instead of in the grid above.
    get subjectTeachersSummary() {
        const teachersBySubject = new Map();
        for (const entry of this.entries) {
            if (!entry.data.subject_id) {
                continue;
            }
            const label = entry.data.subject_id[1];
            if (!teachersBySubject.has(label)) {
                teachersBySubject.set(label, new Set());
            }
            if (entry.data.employee_id) {
                teachersBySubject.get(label).add(entry.data.employee_id[1]);
            }
        }
        return [...teachersBySubject.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([subject, teachers]) => ({ subject, teachers: [...teachers].sort().join(", ") }));
    }

    async onPdfClick() {
        await this.actionService.doAction("ems.action_report_group_schedule", {
            additionalContext: { active_ids: [this.props.record.resId] },
        });
    }
}

export const groupScheduleGridField = {
    component: GroupScheduleGridField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("group_schedule_grid", groupScheduleGridField);
