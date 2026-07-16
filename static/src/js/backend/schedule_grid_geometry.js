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
