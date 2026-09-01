/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { dayLabels } from "./schedule_grid_geometry";

const SHIFTS = [
    { key: "morning", label: _t("Morning") },
    { key: "afternoon", label: _t("Afternoon") },
];

// Mirrors ems.course's own SHIFT_HOURS (models/attendance/guard_duty_board.py): the afternoon
// shift starts at 15:00, kept in sync by hand since a plain JS constant can't share the Python
// one directly.
const AFTERNOON_START_HOUR = 15;

// Defaults the board to whichever day/shift the viewer would actually want to see right now
// (developer feedback, 2026-09-01: "hoy es martes... como ya son las 15h, pues el turno de
// tarde") — the browser's own local clock, since "now" here means the viewer's own wall-clock
// time, not the server's. Date.getDay() is 0=Sunday..6=Saturday; our own day index is 0=Monday.
// ..4=Friday, so a weekend falls outside that range - Monday is as reasonable a fallback as any
// (the board has no "weekend" concept at all, every table is keyed to a Mon-Fri dayofweek).
function getDefaultDayAndShift() {
    const now = new Date();
    const jsDay = now.getDay();
    const day = jsDay >= 1 && jsDay <= 5 ? jsDay - 1 : 0;
    const shift = now.getHours() >= AFTERNOON_START_HOUR ? "afternoon" : "morning";
    return { day, shift };
}

// Read-only, centre-wide board: one weekday visible at a time (tabs), morning/afternoon are
// different shifts (never merged into one table — see ems.group.shift) picked via a dropdown
// within the active day, not shown stacked together — columns are the groups actually taught in
// that shift, rows are time blocks, plus the guard-duty teacher(s) for each block. A guard slot
// has no group of its own (see resource.calendar.attendance.group_ids' own NOTE on non-teaching
// rows), so guards are reported per-row instead of as one more column.
//
// A plain ir.actions.client (registered below), not a form view on a wizard record — see
// models/attendance/guard_duty_board.py's own class docstring for why: a wizard record's URL
// would show a raw "model/id" instead of a proper "action-<xmlid>" like every other EMS screen.
//
// Data is fetched via RPC, one weekday/shift at a time (ems.course.get_guard_duty_board_data()) —
// not read from any field's own prefetched sub-records, unlike the teacher/group grids
// (schedule_grid_field.js/group_schedule_grid_field.js). Those aggregate at most one teacher's or
// one group's own schedule; this one aggregates the whole centre (easily several hundred rows),
// which the web client's own x2many sub-record fetch silently caps — an earlier version that did
// read a prefetched field this way only ever showed real data for whichever weekday loaded first.
export class GuardDutyBoard extends Component {
    static template = "ems.GuardDutyBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        const { day, shift } = getDefaultDayAndShift();
        this.state = useState({
            activeDay: day,
            activeShift: shift,
            board: null,
            loading: true,
            courseId: null,
            courseName: "",
        });
        onWillStart(async () => {
            const course = await this.orm.call("ems.course", "get_current_course_data", []);
            this.state.courseId = course.id;
            this.state.courseName = course.name;
            await this.loadBoard();
        });
    }

    get days() {
        return dayLabels().map((label, index) => ({ index, label }));
    }

    get shifts() {
        return SHIFTS;
    }

    async setActiveDay(index) {
        if (index === this.state.activeDay) {
            return;
        }
        this.state.activeDay = index;
        await this.loadBoard();
    }

    async onShiftChange(ev) {
        const key = ev.target.value;
        if (key === this.state.activeShift) {
            return;
        }
        this.state.activeShift = key;
        await this.loadBoard();
    }

    async loadBoard() {
        this.state.loading = true;
        this.state.board = await this.orm.call(
            "ems.course",
            "get_guard_duty_board_data",
            [String(this.state.activeDay), this.state.activeShift]
        );
        this.state.loading = false;
    }

    // One PDF per day AND per shift — whichever day tab / shift dropdown is currently active,
    // not the whole week or both shifts — see reports/attendance/report_guard_duty_board.xml's
    // own use of the 'guard_duty_weekday'/'guard_duty_shift' context keys.
    async onPdfClick() {
        await this.actionService.doAction("ems.action_report_guard_duty_board", {
            additionalContext: {
                active_ids: [this.state.courseId],
                guard_duty_weekday: String(this.state.activeDay),
                guard_duty_shift: this.state.activeShift,
            },
        });
    }
}

registry.category("actions").add("ems_guard_duty_board", GuardDutyBoard);
