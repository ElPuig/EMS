/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { _t } from "@web/core/l10n/translation";
import { formatList } from "@web/core/l10n/utils";
import { dayLabels } from "./schedule_grid_geometry";
import { serverNow, syncServerClock } from "./server_clock";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { GuardChangeProposalDialog } from "./guard_change_proposal_dialog";
import { GuardCoverDialog } from "./guard_cover_dialog";
import { GuardSupportDialog } from "./guard_support_dialog";
import { GuardUncheckedDialog } from "./guard_unchecked_dialog";
import { GuardArrangementPlan, fullPlanSelection, selectedPlanSteps, toggledPlanSelection } from "./guard_arrangement_plan";

// The reason a struck-out line needs no guard, opened by clicking its info icon - the same text
// its tooltip shows on hover, for whoever doesn't hover (or uses a touchscreen).
class GuardBoardReasonPopover extends Component {
    static template = "ems.GuardBoardReasonPopover";
    static props = {
        reason: String,
        // A line struck out because a guard was sent stays editable by whoever organises the
        // absence: the popover then also offers to change or remove that guard.
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
        close: Function,
    };

    onAction() {
        this.props.close();
        this.props.onAction();
    }
}

const SHIFTS = [
    { key: "morning", label: _t("Morning") },
    { key: "afternoon", label: _t("Afternoon") },
];

// The two ways of reading the same day: the timetable everyone already knows, with whoever is
// away struck through it, and the plain "who is missing / who is on guard" list built from the
// very same payload (see ems.course.get_guard_duty_board_data) - one fetch, two renderings.
// The absences table comes first and opens by default: it is the one the centre works from day to
// day (developer feedback, 2026-10-07).
const VIEWS = [
    { key: "table", label: _t("Absences table") },
    { key: "schedule", label: _t("Guard duty schedule") },
];

// How often the current-time line moves down the grid: once a minute, its own resolution.
const NOW_LINE_REFRESH_MS = 60 * 1000;
// Issue #692: the bus channel and notification the server sends when a day of the board changes
// (see models/shared/guard_board_notifier.py), and how long to wait for the rest of a burst.
const GUARD_BOARD_CHANNEL = "ems.guard_duty_board";
const GUARD_BOARD_CHANGED = "ems.guard_duty_board/changed";
const REFRESH_DEBOUNCE_MS = 500;

// Mirrors ems.course's own SHIFT_HOURS (models/attendance/guard_duty_board.py): the afternoon
// shift starts at 15:00, kept in sync by hand since a plain JS constant can't share the Python
// one directly.
const AFTERNOON_START_HOUR = 15;

// Defaults the board to whichever day/shift the viewer would actually want to see right now
// (developer feedback, 2026-09-01: "hoy es martes... como ya son las 15h, pues el turno de
// tarde") — the server's clock in the company's timezone, never the computer's (see
// server_clock.js). luxon's weekday is 1=Monday..7=Sunday; our own day index is 0=Monday..4=Friday,
// so a weekend falls outside that range - Monday is as reasonable a fallback as any (the board has
// no "weekend" concept at all, every table is keyed to a Mon-Fri dayofweek).
function getDefaultDayAndShift(now) {
    const day = now.weekday <= 5 ? now.weekday - 1 : 0;
    const shift = now.hour >= AFTERNOON_START_HOUR ? "afternoon" : "morning";
    return { day, shift };
}

// "YYYY-MM-DD" from the browser's own local calendar date - deliberately NOT toISOString(),
// which converts to UTC first and so hands back the previous day for anyone east of Greenwich
// during the evening. The board's date is a plain calendar day, never an instant in time.
function toIsoDate(date) {
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
}

function fromIsoDate(iso) {
    const [year, month, day] = iso.split("-").map(Number);
    return new Date(year, month - 1, day);
}

// `days` calendar days after `date` (before, if negative), at midnight. Never by adding
// milliseconds: the day the clocks go back has 25 hours, so a week of 7 x 24h from a Monday landed
// on Sunday 23:00, and Monday and Tuesday both showed as the 25th (issue #678, 25/10/2026).
function addDays(date, days) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

// The Monday of whichever week `date` falls in. A weekend date belongs to the week that just
// happened (Saturday and Sunday follow their own Monday), which is also what makes picking a
// weekend in the date input land on a real, showable weekday instead of nothing at all.
function mondayOf(date) {
    const jsDay = date.getDay();
    const offset = jsDay === 0 ? 6 : jsDay - 1;
    return addDays(date, -offset);
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
// not read from any field's own prefetched sub-records, unlike the teacher/group/student grids
// (schedule_grid_field.js/schedule_grid_readonly_field.js). Those aggregate at most one teacher's,
// one group's or one student's own schedule; this one aggregates the whole centre (easily several hundred rows),
// which the web client's own x2many sub-record fetch silently caps — an earlier version that did
// read a prefetched field this way only ever showed real data for whichever weekday loaded first.
export class GuardDutyBoard extends Component {
    static template = "ems.GuardDutyBoard";
    static components = { GuardArrangementPlan };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.popover = useService("popover");
        this.notification = useService("notification");
        this.state = useState({
            // Both set in onWillStart, once the server clock is known.
            activeDay: 0,
            activeShift: "morning",
            // Area filter (issue #637): empty = "All areas" - see guard_duty_board.py's own
            // get_guard_duty_board_lines() docstring.
            activeAreaIds: [],
            areas: [],
            // The Monday the weekday tabs hang off. Absences are keyed to real dates while the
            // timetable is keyed to weekdays, so the board needs a concrete week before it can
            // say who is away - see ems.course.get_guard_duty_board_lines()'s 'day' argument.
            weekStart: "",
            activeView: "table",
            board: null,
            loading: true,
            courseId: null,
            courseName: "",
            // Which steps of each detected plan are checked (issue #645), by plan key: all of
            // them until the planner unchecks some. Forgotten on every reload.
            planSelections: {},
            noticeSelections: {},
        });
        onWillStart(async () => {
            const [course, areas] = await Promise.all([
                this.orm.call("ems.course", "get_current_course_data", []),
                this.orm.call("ems.course", "get_guard_duty_board_areas", []),
                syncServerClock(this.orm),
            ]);
            const now = serverNow();
            const { day, shift } = getDefaultDayAndShift(now);
            this.state.activeDay = day;
            this.state.activeShift = shift;
            this.state.weekStart = toIsoDate(mondayOf(fromIsoDate(now.toISODate())));
            this.state.courseId = course.id;
            this.state.courseName = course.name;
            this.state.areas = areas;
            this.restoreNavigation(this.props.state || this.props.action?.context?.params || {});
            await this.loadBoard();
        });
        // Coming back through the breadcrumbs hands this back as props.state (see restoreNavigation).
        useSetupAction({ getLocalState: () => this.navigationState });

        // The red line marking the current time (issue #647): placed on the DOM after every
        // render, on a resize (a centred table moves) and once a minute - never through a
        // re-render, so the board itself is never redrawn just to move it.
        this.contentRef = useRef("content");
        useEffect(() => this.placeNowLine());
        useExternalListener(window, "resize", () => this.placeNowLine());
        onMounted(() => {
            this.nowLineTimer = setInterval(() => this.placeNowLine(), NOW_LINE_REFRESH_MS);
        });
        onWillUnmount(() => {
            clearInterval(this.nowLineTimer);
            clearTimeout(this.lessonTimer);
            clearTimeout(this.refreshDebounce);
            this.busService.unsubscribe(GUARD_BOARD_CHANGED, this.onBoardChanged);
            this.busService.deleteChannel(GUARD_BOARD_CHANNEL);
        });
        // Issue #692: reload when the server says the day on screen changed (see onBoardChanged).
        this.busService = useService("bus_service");
        this.onBoardChanged = this.onBoardChanged.bind(this);
        this.busService.subscribe(GUARD_BOARD_CHANGED, this.onBoardChanged);
        this.busService.addChannel(GUARD_BOARD_CHANNEL);
        useExternalListener(document, "visibilitychange", () => this.flushRefresh());
    }

    // What the planner is looking at - week and day, shift, view and areas - kept in the URL
    // (?date=...&shift=...&view=...&areas=...) so the browser's back button, the breadcrumbs, a
    // reload and a shared link all return to it, instead of the default "now" (developer request,
    // 2026-10-07: back from a notice landed on this morning while organising this afternoon). Opening
    // the board from the menu carries no such parameters, so it still starts at "now".
    get navigationState() {
        return {
            date: this.activeDate,
            shift: this.state.activeShift,
            view: this.state.activeView,
            areas: this.state.activeAreaIds.join(","),
        };
    }

    syncNavigation() {
        this.props.updateActionState?.(this.navigationState);
    }

    // Applies a saved navigation state over the defaults, ignoring anything that isn't valid -
    // a URL can be edited or outlive the areas it named.
    restoreNavigation(saved) {
        if (/^\d{4}-\d{2}-\d{2}$/.test(saved.date || "")) {
            const picked = fromIsoDate(saved.date);
            const jsDay = picked.getDay();
            this.state.weekStart = toIsoDate(mondayOf(picked));
            this.state.activeDay = jsDay >= 1 && jsDay <= 5 ? jsDay - 1 : 0;
        }
        if (SHIFTS.some((shift) => shift.key === saved.shift)) {
            this.state.activeShift = saved.shift;
        }
        if (VIEWS.some((view) => view.key === saved.view)) {
            this.state.activeView = saved.view;
        }
        const areaIds = this.state.areas.map((area) => area.id);
        this.state.activeAreaIds = String(saved.areas || "").split(",").map(Number)
            .filter((id) => areaIds.includes(id));
    }

    // Each weekday tab carries its own real date, so the tab strip doubles as the week's
    // calendar: the label says which Monday, not just "Monday".
    get days() {
        const monday = fromIsoDate(this.state.weekStart);
        return dayLabels().map((label, index) => {
            const date = addDays(monday, index);
            return { index, label, date: toIsoDate(date), dayOfMonth: date.getDate() };
        });
    }

    // The header's own title - a plain string literal in the template would never go through
    // the translation extractor at all (found 2026-09-11: it always rendered in English
    // regardless of the user's own language, unlike every other label on this screen).
    get title() {
        return this.state.courseName
            ? _t("Guard duty schedule (%s)", this.state.courseName)
            : _t("Guard duty schedule");
    }

    get shifts() {
        return SHIFTS;
    }

    get views() {
        return VIEWS;
    }

    // The date the board is actually showing: the active weekday tab within the active week.
    get activeDate() {
        return this.days[this.state.activeDay].date;
    }

    get columnLabels() {
        return {
            time: _t("Time block"),
            guard: _t("Guard duty"),
            absences: _t("Absences"),
        };
    }

    // Both views come laid out on the server (ems.course's BoardTimeGrid, issue #637): a slot
    // points at its line by index, and the row's height follows its length, so the grid reads
    // like a clock.
    rowStyle(row) {
        return `height: ${Math.max(26, Math.round(row.minutes * 1.3))}px`;
    }

    // Where "now" falls in the grid on screen: the index of its row and how far down that row,
    // from 0 to 1 - or null when the board shows another day, or a time range that does not
    // include it (the other shift, before the first block, after the last one). The rows are
    // consecutive stretches of the shift, so there is no gap between two of them.
    nowLinePosition() {
        const board = this.state.board;
        if (this.state.loading || !board || !board.lines.length) {
            return null;
        }
        const now = serverNow();
        if (now.toISODate() !== this.activeDate) {
            return null;
        }
        const hour = now.hour + now.minute / 60;
        const grid = this.state.activeView === "schedule" ? board.schedule_grid : board.absence_grid;
        const index = grid.rows.findIndex((row) => hour >= row.hour_from && hour < row.hour_to);
        if (index === -1) {
            return null;
        }
        const row = grid.rows[index];
        return { index, fraction: (hour - row.hour_from) / (row.hour_to - row.hour_from) };
    }

    // Draws the line across the whole table at the current time, proportionally inside the row
    // holding it: the rows have different heights, so it is measured on the row itself. The line
    // sits in the table's wrapper (positioned), which scrolls sideways with the table.
    placeNowLine() {
        const line = this.contentRef.el?.querySelector(".o_guard_board_now_line");
        if (!line) {
            return;
        }
        const position = this.nowLinePosition();
        const wrap = line.parentElement;
        const table = wrap.querySelector(".o_guard_board_timeline");
        const row = position && table?.tBodies[0]?.rows[position.index];
        if (!row) {
            line.style.display = "none";
            return;
        }
        const wrapBox = wrap.getBoundingClientRect();
        const rowBox = row.getBoundingClientRect();
        const tableBox = table.getBoundingClientRect();
        line.style.top = `${rowBox.top - wrapBox.top + wrap.scrollTop + rowBox.height * position.fraction}px`;
        line.style.left = `${tableBox.left - wrapBox.left + wrap.scrollLeft}px`;
        line.style.width = `${tableBox.width}px`;
        line.style.display = "block";
    }

    slotAbsences(slot, key) {
        const line = this.state.board.lines[slot.line];
        return slot[key].map((index) => line.absences[index]);
    }

    get noAreaLabel() {
        return _t("Other groups");
    }

    get emptyLabels() {
        return {
            schedule: _t("No schedule for this shift."),
            absences: _t("Nobody is missing this shift."),
            loading: _t("Loading..."),
        };
    }

    // Small text tags rendered inline next to a time/guard name - kept as their own getters
    // (rather than folded into columnLabels/emptyLabels above, which are keyed by column/empty-
    // state, not by row) so the template can translate them the same way as everything else on
    // this board (developer request, 2026-09-11: make a patio guard duty and a WC guard duty
    // both visually obvious - see is_break/is_wc in guard_duty_board.py).
    //
    // The SOURCE string stays "Break" (real English), same msgid this board's own non-teaching
    // type ("Break", ems.non_teaching_br) is already translated under - it renders as "Patio"/
    // "Pati" only once ca_ES/es_ES's own msgstr kicks in. Found the hard way (2026-09-11,
    // developer report): an earlier version returned _t("Patio") directly - "Patio" isn't an
    // English word, so English readers saw "Patio" too, with no ca/es override needed to notice
    // anything was wrong (the bug was invisible from ca/es, which is exactly why it shipped).
    get breakLabel() {
        return _t("Break");
    }

    get wcSuffix() {
        return _t("(WC)");
    }

    get markPresentTooltip() {
        return _t("Not checked in: say they are in the centre");
    }

    get supportTooltip() {
        return _t("Send as support to a teacher in class");
    }

    get availableTooltip() {
        return _t("Available: assign them from the row of an absence");
    }

    get coverCountTitle() {
        return _t("Classes covered this course");
    }

    get coveredTitle() {
        return _t("Co-taught: another teacher is in the class, no guard needed");
    }

    // Compact label for the area dropdown's own toggle button - the full checkbox list already
    // shows every area by name, this is just what's visible before opening it.
    get areaFilterLabel() {
        if (!this.state.activeAreaIds.length) {
            return _t("All areas");
        }
        const selected = this.state.areas.filter((area) => this.state.activeAreaIds.includes(area.id));
        return selected.map((area) => area.name).join(", ");
    }

    async setActiveDay(index) {
        if (index === this.state.activeDay) {
            return;
        }
        this.state.activeDay = index;
        await this.loadBoard();
    }

    setActiveView(key) {
        // Both tabs render the same already-fetched payload, so switching between them never
        // costs a round trip.
        this.state.activeView = key;
        this.syncNavigation();
    }

    async onShiftChange(ev) {
        const key = ev.target.value;
        if (key === this.state.activeShift) {
            return;
        }
        this.state.activeShift = key;
        await this.loadBoard();
    }

    async toggleArea(areaId) {
        const activeAreaIds = this.state.activeAreaIds;
        const index = activeAreaIds.indexOf(areaId);
        if (index === -1) {
            activeAreaIds.push(areaId);
        } else {
            activeAreaIds.splice(index, 1);
        }
        await this.loadBoard();
    }

    // Picking any date moves the whole week and lands on that date's own weekday tab - a
    // weekend picks the week it closes (see mondayOf) and falls back to its Monday, since the
    // board has no weekend column to show.
    async onDateChange(ev) {
        const value = ev.target.value;
        if (!value) {
            return;
        }
        const picked = fromIsoDate(value);
        const monday = mondayOf(picked);
        const jsDay = picked.getDay();
        this.state.weekStart = toIsoDate(monday);
        this.state.activeDay = jsDay >= 1 && jsDay <= 5 ? jsDay - 1 : 0;
        await this.loadBoard();
    }

    async shiftWeek(weeks) {
        const monday = fromIsoDate(this.state.weekStart);
        this.state.weekStart = toIsoDate(addDays(monday, weeks * 7));
        await this.loadBoard();
    }

    get boardArgs() {
        return [String(this.state.activeDay), this.state.activeShift, this.state.activeAreaIds, this.activeDate];
    }

    async loadBoard() {
        this.state.loading = true;
        this.state.planSelections = {};
        this.state.noticeSelections = {};
        this.state.board = await this.orm.call("ems.course", "get_guard_duty_board_data", this.boardArgs);
        this.state.loading = false;
        this.refreshPending = false;
        this.syncNavigation();
        this.scheduleLessonRefresh();
    }

    // Issue #692: the board reloads itself only when something it shows may have changed, never on
    // a fixed interval: when the server says so through the bus (a check-in, a guard sent or
    // released, an absence, a timetable change told to the families - see
    // ems.guard_board_notifier) for the day on screen, and when a lesson starts or ends today
    // (a class whose teacher has not checked in shows up as it starts). Quietly: no spinner, the
    // planner's checked steps are kept, and nothing is redrawn unless something changed. A burst
    // of notifications is one reload. While a dialog or popover is open, or the tab is hidden, the
    // reload waits and happens as soon as it is closed or shown again.
    onBoardChanged(payload) {
        const date = this.activeDate;
        if (date && payload.date_from <= date && date <= payload.date_to) {
            this.requestRefresh();
        }
    }

    requestRefresh() {
        this.refreshPending = true;
        clearTimeout(this.refreshDebounce);
        this.refreshDebounce = setTimeout(() => this.flushRefresh(), REFRESH_DEBOUNCE_MS);
    }

    get refreshBlocked() {
        return this.state.loading || this.refreshing || document.visibilityState !== "visible"
            // A tooltip is a popover too, but only shows what the pointer is over.
            || Boolean(document.querySelector(".o_dialog, .o_popover:not(:has(.o-tooltip))"));
    }

    async flushRefresh() {
        if (!this.refreshPending || this.refreshBlocked) {
            return;
        }
        this.refreshPending = false;
        const args = this.boardArgs;
        this.refreshing = true;
        try {
            const board = await this.orm.silent.call("ems.course", "get_guard_duty_board_data", args);
            // The planner moved to another day, shift or area meanwhile: that load wins.
            if (JSON.stringify(args) === JSON.stringify(this.boardArgs) && !this.state.loading
                    && JSON.stringify(board) !== JSON.stringify(this.state.board)) {
                this.state.board = board;
                this.scheduleLessonRefresh();
            }
        } catch {
            // A network hiccup: the next change or lesson tries again.
        } finally {
            this.refreshing = false;
        }
        if (this.refreshPending) {
            this.flushRefresh();
        }
    }

    // The next start or end of a lesson today, plus a second: rows appear (a class whose teacher
    // has not checked in) or stop offering "They are in the classroom" then.
    scheduleLessonRefresh() {
        clearTimeout(this.lessonTimer);
        const now = serverNow();
        if (!this.state.board || this.activeDate !== now.toISODate()) {
            return;
        }
        const hour = now.hour + now.minute / 60 + now.second / 3600;
        const next = Math.min(...this.state.board.lines.flatMap((line) => [line.hour_from, line.hour_to])
            .filter((boundary) => boundary > hour));
        if (Number.isFinite(next)) {
            this.lessonTimer = setTimeout(() => this.requestRefresh(), (next - hour) * 3600 * 1000 + 1000);
        }
    }

    // Dialogs and popovers opened from the board flush a reload that waited for them on close.
    addDialog(component, props, onClose = () => {}) {
        return this.dialog.add(component, props, { onClose: () => {
            onClose();
            setTimeout(() => this.flushRefresh());
        } });
    }

    addPopover(target, component, props) {
        return this.popover.add(target, component, props, { onClose: () => setTimeout(() => this.flushRefresh()) });
    }

    // Bold red for an absence that is going to happen, a lighter italic for one still waiting
    // on its approver - the planner has to be able to tell a fact from a warning at a glance.
    absenceClass(absence) {
        if (absence === "approved") {
            return "o_guard_board_absent";
        }
        if (absence === "moved") {
            // Issue #645: not away, their lesson went elsewhere - nobody is with the group then.
            return "o_guard_board_absent_moved";
        }
        if (absence === "unchecked") {
            // Issue #692: not checked in yet - maybe in the building, maybe not.
            return "o_guard_board_absent_unchecked";
        }
        return absence === "pending" ? "o_guard_board_absent_pending" : "";
    }

    // Managing absences from the absences table (issues #539, #571, #581). Every action below
    // is checked again on the server (ems.absence_cover.board_assign/board_release,
    // ems.notice.board_send_absence_change): the flags the board sends only decide what is
    // offered, never what is allowed.

    get actionLabels() {
        return {
            releasesTitle: _t("Guards no longer needed"),
            openDraft: _t("Open draft"),
            release: _t("Release guard"),
            removeArrangement: _t("Remove arrangement"),
            changeProposal: _t("Change proposal"),
            arrangementsTitle: _t("Proposals for the absences"),
            // What each kind of step means (issue #709): a short intro and one line per kind, with the
            // icon the steps themselves carry.
            arrangementsHelp: {
                intro: _t("For each group, the best ways to organise its absences, the best first. Check what you want and click"),
                // The button's own name, in its colour, so it is easy to find.
                button: _t("Apply the checked steps"),
                points: [
                    { icon: "fa-arrows-v", text: _t("A teacher moves a lesson, or two teachers swap theirs. Under it, in grey, the details; in orange, whether somebody comes in or leaves at another time.") },
                    { icon: "fa-envelope-o", text: _t("A notice to the families, when the group can come in later or leave earlier: its lessons are struck off the table.") },
                    { icon: "fa-user-o", text: _t("A lesson no checked step solves stays on the table, for a guard. The teachers involved are notified.") },
                ],
            },
            noticeOnly: _t("Only tell the families"),
            noticeOnlyStudents: _t("Only tell the students"),
            correctionsTitle: _t("Corrections to absences already organised"),
            correctionsHelp: { intro: _t("The families of these groups were told something that no longer matches the absences: send them a correction as soon as possible. Every proposal already includes it, in one email per group; to send only the correction, uncheck the other steps."), points: [] },
            applyPlan: _t("Apply the checked steps"),
        };
    }

    // A row nobody needs to be sent to anymore is struck out: a co-teacher is in the class, a
    // guard has been assigned (the row then takes that guard's colour), the families were told
    // the students can stay at home for it, or the teachers rearranged themselves (issue #605).
    absenceRowClass(absence) {
        const classes = {
            o_guard_board_absence_covered: absence.covered,
            o_guard_board_absence_struck: !absence.covered && Boolean(this.isFullyCovered(absence) || absence.authorized || this.isArranged(absence)),
            o_guard_board_absence_manageable: this.isAssignable(absence) || absence.can_self_assign || Boolean(absence.self_cover_id)
                || absence.can_mark_present,
            o_guard_board_absence_not_on_guard: Boolean(this.notOnGuardReason(absence)),
        };
        if (absence.covers.length) {
            classes[`o_guard_board_cover_${absence.covers[0].color}`] = true;
            // Painted as soon as a guard covers any of it; a dashed border while a part is still
            // missing, solid once it is all covered (issue #637).
            classes.o_guard_board_cover_partial = absence.missing.length > 0;
        }
        return classes;
    }

    // Several guards can each cover part of a class (issue #637): it only needs nobody else once
    // nothing is missing.
    isFullyCovered(absence) {
        return absence.covers.length > 0 && !absence.missing.length;
    }

    // The line's tooltip: why it is struck out (the same as its info icon), or, on a line still
    // to be covered, how to send a guard to it.
    absenceRowTooltip(absence) {
        if (absence.can_mark_present) {
            return _t("%s has not checked in yet. Click if they are in the classroom, or to cover the class.", absence.teacher);
        }
        if (this.struckReason(absence)) {
            return this.struckReason(absence);
        }
        if (absence.arrangement) {
            return _t("%s It only counts once its notice to the families is sent.", absence.arrangement.label);
        }
        if (absence.arrangement_plans.length && absence.can_manage) {
            return _t("Click to see the possible arrangements, or to send a guard teacher");
        }
        // A row can also be a guard duty that is not regular (WC, break...) left without its
        // teacher (issue #606): 'duty_id' set, 'group' holding the duty's name.
        if (this.isAssignable(absence)) {
            if (absence.covers.length) {
                return _t("Click to send a guard teacher to the part still missing");
            }
            return absence.duty_id
                ? _t("Click to send a guard teacher to this guard duty")
                : _t("Click to send a guard teacher to this class");
        }
        if (!absence.can_self_assign) {
            return this.notOnGuardReason(absence);
        }
        return absence.duty_id ? _t("Click to cover this guard duty yourself") : _t("Click to cover this class yourself");
    }

    // Issue #659: a line still to be covered that the current user can do nothing about, because
    // they are not on guard duty then, says so too - every line answers the pointer, not only some.
    notOnGuardReason(absence) {
        if (!this.state.board.editable || absence.self_label || absence.can_self_assign || absence.self_cover_id
                || absence.arrangement || this.struckReason(absence) || this.isAssignable(absence) || absence.can_mark_present) {
            return false;
        }
        return _t("You cannot cover this teacher: you are not on guard duty at this time.");
    }

    // Why a line is struck out, for everyone (not only whoever can organise the absence): shown by
    // the info icon to its left, on hover and on click.
    struckReason(absence) {
        if (absence.covered) {
            return this.coveredTitle;
        }
        if (absence.authorized) {
            return _t("No guard needed: the families were told \"%s\".", absence.authorized);
        }
        if (this.isFullyCovered(absence)) {
            if (absence.covers.length > 1) {
                const guards = absence.covers.map((cover) => `${cover.guard} (${cover.label})`).join(", ");
                return _t("Covered by %s, the guard teachers sent to it.", guards);
            }
            return absence.duty_id
                ? _t("Covered by %s, the guard teacher sent to this guard duty.", absence.covers[0].guard)
                : _t("Covered by %s, the guard teacher sent to this class.", absence.covers[0].guard);
        }
        if (this.isArranged(absence)) {
            return _t("No guard needed: %s", absence.arrangement.label);
        }
        return false;
    }

    // An internal arrangement in effect (issue #605): one still waiting for its notice resolves nothing yet.
    isArranged(absence) {
        return Boolean(absence.arrangement && !absence.arrangement.pending);
    }

    // Clicking a struck-out line (anywhere on it, not only its icon) explains it, anchored to the
    // icon; clicking a line still to be covered sends a guard to it.
    onAbsenceClick(ev, line, absence) {
        if (absence.can_mark_present) {
            this.openUncheckedDialog(line, absence);
            return;
        }
        const reason = this.struckReason(absence);
        if (!reason) {
            const notOnGuard = this.notOnGuardReason(absence);
            if (notOnGuard) {
                const anchor = ev.currentTarget.querySelector(".o_guard_board_absence_info") || ev.currentTarget;
                this.addPopover(anchor, GuardBoardReasonPopover, { reason: notOnGuard });
            } else if (absence.arrangement && absence.can_manage) {
                // Waiting for its notice: the planner either sends it or changes their mind.
                this.openCoverDialog(line, absence);
            } else if (this.isAssignable(absence)) {
                this.openCoverDialog(line, absence);
            } else if (absence.can_self_assign) {
                this.confirmSelfAssign(line, absence);
            } else if (absence.self_cover_id) {
                // Their own part of a class still missing another (issue #637).
                this.confirmSelfRelease(absence);
            }
            return;
        }
        const props = { reason };
        if (absence.covers.length && this.isAssignable(absence)) {
            props.actionLabel = _t("Change or remove the guard");
            props.onAction = () => this.openCoverDialog(line, absence);
        } else if (absence.arrangement && this.isAssignable(absence)) {
            props.actionLabel = _t("Change or remove the arrangement");
            props.onAction = () => this.openCoverDialog(line, absence);
        } else if (absence.authorized && absence.change_side && absence.can_manage) {
            props.actionLabel = this.actionLabels.changeProposal;
            props.onAction = () => this.openChangeProposalDialog(absence);
        } else if (absence.self_cover_id) {
            props.actionLabel = _t("Stop covering this class");
            props.onAction = () => this.confirmSelfRelease(absence);
        }
        const icon = ev.currentTarget.querySelector(".o_guard_board_absence_info") || ev.currentTarget;
        this.addPopover(icon, GuardBoardReasonPopover, props);
    }

    // A co-taught class or one the families were told about needs nobody, so it offers nothing.
    isAssignable(absence) {
        return absence.can_manage && !absence.covered && !absence.authorized;
    }

    guardBadgeClass(guard) {
        let base = this.absenceClass(guard.absence);
        if (guard.busy) {
            base += " o_guard_board_guard_busy";
        }
        if (guard.color === false) {
            return base;
        }
        return `${base} o_guard_board_cover_${guard.color}${guard.partial ? " o_guard_board_cover_partial" : ""}`;
    }

    // Issues #539, #605, #645: the day's proposals, one section per group (with the groups sharing
    // lessons with it): what is waiting (an arrangement waiting for its notice), the arrangement
    // plans, the best first, and the timetable changes alone. A section with a correction pending
    // is 'urgent' (issue #659), shown in a box of its own: the correction is a step of every one of
    // its proposals, the last one ("Only tell the families") included.
    get proposalSections() {
        const sections = new Map();
        for (const action of this.state.board.actions) {
            if (action.type === "obsolete_cover") {
                continue;
            }
            if (!sections.has(action.section_key)) {
                sections.set(action.section_key, {
                    key: action.section_key, title: action.section_title, waiting: [], plans: [], notices: [], urgent: false,
                });
            }
            const section = sections.get(action.section_key);
            if (action.type === "arrangement_plan") {
                section.plans.push(action);
            } else if (action.type === "proposal" || action.type === "rectification") {
                section.notices.push(action);
                section.urgent ||= action.type === "rectification";
            } else {
                section.waiting.push(action);
            }
        }
        return [...sections.values()].sort((first, second) => first.title.localeCompare(second.title));
    }

    // The timetable change alone comes after the section's arrangement plans, numbered with them.
    noticePlanTitle(section) {
        return _t("Proposal %s:", section.plans.length + 1);
    }

    // A break is only told to the students (issue #679).
    noticeOnlyLabel(section) {
        return section.notices.every((action) => action.students_only)
            ? this.actionLabels.noticeOnlyStudents
            : this.actionLabels.noticeOnly;
    }

    arrangementCountLabel(absence) {
        const count = absence.arrangement_plans.length;
        return count === 1 ? _t("1 possible arrangement") : _t("%s possible arrangements", count);
    }

    planSelection(plan) {
        return this.state.planSelections[plan.key] || fullPlanSelection(plan);
    }

    hasSelectedSteps(plan) {
        return this.planSelection(plan).some((checked) => checked);
    }

    togglePlanStep(plan, index, checked) {
        this.state.planSelections[plan.key] = toggledPlanSelection(plan, this.planSelection(plan), index, checked);
    }

    // Applies the checked steps of a detected plan (issue #652): the notices they bring, one per
    // group to its families and one to its students, are sent straight away - checking the step
    // was the confirmation. One that could not be sent stays a draft and opens, with the reason,
    // for the planner to review and send: the moves it frees the group from only count once it is.
    // `reopen`: the side of a group's day whose notice the plan corrects (issue #659).
    // A teacher's timetable can't be changed without them (issue #709): when the checked steps
    // change somebody's entry or exit time, the planner confirms first that they agreed. False when
    // the planner cancels, so the dialog it came from stays open.
    async applyPlan(plan, selection, reopen = false) {
        const steps = plan.steps.filter((_step, index) => selection[index]);
        if (!(await this.confirmScheduleChanges(steps))) {
            return false;
        }
        await this.applySteps(selectedPlanSteps(plan, selection), reopen);
        return true;
    }

    confirmScheduleChanges(steps) {
        const changes = steps.flatMap((step) => step.schedule_changes);
        if (!changes.length) {
            return Promise.resolve(true);
        }
        const teachers = [...new Set(steps.flatMap((step) => step.schedule_teachers))];
        return new Promise((resolve) => {
            this.addDialog(ConfirmationDialog, {
                title: _t("Working day changes"),
                body: _t("This arrangement changes when some teachers come in or leave:\n\n%(changes)s\n\nA teacher's timetable cannot be changed without their agreement. Have you talked to %(teachers)s?", {
                    changes: changes.map((change) => `- ${change}`).join("\n"),
                    teachers: formatList(teachers),
                }),
                confirmLabel: _t("Yes, apply it"),
                cancelLabel: _t("Not yet"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
    }

    async applySteps(steps, reopen = false) {
        const result = await this.orm.call("ems.absence_cover", "board_apply_plan", [this.activeDate, steps], { reopen });
        if (!(await this.openUnsentNotice(result))) {
            await this.loadBoard();
            this.openGapCovers(result.gaps);
        }
    }

    // Issue #710: the classes the applied steps still leave without anybody need a guard, so the
    // guard assignment of each opens, one after the other, offering only that: the planner already
    // chose how to organise the day. A class not on the board's shift, or already covered, is
    // skipped.
    openGapCovers(gaps) {
        const [gap, ...rest] = gaps || [];
        if (!gap) {
            return;
        }
        for (const line of this.state.board.lines) {
            if (line.hour_from >= gap.hour_to || gap.hour_from >= line.hour_to) {
                continue;
            }
            const absence = line.absences.find((row) => row.group_id === gap.group_id && this.isAssignable(row)
                && !row.covers.length && !row.arrangement);
            if (absence) {
                this.openCoverDialog(line, absence, { guardOnly: true, onClose: () => this.openGapCovers(rest) });
                return;
            }
        }
        this.openGapCovers(rest);
    }

    // "Only tell the families", its rows as steps (issue #659; all checked until the planner
    // unchecks some): the checked ones go out together, one notice per group, a correction when
    // it carries one.
    isNoticeChecked(section, index) {
        return this.state.noticeSelections[`${section.key}:${index}`] !== false;
    }

    toggleNotice(section, index, checked) {
        this.state.noticeSelections[`${section.key}:${index}`] = checked;
    }

    async applyNotices(section) {
        await this.applySteps(section.notices.filter((action, index) => this.isNoticeChecked(section, index)).map((action) => ({
            kind: action.type === "rectification" ? "correction" : "notice",
            group_ids: [action.group_id],
            change: action.options[action.default].change,
        })));
    }

    // A board action sends its notices at once (issue #652); one that could not be sent stays a
    // draft, which opens with the reason for the planner to review and send. Whether it did.
    async openUnsentNotice(result) {
        if (!result.notice_action) {
            return false;
        }
        if (result.notice_error) {
            this.notification.add(result.notice_error, { type: "warning", sticky: true });
        }
        await this.actionService.doAction(result.notice_action);
        return true;
    }

    // An arrangement described by hand (issue #605).
    async applyManualArrangement(classHours, absentId, groupId, teacherId, note) {
        await this.orm.call("ems.absence_cover", "board_arrange", [
            this.activeDate, classHours.hour_from, classHours.hour_to, absentId, groupId, "manual", teacherId || false, note,
        ]);
        await this.loadBoard();
    }

    get releaseActions() {
        return this.state.board.actions.filter((action) => action.type === "obsolete_cover");
    }

    // Which of the allowed changes the planner picked in the proposal's selector (the largest one
    // until they choose otherwise) - kept on the action itself, which lives until the next reload.
    onActionOptionChange(action, ev) {
        action.default = Number(ev.target.value);
    }

    actionIcon(action) {
        if (action.type === "obsolete_cover") {
            return "fa fa-user-times";
        }
        if (action.type === "pending_arrangement") {
            return "fa fa-exchange";
        }
        return action.type === "rectification" ? "fa fa-exclamation-triangle" : "fa fa-envelope-o";
    }

    actionButtonLabel(action) {
        if (action.type === "obsolete_cover") {
            return action.cover_type === "arrangement" ? this.actionLabels.removeArrangement : this.actionLabels.release;
        }
        return this.actionLabels.openDraft;
    }

    // `guardOnly`: only "Send a guard teacher" (issue #710); `onClose`: once it closes.
    openCoverDialog(line, absence, { guardOnly = false, onClose } = {}) {
        if (!this.isAssignable(absence)) {
            return;
        }
        const classArgs = [this.activeDate, line.hour_from, line.hour_to, absence.teacher_id, absence.group_id];
        this.addDialog(GuardCoverDialog, {
            row: absence,
            line,
            guardOnly,
            onAssign: async (guardId, message) => {
                await this.orm.call("ems.absence_cover", "board_assign", [...classArgs, guardId, message],
                    { duty_id: absence.duty_id });
                await this.loadBoard();
            },
            // Issue #605: an internal arrangement, detected or described by hand.
            loadArrangementCandidates: () => this.orm.call("ems.course", "get_arrangement_candidates", classArgs),
            onApplyPlan: (plan, selection) => this.applyPlan(plan, selection),
            onArrange: (teacherId, note) => this.applyManualArrangement(line, absence.teacher_id, absence.group_id, teacherId, note),
            onOpenNotice: absence.arrangement && absence.arrangement.pending
                ? () => this.openNotice(absence.arrangement.notice_id) : undefined,
            onRelease: async (coverId) => {
                await this.orm.call("ems.absence_cover", "board_release", [coverId || absence.arrangement.id]);
                await this.loadBoard();
            },
        }, onClose);
    }

    // A guard's badge on the absences table: says a guard who has not checked in is in the centre
    // (issue #692), or sends a guard as support (issue #725).
    onGuardClick(line, guard) {
        if (guard.can_mark_present) {
            this.openUncheckedGuardDialog(line, guard);
        } else if (guard.can_support) {
            this.openSupportDialog(line, guard);
        }
    }

    openUncheckedGuardDialog(line, guard) {
        this.addDialog(GuardUncheckedDialog, {
            row: { teacher: guard.name, group: _t("Guard duty") },
            line,
            guard: true,
            onMarkPresent: async () => {
                await this.orm.call("ems.absence_cover", "board_mark_present", [
                    this.activeDate, line.hour_from, line.hour_to, guard.id,
                ]);
                this.notification.add(_t("%s is now checked in.", guard.name), { type: "success" });
                await this.loadBoard();
            },
        });
    }

    // Issue #725: sends a guard of the period to support a teacher who is in class, or withdraws
    // the support they already give.
    openSupportDialog(line, guard) {
        const period = [this.activeDate, line.hour_from, line.hour_to, guard.id];
        this.addDialog(GuardSupportDialog, {
            guard,
            line,
            loadOptions: () => this.orm.call("ems.absence_cover", "get_support_options", period),
            onSend: async (option, message) => {
                await this.orm.call("ems.absence_cover", "board_support", [...period, option.teacher_id, option.group_id, message]);
                await this.loadBoard();
            },
            onRelease: async (coverId) => {
                await this.orm.call("ems.absence_cover", "board_release", [coverId]);
                await this.loadBoard();
            },
        });
    }

    // Issue #692: the teacher of a class in progress has not checked in. The dialog offers to say
    // they are in the classroom, and whatever the user could otherwise do with the row.
    openUncheckedDialog(line, absence) {
        let onCover;
        let coverLabel;
        if (this.isAssignable(absence)) {
            coverLabel = absence.covers.length ? _t("Change or remove the guard") : _t("Send a guard teacher");
            onCover = () => this.openCoverDialog(line, absence);
        } else if (absence.self_cover_id) {
            coverLabel = _t("Stop covering this class");
            onCover = () => this.confirmSelfRelease(absence);
        } else if (absence.can_self_assign) {
            // Choosing it in this dialog is the confirmation, as for "They are in the classroom".
            coverLabel = _t("Cover it myself");
            onCover = () => this.selfAssign(line, absence);
        }
        this.addDialog(GuardUncheckedDialog, {
            row: absence,
            line,
            coverLabel,
            onCover,
            onMarkPresent: async () => {
                await this.orm.call("ems.absence_cover", "board_mark_present", [
                    this.activeDate, line.hour_from, line.hour_to, absence.teacher_id, absence.group_id,
                ], { duty_id: absence.duty_id });
                this.notification.add(_t("%s is now checked in.", absence.teacher), { type: "success" });
                await this.loadBoard();
            },
        });
    }

    // Issue #659: changes what the families were told for a struck-out row, with one correction
    // sent at once: choosing it in the dialog is the confirmation.
    openChangeProposalDialog(absence) {
        this.addDialog(GuardChangeProposalDialog, {
            loadOptions: () => this.orm.call("ems.course", "get_change_proposal_options", [
                this.activeDate, absence.group_id, absence.change_side,
            ]),
            onSend: (option) => this.sendChange(absence.group_id, option),
            onApplyPlan: (plan, selection, reopen) => this.applyPlan(plan, selection, reopen),
        });
    }

    // Issue #601: a teacher on guard duty takes a class nobody covers yet, or leaves one they
    // took themselves. Nobody is notified - the board itself shows it to whoever organises it.
    confirmSelfAssign(line, absence) {
        this.addDialog(ConfirmationDialog, {
            title: _t("Cover this class"),
            body: _t("You will cover %(group)s (%(time)s) instead of %(teacher)s.", {
                group: absence.group, time: absence.self_label, teacher: absence.teacher,
            }),
            confirmLabel: _t("Cover it"),
            confirm: () => this.selfAssign(line, absence),
            cancel: () => {},
        });
    }

    async selfAssign(line, absence) {
        await this.orm.call("ems.absence_cover", "board_self_assign", [
            this.activeDate, line.hour_from, line.hour_to, absence.teacher_id, absence.group_id,
        ], { duty_id: absence.duty_id });
        await this.loadBoard();
    }

    confirmSelfRelease(absence) {
        this.addDialog(ConfirmationDialog, {
            title: _t("Stop covering this class"),
            body: _t("%(group)s will be left without a guard teacher again.", { group: absence.group }),
            confirmLabel: _t("Stop covering"),
            confirm: async () => {
                await this.orm.call("ems.absence_cover", "board_self_release", [absence.self_cover_id]);
                await this.loadBoard();
            },
            cancel: () => {},
        });
    }

    // Releasing a guard that is no longer needed notifies them straight away; an arrangement
    // waiting for its notice opens that draft.
    async onAction(action) {
        if (action.type === "obsolete_cover") {
            await this.orm.call("ems.absence_cover", "board_release", [action.cover_id]);
            await this.loadBoard();
            return;
        }
        await this.openNotice(action.draft_id);
    }

    async openNotice(noticeId) {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "ems.notice",
            res_id: noticeId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Sends one timetable change (or its correction) to a group's families at once (issue #652):
    // choosing it was the confirmation. A notice that could not be sent stays a draft and opens,
    // with the reason, for the planner to review.
    async sendChange(groupId, option) {
        const result = await this.orm.call("ems.notice", "board_send_absence_change", [
            this.activeDate, groupId, option.change_type, option.hour, option.hour_to,
        ]);
        if (!(await this.openUnsentNotice(result))) {
            this.notification.add(_t("Correction sent."), { type: "success" });
            await this.loadBoard();
        }
    }

    // One PDF per day AND per shift — whichever day tab / shift dropdown is currently active,
    // not the whole week or both shifts — see reports/attendance/report_guard_duty_board.xml's
    // own use of the 'guard_duty_weekday'/'guard_duty_shift' context keys. 'guard_duty_area_ids'
    // (issue #637) forwards the same area selection, following the same pattern; 'guard_duty_date'
    // is the printed copy's own absence information - a cuadrante handed out to plan the day's
    // guards is no use without them. 'guard_duty_view' (found 2026-09-11) forwards which of the
    // two tabs is actually on screen, so the PDF prints whatever the user is currently looking
    // at instead of always the schedule tab regardless of the "Absences table" tab being active.
    async onPdfClick() {
        await this.actionService.doAction("ems.action_report_guard_duty_board", {
            additionalContext: {
                active_ids: [this.state.courseId],
                guard_duty_weekday: String(this.state.activeDay),
                guard_duty_shift: this.state.activeShift,
                guard_duty_area_ids: this.state.activeAreaIds,
                guard_duty_date: this.activeDate,
                guard_duty_view: this.state.activeView,
            },
        });
    }
}

registry.category("actions").add("ems_guard_duty_board", GuardDutyBoard);
