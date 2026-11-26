/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { serverNow, syncServerClock } from "./server_clock";

// One pixel height per hour of the grid, and the step a time snaps to (a quarter of an hour).
const HOUR_PX = 40;
const STEP = 0.25;
const ISO_DAY = 24 * 3600 * 1000;
// How often the current-time line moves down the grid: once a minute, its own resolution.
const NOW_REFRESH_MS = 60 * 1000;

// The week of a space as a grid (space reservation wizard, issue #475): the days as columns, the
// hours as rows, what holds the space drawn over it (classes and duties of the weekly schedule,
// reservations) and the free time left blank. Dragging over a free time (or clicking it, for an
// hour) fills the wizard's day, start and end; a time already held, or a day gone by, cannot be
// chosen. A dotted red line marks the current time in today's column: what lies above it is the
// past, shaded, and cannot be chosen either. The server decides what holds the space (ems.space_reservation_wizard.get_occupation_week):
// the grid only draws it. It is hosted by a boolean field, whose value tells whether to show it.
// Not Odoo's calendar view: it shows the records of one model in a view of its own, while this week
// mixes recurring schedule blocks (not dated records) with reservations and lives inside the wizard,
// filling its slot fields.
export class EmsSpaceWeekGridField extends Component {
    static template = "ems.SpaceWeekGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, monday: null, weekend: false, drag: null, now: null });
        // The company's "now" comes from the server's clock, never the computer's (see server_clock.js).
        onWillStart(async () => {
            await syncServerClock(this.orm);
            this.state.now = serverNow();
        });
        onMounted(() => {
            this.nowTimer = setInterval(() => (this.state.now = serverNow()), NOW_REFRESH_MS);
        });
        this.onMove = (ev) => this.dragTo(ev);
        this.onUp = () => this.dragEnd();
        useEffect(
            (spaceId, monday) => {
                if (spaceId) {
                    this.load(spaceId, monday);
                }
            },
            () => [this.spaceId, this.state.monday]
        );
        onWillUnmount(() => {
            clearInterval(this.nowTimer);
            this.removeListeners();
        });
    }

    get spaceId() {
        const space = this.props.record.data.space_id;
        return space && space[0];
    }

    async load(spaceId, monday) {
        const data = await this.orm.call("ems.space_reservation_wizard", "get_occupation_week", [spaceId, monday]);
        // A slow answer for a week or a space that was left already is not what is shown.
        if (spaceId === this.spaceId && monday === this.state.monday) {
            this.state.data = data;
        }
    }

    get days() {
        const days = this.state.data ? this.state.data.days : [];
        const today = this.state.now.toISODate();
        return days.map((day, index) => ({ ...day, index, past: day.date < today, today: day.date === today }))
            .filter((day) => this.state.weekend || day.index < 5);
    }

    /** The current time as an hour of the day (a float). */
    get nowHour() {
        return this.state.now.hour + this.state.now.minute / 60;
    }

    /** Today's column: how much of it is gone by (the shaded past) and where the line goes, if inside the grid. */
    nowBox(day) {
        const { hour_from: from, hour_to: to } = this.state.data;
        const elapsedTo = Math.min(Math.max(this.nowHour, from), to);
        const line = this.nowHour >= from && this.nowHour <= to;
        return { elapsed: this.box(from, elapsedTo), line: line ? `top: ${(this.nowHour - from) * HOUR_PX}px;` : null };
    }

    /** Whether the time asked for has already gone by (a day before today, or earlier today). */
    isGone(day, start) {
        return day.past || (day.today && start < this.nowHour);
    }

    get hours() {
        const { hour_from, hour_to } = this.state.data;
        return Array.from({ length: hour_to - hour_from }, (_, offset) => hour_from + offset);
    }

    get bodyHeight() {
        return (this.state.data.hour_to - this.state.data.hour_from) * HOUR_PX;
    }

    get weekLabel() {
        const days = this.state.data.days;
        return `${days[0].label} - ${days[6].label}`;
    }

    box(start, end) {
        const from = this.state.data.hour_from;
        return `top: ${(start - from) * HOUR_PX}px; height: ${(end - start) * HOUR_PX}px;`;
    }

    blocks(day) {
        return this.state.data.blocks.filter((block) => block.day === day.index);
    }

    /** The slot chosen in the wizard, when it falls in this day. */
    chosen(day) {
        const { space_day: date, space_start: start, space_end: end } = this.props.record.data;
        if (!date || date.toISODate() !== day.date) {
            return null;
        }
        return { start, end };
    }

    moveWeek(weeks) {
        const monday = new Date(Date.parse(this.state.data.monday) + weeks * 7 * ISO_DAY);
        this.state.monday = monday.toISOString().slice(0, 10);
        this.state.data = null;
    }

    goToday() {
        this.state.monday = null;
        this.state.data = null;
    }

    toggleWeekend(ev) {
        this.state.weekend = ev.target.checked;
    }

    timeAt(ev, column) {
        const rect = column.getBoundingClientRect();
        const hours = (ev.clientY - rect.top) / HOUR_PX + this.state.data.hour_from;
        const snapped = Math.round(hours / STEP) * STEP;
        return Math.min(Math.max(snapped, this.state.data.hour_from), this.state.data.hour_to);
    }

    dragStart(ev, day) {
        if (day.past || ev.button !== 0) {
            return;
        }
        ev.preventDefault();
        const column = ev.currentTarget;
        const start = Math.min(this.timeAt(ev, column), this.state.data.hour_to - STEP);
        if (this.isGone(day, start)) {
            return;
        }
        this.state.drag = { day, column, anchor: start, start, end: start + STEP };
        document.addEventListener("mousemove", this.onMove);
        document.addEventListener("mouseup", this.onUp);
    }

    dragTo(ev) {
        const drag = this.state.drag;
        if (!drag) {
            return;
        }
        const time = this.timeAt(ev, drag.column);
        drag.start = Math.min(drag.anchor, time);
        drag.end = Math.max(drag.anchor + STEP, time);
    }

    dragEnd() {
        const drag = this.state.drag;
        this.removeListeners();
        this.state.drag = null;
        if (!drag) {
            return;
        }
        let { start, end } = drag;
        if (end - start <= STEP) {
            // A click: an hour from where it was made.
            end = Math.min(start + 1, this.state.data.hour_to);
        }
        if (this.isHeld(drag.day, start, end) || this.isGone(drag.day, start)) {
            return;
        }
        this.props.record.update({
            space_day: luxon.DateTime.fromISO(drag.day.date),
            space_start: start,
            space_end: end,
        });
    }

    isHeld(day, start, end) {
        return this.blocks(day).some((block) => block.start < end && block.end > start);
    }

    /** Whether the slot being dragged takes a time that is held (it is drawn as not allowed). */
    get dragHeld() {
        const drag = this.state.drag;
        return Boolean(drag) && this.isHeld(drag.day, drag.start, drag.end);
    }

    removeListeners() {
        document.removeEventListener("mousemove", this.onMove);
        document.removeEventListener("mouseup", this.onUp);
    }
}

export const emsSpaceWeekGridField = {
    component: EmsSpaceWeekGridField,
    displayName: "Week of a space",
    supportedTypes: ["boolean"],
};

registry.category("fields").add("ems_space_week_grid", emsSpaceWeekGridField);
