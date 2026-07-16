/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

// Pure display/geometry helpers shared by every weekly schedule grid widget (the teacher's
// editable 'schedule_grid' and the read-only group 'group_schedule_grid') — day/hour layout math
// with no OWL state of its own, so it's a plain module rather than a shared component: the two
// widgets' interactive surface (an edit buffer vs. none) differs enough that forcing them through
// one component would leave a lot of dead code active in the read-only case.

export const PX_PER_HOUR = 64;
export const DEFAULT_START = 8;
export const DEFAULT_END = 20;
export const WEEKDAYS = [0, 1, 2, 3, 4];
// A short period (e.g. a 20-30min patio break) still needs room for a wrapped subject/reason
// label plus its time and room lines without visually spilling into the next period below it.
export const MIN_ENTRY_HEIGHT = 44;

export function dayLabels() {
    return [_t("Monday"), _t("Tuesday"), _t("Wednesday"), _t("Thursday"), _t("Friday")];
}

// 'hourPairs' is any iterable of {hour_from, hour_to} — callers pass their own entries so this
// stays free of any dependency on how those entries are stored (plain records, grouped blocks...).
// Fits tightly to whatever hours are actually present (an afternoon-only teacher, 14h-22h, sees
// exactly that — not a wider range padded out to a generic default) — DEFAULT_START/DEFAULT_END
// only apply as a fallback canvas when there's nothing to fit yet (an empty/new schedule).
export function computeBounds(hourPairs) {
    let start = null;
    let end = null;
    for (const { hour_from, hour_to } of hourPairs) {
        start = start === null ? Math.floor(hour_from) : Math.min(start, Math.floor(hour_from));
        end = end === null ? Math.ceil(hour_to) : Math.max(end, Math.ceil(hour_to));
    }
    return { start: start ?? DEFAULT_START, end: end ?? DEFAULT_END };
}

export function formatHour(hour) {
    return `${String(hour).padStart(2, "0")}:00`;
}

export function formatHourMinutes(value) {
    const hour = Math.floor(value);
    const minutes = Math.round((value - hour) * 60);
    return `${String(hour).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

// Mirrors ems.schedule_report_mixin.REPORT_COLOR_PALETTE on the Python side (kept in sync by
// hand — different languages can't literally share one constant) — so a subject/activity tends
// to land on the same colour in the widget as it does in the PDF.
export const REPORT_COLOR_PALETTE = [
    "#5b8def", "#f4a261", "#2a9d8f", "#e76f51", "#8ecae6", "#ffb703",
    "#c77dff", "#06d6a0", "#ef476f", "#118ab2", "#bc6c25", "#9d4edd",
];

// Assigns each distinct 'key' its own colour, reused every time that key reappears, in
// first-seen (day, hour) order — the same "same subject/activity always gets the same colour"
// rule the PDF's own REPORT_COLOR_PALETTE/_report_color_key already follows. Only distinguishes
// colours *within* the entries actually passed in (a schedule's own subjects/activities), not
// across every subject that exists — there's no reason to reserve a colour for one this
// particular schedule never uses. 'items' is [{key, dayofweek, hour_from}, ...]; returns a
// Map<key, hexColor>.
export function buildColorMap(items) {
    const sorted = [...items].sort((a, b) => a.dayofweek - b.dayofweek || a.hour_from - b.hour_from);
    const colorByKey = new Map();
    for (const item of sorted) {
        if (!colorByKey.has(item.key)) {
            colorByKey.set(item.key, REPORT_COLOR_PALETTE[colorByKey.size % REPORT_COLOR_PALETTE.length]);
        }
    }
    return colorByKey;
}
