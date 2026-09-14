/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { PX_PER_HOUR, WEEKDAYS, MIN_ENTRY_HEIGHT, dayLabels, computeBounds, formatHour, formatHourMinutes, buildColorMap, layoutOverlappingBlocks } from "./schedule_grid_geometry";

// A record's own 'shift' field already tells us the realistic hour window for its schedule —
// unlike the teacher's grid (which has no single shift and must auto-fit whatever hours its
// entries span), this widget uses that fixed window instead, so it doesn't render a tall,
// mostly-empty axis for a record only ever scheduled in half of it. Kept in sync by hand with
// the equivalent SHIFT_HOURS in models/shared/schedule_report_mixin.py.
const SHIFT_HOURS = {
    morning: { start: 8, end: 15 },
    afternoon: { start: 15, end: 22 },
};

// PDF export action per model this widget is used on (see 'onPdfClick') — the widget itself is
// otherwise fully generic, so this is the one place a new caller needs to register itself.
const PDF_ACTION_BY_MODEL = {
    "ems.group": "ems.action_report_group_schedule",
    "res.partner": "ems.action_report_student_schedule",
};

// Mostly-read-only weekly grid (day columns x hourly rows) for any record exposing its own
// aggregated 'schedule_attendance_ids' (a Many2many of resource.calendar.attendance, computed,
// not stored — see ems.group._compute_schedule_attendance_ids and res.partner (student)'s own
// version) — originally built for a GROUP's schedule (aggregating every teacher whose calendar
// includes that group) and reused as-is for a STUDENT's schedule (aggregating every entry
// matching one of their own subject+group enrollment pairs) since the two are the exact same
// rendering problem: a "photo" built entirely client-side from prefetched sub-records. Day/hour/
// subject/teacher(s)/groups always stay read-only here — those still require the relevant
// teacher's own Schedule tab. Issue #446 added ONE exception: a permission-gated "Edit" mode
// (see 'canEditSchedule' below, true only for 'ems.group' and only for
// 'ems.group_department_chief' and above — a student's own tab never has it) turns each day's
// blocks into cards, mirroring the teacher's own edit mode's visual language, where 'topic' and
// classroom become editable while everything else on the card stays plain text.
// Co-teaching (two teachers, same subject, same slot) collapses into ONE block (never one per
// teacher) — see who teaches what in the "Subject -> Teacher(s)" table below the grid.
export class ReadonlyScheduleGridField extends Component {
    static template = "ems.ReadonlyScheduleGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        // Issue #446 - card-based edit mode for 'topic'/classroom, gated by 'can_edit_schedule'
        // (only ever true on 'ems.group', never on a student's own read-only tab - see the
        // field's own docstring, models/contacts/group.py).
        this.editing = useState({ value: false });
        this.buffer = useState({ 0: [], 1: [], 2: [], 3: [], 4: [] });
        this.catalog = useState({ spaces: [] });
        onWillStart(async () => {
            this.catalog.spaces = await this.orm.searchRead("ems.space", [], ["id", "display_name"]);
        });
    }

    // Gates the "Edit" toolbar button below - a plain per-request permission check
    // ('ems.group.can_edit_schedule', mirroring 'hr.employee.can_edit_schedule'), false (and thus
    // absent from the record's own data) for every OTHER model reusing this widget (a student's
    // own read-only tab never defines this field at all).
    get canEditSchedule() {
        return !!this.props.record.data.can_edit_schedule;
    }

    get entries() {
        return this.props.record.data[this.props.name].records;
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
        const shift = this.props.record.data.shift;
        if (shift && SHIFT_HOURS[shift]) {
            return SHIFT_HOURS[shift];
        }
        // No shift set/derivable (e.g. a reinforcement group, or a student with no main group) —
        // fall back to auto-fitting the entries themselves, rather than guessing a window that
        // might hide real data.
        return computeBounds(
            this.entries.filter((entry) => this._hasValidDuration(entry)).map((entry) => ({ hour_from: entry.data.hour_from, hour_to: entry.data.hour_to }))
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

    entriesForDay(dayIndex) {
        return this.entries.filter((entry) => Number(entry.data.dayofweek) === dayIndex && this._hasValidDuration(entry));
    }

    // Groups a day's entries into visual blocks: entries sharing the same (hour_from, hour_to) AND
    // the same subject/non-teaching reason collapse into ONE block — co-teaching never repeats a
    // block per teacher (see the class comment above). Blocks that are still genuinely overlapping
    // after that merge (a real possibility for a student's own schedule, spanning more than one
    // group — see 'layoutOverlappingBlocks') are then laid out side by side instead of silently
    // stacking on top of each other.
    blocksForDay(dayIndex) {
        const blocks = new Map();
        for (const entry of this.entriesForDay(dayIndex)) {
            const key = `${entry.data.hour_from}_${entry.data.hour_to}_${this._blockKey(entry)}`;
            if (!blocks.has(key)) {
                blocks.set(key, { hour_from: entry.data.hour_from, hour_to: entry.data.hour_to, entries: [] });
            }
            blocks.get(key).entries.push(entry);
        }
        return layoutOverlappingBlocks([...blocks.values()]);
    }

    // 'topic' (issue #428) is part of the key too: two teachers can genuinely share the exact same
    // subject/group/slot while teaching different topics (e.g. FP Basica's MP 3161, split by
    // language) - without topic here, 'blocksForDay' would silently merge them into one block
    // showing only one of the two teachers/topics, chosen arbitrarily by entry order. Mirrors
    // '_report_color_key' on the Python side (schedule_report_mixin.py).
    _blockKey(entry) {
        return entry.data.non_teaching ? `n_${entry.data.non_teaching[0]}` : `s_${entry.data.subject_id[0]}_${entry.data.topic || ""}`;
    }

    blockStyle(block) {
        const { start } = this.bounds;
        const top = (block.hour_from - start) * PX_PER_HOUR;
        const naturalHeight = (block.hour_to - block.hour_from) * PX_PER_HOUR;
        // A break block is kept at its true, exact duration — stretching it past that would
        // visually bleed into whatever comes right after it (this schedule, unlike a single
        // teacher's, can genuinely have several simultaneous entries — electives, co-teaching —
        // right around the break, so an oversized break block is especially likely to bury one of
        // them; see also the CSS z-index rule that keeps teaching blocks on top regardless).
        const height = this.blockIsBreak(block) ? naturalHeight : Math.max(MIN_ENTRY_HEIGHT, naturalHeight);
        const color = this.blockColor(block);
        // Side-by-side split when 'layoutOverlappingBlocks' found this block genuinely overlapping
        // another one — a single/non-overlapping block keeps the CSS default (left/right:2px, full
        // width), overridden inline only when needed (mirrors schedule_grid_field.js's own
        // 'entryStyle', which does the same for its own, narrower "identical slot" case).
        const columnCount = block.columnCount || 1;
        const position = columnCount > 1
            ? `left:calc(${(100 / columnCount) * (block.column || 0)}% + 2px);width:calc(${100 / columnCount}% - 4px);right:auto;`
            : "";
        return `top:${top}px;height:${height}px;${position}${color ? `background-color:${color}` : ""}`;
    }

    blockIsBreak(block) {
        return !!block.entries[0].data.non_teaching_is_break;
    }

    // A subject gets its own colour, distinct from every other subject in this schedule — but not
    // a break, which already has its own fixed, distinctive look (see the equivalent note in
    // schedule_grid_field.js's own _colorKey).
    _colorKey(block) {
        if (this.blockIsBreak(block)) {
            return null;
        }
        return this._blockKey(block.entries[0]);
    }

    get colorByKey() {
        const items = [];
        for (const day of WEEKDAYS) {
            for (const block of this.blocksForDay(day)) {
                const key = this._colorKey(block);
                if (key) {
                    items.push({ key, dayofweek: day, hour_from: block.hour_from });
                }
            }
        }
        return buildColorMap(items);
    }

    blockColor(block) {
        const key = this._colorKey(block);
        return key ? this.colorByKey.get(key) : null;
    }

    // A break block is too short to fit a time line + a label line (see MIN_ENTRY_HEIGHT's own
    // comment in blockStyle) — time and label are shown together on one compact line instead.
    blockCompactText(block) {
        return `${this.blockTime(block)} ${this.blockLabel(block)}`;
    }

    // Never 'entry.data.name': that Char is frozen in whatever language was active when the row was
    // saved (see resource.calendar.attendance.get_report_label()'s own reasoning) — subject_id/
    // non_teaching's own labels resolve to the current UI language for free. 'topic' (issue #428)
    // is free text typed directly by the teacher, so it's appended as-is, same convention as
    // get_subject_display_label() on the Python side.
    blockLabel(block) {
        const entry = block.entries[0].data;
        if (entry.non_teaching) {
            return entry.non_teaching[1];
        }
        return entry.topic ? `${entry.subject_id[1]} - ${entry.topic}` : entry.subject_id[1];
    }

    blockRoom(block) {
        const space = block.entries[0].data.space_id;
        return space ? space[1] : "";
    }

    blockTime(block) {
        return `${formatHourMinutes(block.hour_from)}-${formatHourMinutes(block.hour_to)}`;
    }

    // Stable identity for a block - used as the read-view's own t-key and as each edit-mode
    // card's own key (see '_cardFromBlock').
    blockKey(block) {
        return `${block.hour_from}_${block.hour_to}_${this.blockLabel(block)}`;
    }

    // ── Inline edit (issue #446: topic/classroom only, from the group's own Schedule tab) ────
    // Mirrors the teacher's own card-based edit mode (schedule_grid_field.js) visually - same CSS
    // classes, same day-column layout - but purpose-built here rather than shared: unlike that
    // widget, there is no framework baseline to overlay (no blank/unassigned cards are ever
    // shown - 'blocksForDay' already only ever contains real entries), no add/remove, no
    // day/hour/subject/group editing - only 'topic' and classroom, on cards seeded straight from
    // the currently displayed blocks. Developer feedback (2026-09-12): a per-block pencil icon
    // was too fiddly to click, hard to target depending on the label's own text length - a full
    // "Edit" mode switching the day columns into cards (like the teacher's own tab already does)
    // is the familiar, easier-to-use equivalent instead.

    // Snapshotted into 'buffer' on 'startEdit()' (decoupled from the live 'entries'/'blocksForDay'
    // getters for the rest of the edit session, same reasoning as the teacher grid's own buffer) -
    // editing several cards, then a single Save/Cancel for all of them at once.
    startEdit() {
        for (const day of WEEKDAYS) {
            this.buffer[day] = this.blocksForDay(day).map((block) => this._cardFromBlock(block));
        }
        this.editing.value = true;
    }

    cancelEdit() {
        this.editing.value = false;
    }

    cardsForDay(dayIndex) {
        return this.buffer[dayIndex];
    }

    // Only a real teaching block has a 'topic'/classroom worth editing - a non-teaching entry
    // (break, guard duty, meeting) has neither and is shown fully read-only, same as every other
    // field on a teaching card except topic/classroom.
    _cardFromBlock(block) {
        const entry = block.entries[0].data;
        const editable = !this.blockIsBreak(block) && !!entry.subject_id;
        return {
            key: this.blockKey(block),
            ids: block.entries.map((blockEntry) => blockEntry.resId),
            timeLabel: this.blockTime(block),
            // The subject/non-teaching name alone, WITHOUT the topic suffix 'blockLabel' adds -
            // topic gets its own editable line right below this read-only one instead.
            subjectLabel: entry.non_teaching ? entry.non_teaching[1] : entry.subject_id[1],
            // New here (not on the teacher's own card, which has no need for it - a teacher's
            // calendar only ever has ONE teacher): which teacher(s) teach this block, since a
            // group's schedule aggregates several - lets two cards sharing the same day/time
            // (e.g. a subject split by topic) be told apart at a glance.
            teacherLabel: [...new Set(block.entries.map((blockEntry) => blockEntry.data.employee_id?.[1]).filter(Boolean))].sort().join(", "),
            editable,
            topic: entry.topic || "",
            spaceId: entry.space_id ? entry.space_id[0] : false,
        };
    }

    onCardTopicChange(dayIndex, cardKey, ev) {
        const card = this.buffer[dayIndex].find((candidate) => candidate.key === cardKey);
        if (card) {
            card.topic = ev.target.value;
        }
    }

    onCardSpaceChange(dayIndex, cardKey, ev) {
        const card = this.buffer[dayIndex].find((candidate) => candidate.key === cardKey);
        if (card) {
            card.spaceId = ev.target.value ? Number(ev.target.value) : false;
        }
    }

    // Applies to EVERY underlying 'resource.calendar.attendance' row behind each editable card
    // (more than one for a co-taught session, one per co-teacher - see 'is_co_teaching_with') so
    // both fields stay consistent across every co-teacher's own calendar, never just one of them
    // - see 'resource.calendar.attendance.update_topic_and_relocate()' for why. A room collision
    // never blocks this: it flags 'space_pending_group_sync' server-side instead of raising,
    // surfaced by the group form's own pre-existing pending-classroom banner + wizard (issue
    // #405/#444) once 'record.load()' below refreshes it - nothing more to handle here. Every
    // editable card is sent unconditionally (no dirty-tracking) - both a no-op topic write and a
    // same-room 'relocate_or_flag_pending' call are harmless server-side, and a group's own
    // schedule is small enough that this stays cheap.
    async save() {
        const editableCards = WEEKDAYS.flatMap((day) => this.buffer[day].filter((card) => card.editable));
        await Promise.all(editableCards.map((card) =>
            this.orm.call("resource.calendar.attendance", "update_topic_and_relocate", [card.ids, card.topic, card.spaceId])
        ));
        this.editing.value = false;
        await this.props.record.load();
    }

    // "Subject -> Teacher(s)" summary table, below the grid: one row per distinct (subject, topic)
    // pair in this schedule, with the sorted, de-duplicated teacher names — this is where
    // co-teaching (a group) or several teachers across different groups (a student) becomes
    // visible (more than one name in a row), instead of in the grid above. Grouping by topic too
    // (issue #428) is what separates a subject split into several distinct topics (e.g. FP
    // Basica's MP 3161) into their own rows instead of merging every teacher under one row -
    // mirrors get_subject_teachers_summary() on the Python side (schedule_report_mixin.py).
    get subjectTeachersSummary() {
        const teachersByKey = new Map();
        for (const entry of this.entries) {
            if (!entry.data.subject_id) {
                continue;
            }
            const label = entry.data.topic ? `${entry.data.subject_id[1]} - ${entry.data.topic}` : entry.data.subject_id[1];
            const key = `${entry.data.subject_id[0]}_${entry.data.topic || ""}`;
            if (!teachersByKey.has(key)) {
                teachersByKey.set(key, { subject: label, teachers: new Set() });
            }
            if (entry.data.employee_id) {
                teachersByKey.get(key).teachers.add(entry.data.employee_id[1]);
            }
        }
        return [...teachersByKey.values()]
            .sort((a, b) => a.subject.localeCompare(b.subject))
            .map(({ subject, teachers }) => ({ subject, teachers: [...teachers].sort().join(", ") }));
    }

    async onPdfClick() {
        const action = PDF_ACTION_BY_MODEL[this.props.record.resModel];
        if (!action) {
            return;
        }
        await this.actionService.doAction(action, {
            additionalContext: { active_ids: [this.props.record.resId] },
        });
    }
}

export const readonlyScheduleGridField = {
    component: ReadonlyScheduleGridField,
    supportedTypes: ["many2many"],
};

registry.category("fields").add("readonly_schedule_grid", readonlyScheduleGridField);
