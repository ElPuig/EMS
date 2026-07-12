/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

const PX_PER_HOUR = 48;
const DEFAULT_START = 8;
const DEFAULT_END = 20;

function dayLabels() {
    return [_t("Monday"), _t("Tuesday"), _t("Wednesday"), _t("Thursday"), _t("Friday")];
}

// Visual weekly grid (day columns x hour rows) for a resource.calendar's weekly attendance slots
// (dayofweek/hour_from/hour_to — a recurring pattern, not real dates, so the native <calendar> view
// does not apply). There is no local edit buffer here, unlike the grade matrix widget: each slot is a
// real resource.calendar.attendance record, opened/created/removed through the standard Odoo form
// dialog (FormViewDialog), then the field is reloaded from the server — the dialog's own form is the
// single source of truth for validation (overlaps, required fields, etc.).
export class ScheduleGridField extends Component {
    static template = "ems.ScheduleGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.state = useState({});
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

    entriesForDay(dayIndex) {
        return this.entries.filter((entry) => Number(entry.data.dayofweek) === dayIndex);
    }

    entryStyle(entry) {
        const { start } = this.bounds;
        const top = (entry.data.hour_from - start) * PX_PER_HOUR;
        const height = Math.max(20, (entry.data.hour_to - entry.data.hour_from) * PX_PER_HOUR);
        return `top:${top}px;height:${height}px`;
    }

    entryLabel(entry) {
        return entry.data.name || "";
    }

    formatHour(hour) {
        return `${String(hour).padStart(2, "0")}:00`;
    }

    onEntryClick(entry, ev) {
        ev.stopPropagation();
        this.openEntry(entry.resId);
    }

    openEntry(entryId) {
        if (this.props.readonly) {
            return;
        }
        this.dialog.add(FormViewDialog, {
            resModel: "resource.calendar.attendance",
            resId: entryId,
            title: _t("Working time"),
            onRecordSaved: () => this.props.record.load(),
            removeRecord: async () => {
                await this.orm.unlink("resource.calendar.attendance", [entryId]);
                await this.props.record.load();
            },
        });
    }

    addEntry(dayIndex, hourFrom) {
        if (this.props.readonly || !this.calendarId) {
            return;
        }
        this.dialog.add(FormViewDialog, {
            resModel: "resource.calendar.attendance",
            resId: false,
            title: _t("Working time"),
            context: {
                default_calendar_id: this.calendarId,
                default_dayofweek: String(dayIndex),
                default_hour_from: hourFrom,
                default_hour_to: hourFrom + 1,
                default_day_period: hourFrom < 13 ? "morning" : "afternoon",
            },
            onRecordSaved: () => this.props.record.load(),
        });
    }

    onColumnClick(dayIndex, ev) {
        const { start } = this.bounds;
        const hour = start + Math.round(((ev.offsetY / PX_PER_HOUR) * 2)) / 2;
        this.addEntry(dayIndex, hour);
    }
}

export const scheduleGridField = {
    component: ScheduleGridField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("schedule_grid", scheduleGridField);
