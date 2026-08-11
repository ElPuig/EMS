/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { PX_PER_HOUR, DEFAULT_START, WEEKDAYS, MIN_ENTRY_HEIGHT, dayLabels, computeBounds, formatHour, formatHourMinutes, buildColorMap } from "./schedule_grid_geometry";

// 'date_from'/'date_to' are core Odoo fields on resource.calendar.attendance (not EMS-specific) -
// see working_schedule.py's own NOTE for why they're reused as-is for the "same slot, different
// subject at a different point in the year" feature, instead of adding new EMS-only fields.
// 'space_id' - exposed as its own explicit per-card field since the 2026-08-11 card-based edit mode
// redesign (previously only ever inferred server-side, never shown/editable in this widget at all).
const ATTENDANCE_FIELDS = ["dayofweek", "hour_from", "hour_to", "non_teaching", "subject_id", "group_ids", "date_from", "date_to", "space_id"];

// Two different layouts for two different jobs:
//   - VIEW mode (read-only): a visual weekly grid (day columns x hourly rows), entries positioned
//     absolutely by their exact hour_from/hour_to (dayofweek/hour_from/hour_to are a recurring
//     pattern, not real dates, so the native <calendar> view does not apply). UNCHANGED by the
//     2026-08-11 card redesign below - only edit mode's own layout changed.
//   - EDIT mode (entered via "Edit"/"New"): a per-weekday list of independent CARDS (2026-08-11
//     redesign, replacing an earlier "shared period row across all 5 days" grid) - each card is its
//     own self-contained block (own time, own optional date range, own subject/group-or-non-teaching
//     reason, own room), added/removed individually per day via "+ Add"/a card's own "×". Chosen over
//     the previous shared-row model specifically because a date-scoped block (see "Mid-course subject
//     handoff" below) only ever applies to ONE weekday at a time, so forcing it into a row shared
//     across all 5 days read as confusing and cramped in practice (developer feedback, 2026-08-11) -
//     no drag-and-drop between days either, deliberately (remove + re-add covers it, and the added
//     complexity wasn't judged worth it). Nothing is written to the server until "Save" is pressed;
//     "Cancel" discards the whole in-progress buffer (mirrors the grade matrix widget's own pattern).
// Three actions can start an edit session:
//   - "Edit": edit the teacher's current schedule in place.
//   - "Import": opens the XML planner importer already scoped to this teacher (no email lookup needed).
//   - "New": seed the buffer from either a blank schedule framework (a level's period times, still
//     unassigned) or another teacher's current schedule (handy for substitutions) — replacing the whole
//     buffer, but only written to the server on "Save".
// Unassigned slots are NEVER stored as real attendance rows — only what the teacher actually teaches
// (or a real non-teaching commitment, e.g. patio/meeting) gets written. So the blank/unassigned cards
// shown while editing come from TWO merged sources, same as before the card redesign: the calendar's
// reference framework ('source_framework_id', fetched live every time — its periods, including its own
// patio/meeting rows, seed each day's card list as a baseline - kept deliberately, see
// '_seedBufferFromEntries', developer's own call: "eso hará más fácil mostrar los patios en el modo
// edición") and the teacher's own real saved entries (which always win over that baseline for the same
// day+slot, and can add entirely new cards the framework never had). Saving always writes the exact
// (possibly non-hour-aligned) hour_from/hour_to of each real card, never a rounded one, and records
// which framework was used so the next "Edit" keeps showing the right gaps.
export class ScheduleGridField extends Component {
    static template = "ems.ScheduleGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.editing = useState({ value: false });
        // Keyed by weekday index (see WEEKDAYS) - each value is an array of card objects, sorted by
        // (hourFrom, hourTo, startDate) - see '_sortCards'. No more shared "period" concept across
        // days (2026-08-11 card redesign) - each card is independent.
        this.buffer = useState({ 0: [], 1: [], 2: [], 3: [], 4: [] });
        this.dirty = useState({ value: false });
        this._nextCardId = 1;
        this._pendingSourceFrameworkId = false;
        this.newPanel = useState({ open: false, value: "", frameworks: [], teachers: [] });
        this.catalog = useState({ subjects: [], groups: [], nonTeaching: [], spaces: [] });
        this.summary = useState({ teaching: { rows: [], total: 0 }, fixed: { rows: [], total: 0 }, total: 0 });
        this.derivedBreaks = useState({ list: [] });
        // Reference catalogs never depend on which employee record is being viewed - loaded once,
        // not tied to record identity.
        onWillStart(async () => {
            const [subjects, groups, nonTeachingTypes, spaces] = await Promise.all([
                this.orm.searchRead("ems.subject", [], ["id", "display_name"]),
                this.orm.searchRead("ems.group", [], ["id", "display_name"]),
                this.orm.searchRead("ems.non_teaching_type", [], ["id", "name"]),
                this.orm.searchRead("ems.space", [], ["id", "display_name"]),
            ]);
            this.catalog.subjects = subjects;
            this.catalog.groups = groups;
            this.catalog.nonTeaching = nonTeachingTypes.map((item) => [item.id, item.name]);
            this.catalog.spaces = spaces;
        });
        // Reloads on mount AND whenever the underlying employee record actually changes - not
        // just once on mount ('onWillStart' alone would not do this). The form view can reuse
        // this exact same component instance across a pager/breadcrumb navigation to a DIFFERENT
        // employee (Odoo's own web client optimization, no remount) - a mount-only load left
        // these two showing the PREVIOUSLY viewed teacher's own hours summary/derived breaks on a
        // newly navigated-to one, until an actual full page reload (found 2026-08-11: reported as
        // wrong breaks/hours shown while paging between several real teachers). Passes its own
        // 'record' argument through explicitly rather than letting the two methods fall back to
        // reading 'this.props.record' - 'useRecordObserver's callback can fire before OWL has
        // actually reassigned 'this.props' to the new record, so reading 'this.props' at that
        // exact moment could still return the PREVIOUS employee (confirmed the hard way: an
        // earlier version of this fix that ignored the callback's own 'record' argument still
        // fetched the previous teacher's own data on the very first RPC after paging).
        useRecordObserver(async (record) => {
            await Promise.all([this._loadSummary(record), this._loadDerivedBreaks(record)]);
        });
    }

    // Weekly hours summary table (below the grid, view mode only) — always reflects the last SAVED
    // schedule, never the in-progress edit buffer (see the class comment on 'apply_schedule_changes'
    // for why unsaved state shouldn't drive server-computed aggregates). 'record' defaults to the
    // component's own current props for callers outside the record-change hook above (e.g. 'save()'),
    // where 'this.props.record' is already guaranteed up to date.
    async _loadSummary(record = this.props.record) {
        const value = record.data.resource_calendar_id;
        const calendarId = value ? value[0] : false;
        if (!calendarId) {
            return;
        }
        const result = await this.orm.call("resource.calendar", "get_schedule_hours_summary", [[calendarId]]);
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
    // expect from a real x2many record's own data. See '_loadSummary' above for why 'record' is a
    // parameter, not read off 'this.props' directly.
    async _loadDerivedBreaks(record = this.props.record) {
        if (!record.resId) {
            return;
        }
        const rows = await this.orm.call("hr.employee", "get_derived_break_attendance_data", [[record.resId]]);
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
        const combined = [...real, ...derived];
        // Two entries can legitimately share the exact same hour_from/hour_to now (see plans/
        // calendar_driven_attendance_templates.md's "Mid-course subject handoff" refinement - e.g. a
        // regular module until February, the end-of-course project from March, same weekday/time) -
        // render them side by side instead of one silently hiding the other underneath it.
        const bySlot = new Map();
        for (const entry of combined) {
            const key = `${entry.data.hour_from}_${entry.data.hour_to}`;
            if (!bySlot.has(key)) {
                bySlot.set(key, []);
            }
            bySlot.get(key).push(entry);
        }
        for (const group of bySlot.values()) {
            group.forEach((entry, index) => {
                entry.gridColumn = index;
                entry.gridColumnCount = group.length;
            });
        }
        return combined;
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
        // Side-by-side split when this slot has more than one entry (see 'entriesForDay') - a single
        // entry keeps the CSS default (left/right:2px, full width), overridden inline only when needed.
        const columnCount = entry.gridColumnCount || 1;
        const position = columnCount > 1
            ? `left:calc(${(100 / columnCount) * (entry.gridColumn || 0)}% + 2px);width:calc(${100 / columnCount}% - 4px);right:auto;`
            : "";
        return `top:${top}px;height:${height}px;${position}${color ? `background-color:${color}` : ""}`;
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

    // ── Edit mode (independent per-day cards, see class comment) ─────────────

    _timeToHour(value) {
        const [h, m] = value.split(":").map(Number);
        return h + m / 60;
    }

    hourToTimeInput(value) {
        const hour = Math.floor(value);
        const minutes = Math.round((value - hour) * 60);
        return `${String(hour).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
    }

    cardsForDay(dayIndex) {
        return this.buffer[dayIndex];
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
            spaceId: data.space_id ? data.space_id[0] : false,
            // "YYYY-MM-DD" string or false - each card's own date range (2026-08-11 card redesign;
            // previously carried on a shared "period" row). Reads core Odoo's own 'date_from'/
            // 'date_to' (not EMS-specific fields).
            startDate: data.date_from || false,
            endDate: data.date_to || false,
        };
    }

    // A card with no subject/non-teaching is 'blank' (still-unassigned) — shown so the admin can
    // fill it in, but never written on save (see the class comment).
    _kindFromNormalized(n) {
        if (n.non_teaching) {
            return { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: n.non_teaching };
        }
        if (n.subjectId) {
            return { kind: "subject", subjectId: n.subjectId, groupId: n.groupId, nonTeaching: false };
        }
        return { kind: "blank", subjectId: false, groupId: false, nonTeaching: false };
    }

    _cardFromNormalized(n) {
        return { id: this._nextCardId++, hourFrom: n.hour_from, hourTo: n.hour_to, startDate: n.startDate, endDate: n.endDate, spaceId: n.spaceId, ...this._kindFromNormalized(n) };
    }

    _blankCard(hourFrom, hourTo) {
        return { id: this._nextCardId++, hourFrom, hourTo, startDate: false, endDate: false, spaceId: false, kind: "blank", subjectId: false, groupId: false, nonTeaching: false };
    }

    // Cards within a day sort by start time, then end time, then start date - the developer's own
    // spec ("se ordenan por hora de inicio y hora de final, si dos se hacen a la misma hora, sale
    // una seguida de la otra (el orden es por fecha)").
    _sortCards(cards) {
        cards.sort((a, b) => a.hourFrom - b.hourFrom || a.hourTo - b.hourTo || (a.startDate || "").localeCompare(b.startDate || ""));
    }

    // Rebuilds the whole buffer (independent cards per weekday) by merging a baseline (a reference
    // framework's own slots — some blank, some real non-teaching commitments like patio/meetings)
    // with the teacher's real saved entries, which always win for the same day+slot. A baseline slot
    // matched by MORE THAN ONE real entry (a date-split pair sharing the exact same hour_from/hour_to)
    // becomes one card PER real entry, each keeping its own date range - that's what lets a single
    // framework slot expand into two cards mid-course. A real entry at a slot the baseline never had
    // (e.g. a custom "+ Add" card from a previous save) is appended as its own new card.
    _seedBufferFromEntries(baselineEntries, realEntries = []) {
        const baseline = baselineEntries.map((raw) => this._normalizeEntry(raw)).filter((n) => WEEKDAYS.includes(n.dayofweek));
        const real = realEntries.map((raw) => this._normalizeEntry(raw)).filter((n) => WEEKDAYS.includes(n.dayofweek));

        this._nextCardId = 1;
        const slotKey = (n) => `${n.dayofweek}_${n.hour_from}_${n.hour_to}`;
        const realBySlot = new Map();
        for (const n of real) {
            const key = slotKey(n);
            if (!realBySlot.has(key)) {
                realBySlot.set(key, []);
            }
            realBySlot.get(key).push(n);
        }

        const buffer = { 0: [], 1: [], 2: [], 3: [], 4: [] };
        const usedSlots = new Set();
        for (const n of baseline) {
            const key = slotKey(n);
            usedSlots.add(key);
            const matches = realBySlot.get(key);
            if (matches && matches.length) {
                for (const match of matches) {
                    buffer[n.dayofweek].push(this._cardFromNormalized(match));
                }
            } else {
                buffer[n.dayofweek].push(this._blankCard(n.hour_from, n.hour_to));
            }
        }
        for (const [key, matches] of realBySlot.entries()) {
            if (usedSlots.has(key)) {
                continue;
            }
            for (const match of matches) {
                buffer[match.dayofweek].push(this._cardFromNormalized(match));
            }
        }

        for (const dayIndex of WEEKDAYS) {
            this._sortCards(buffer[dayIndex]);
        }
        for (const dayIndex of WEEKDAYS) {
            this.buffer[dayIndex] = buffer[dayIndex];
        }
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

    // Lets the admin add a card the loaded source didn't have (e.g. mixing two levels' bell
    // schedules by hand, or the "same time, different point in the year" case - a second card at an
    // existing card's exact time, scoped to a different, non-overlapping date range - see the class
    // comment's "Mid-course subject handoff").
    addCard(dayIndex) {
        const cards = this.buffer[dayIndex];
        const last = cards[cards.length - 1];
        const hourFrom = last ? last.hourTo : DEFAULT_START;
        cards.push(this._blankCard(hourFrom, hourFrom + 1));
        this._sortCards(cards);
        this.dirty.value = true;
    }

    removeCard(dayIndex, cardId) {
        const cards = this.buffer[dayIndex];
        const index = cards.findIndex((card) => card.id === cardId);
        if (index !== -1) {
            cards.splice(index, 1);
        }
        this.dirty.value = true;
    }

    _findCard(dayIndex, cardId) {
        return this.buffer[dayIndex].find((card) => card.id === cardId);
    }

    onCardSubjectChange(dayIndex, cardId, ev) {
        const card = this._findCard(dayIndex, cardId);
        if (!card) {
            return;
        }
        const value = ev.target.value;
        if (value.startsWith("n_")) {
            Object.assign(card, { kind: "non_teaching", subjectId: false, groupId: false, nonTeaching: Number(value.slice(2)) });
        } else if (value.startsWith("s_")) {
            Object.assign(card, { kind: "subject", subjectId: Number(value.slice(2)), nonTeaching: false });
        } else {
            Object.assign(card, { kind: "blank", subjectId: false, groupId: false, nonTeaching: false });
        }
        this.dirty.value = true;
    }

    onCardGroupChange(dayIndex, cardId, ev) {
        const card = this._findCard(dayIndex, cardId);
        if (!card) {
            return;
        }
        card.groupId = ev.target.value ? Number(ev.target.value) : false;
        this.dirty.value = true;
    }

    onCardSpaceChange(dayIndex, cardId, ev) {
        const card = this._findCard(dayIndex, cardId);
        if (!card) {
            return;
        }
        card.spaceId = ev.target.value ? Number(ev.target.value) : false;
        this.dirty.value = true;
    }

    // "hourFrom"/"hourTo" as the 'field' argument (matching the card's own property names, unlike
    // the old shared-period model's raw 'hour_from'/'hour_to').
    onCardTimeChange(dayIndex, cardId, field, ev) {
        const card = this._findCard(dayIndex, cardId);
        if (!card) {
            return;
        }
        const value = this._timeToHour(ev.target.value);
        if (field === "hourFrom") {
            // Moving the start moves the whole card, keeping its original duration — otherwise
            // dragging the start later/earlier while the end stays put can silently balloon the card
            // into one spanning most of the day.
            const duration = card.hourTo - card.hourFrom;
            card.hourFrom = value;
            card.hourTo = value + duration;
        } else {
            card.hourTo = value;
        }
        this._sortCards(this.buffer[dayIndex]);
        this.dirty.value = true;
    }

    // Blank means "valid all course year", unchanged default behavior. ev.target.value is ""
    // (cleared) or "YYYY-MM-DD" (native <input type="date">).
    onCardDateChange(dayIndex, cardId, field, ev) {
        const card = this._findCard(dayIndex, cardId);
        if (!card) {
            return;
        }
        card[field] = ev.target.value || false;
        if (field === "startDate") {
            this._sortCards(this.buffer[dayIndex]);
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

    subjectSelectValue(card) {
        if (card.kind === "non_teaching") {
            return `n_${card.nonTeaching}`;
        }
        if (card.kind === "subject") {
            return `s_${card.subjectId}`;
        }
        return ""; // 'blank' shows as "—" until the admin picks something
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
            for (const card of this.buffer[dayIndex]) {
                // Blank/unassigned cards are never written — only a real subject or non-teaching
                // commitment is (see the class comment).
                if (card.kind === "blank") {
                    continue;
                }
                const cell = {
                    dayofweek: String(dayIndex),
                    hour_from: card.hourFrom,
                    hour_to: card.hourTo,
                    day_period: card.hourFrom < 13 ? "morning" : "afternoon",
                };
                // Blank (the common case) means "valid all course year" - only send an explicit date
                // when the admin actually set one. Core Odoo's own 'date_from'/'date_to' field names
                // (not EMS-specific).
                if (card.startDate) {
                    cell.date_from = card.startDate;
                }
                if (card.endDate) {
                    cell.date_to = card.endDate;
                }
                // Only sent when the admin explicitly picked a room on this card - otherwise the
                // server keeps auto-deriving it from the group's own default (see
                // ems_working_schedule_assignation.create()), unchanged behavior.
                if (card.spaceId) {
                    cell.space_id = card.spaceId;
                }
                if (card.kind === "subject" && card.subjectId && card.groupId) {
                    cell.subject_id = card.subjectId;
                    cell.group_ids = [card.groupId];
                    cell.name = `${subjectById.get(card.subjectId)}: ${groupById.get(card.groupId)}`;
                } else if (card.kind === "non_teaching") {
                    cell.non_teaching = card.nonTeaching;
                    cell.name = nonTeachingById.get(card.nonTeaching) || card.nonTeaching;
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
