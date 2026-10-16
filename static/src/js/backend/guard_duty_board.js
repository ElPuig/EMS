/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { _t } from "@web/core/l10n/translation";
import { dayLabels } from "./schedule_grid_geometry";
import { serverNow, syncServerClock } from "./server_clock";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { GuardCoverDialog } from "./guard_cover_dialog";
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

const MS_PER_DAY = 24 * 60 * 60 * 1000;

// How often the current-time line moves down the grid: once a minute, its own resolution.
const NOW_LINE_REFRESH_MS = 60 * 1000;

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

// The Monday of whichever week `date` falls in. A weekend date belongs to the week that just
// happened (Saturday and Sunday follow their own Monday), which is also what makes picking a
// weekend in the date input land on a real, showable weekday instead of nothing at all.
function mondayOf(date) {
    const jsDay = date.getDay();
    const offset = jsDay === 0 ? 6 : jsDay - 1;
    return new Date(date.getTime() - offset * MS_PER_DAY);
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
        onWillUnmount(() => clearInterval(this.nowLineTimer));
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
            const date = new Date(monday.getTime() + index * MS_PER_DAY);
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
        this.state.weekStart = toIsoDate(new Date(monday.getTime() + weeks * 7 * MS_PER_DAY));
        await this.loadBoard();
    }

    async loadBoard() {
        this.state.loading = true;
        this.state.planSelections = {};
        this.state.board = await this.orm.call(
            "ems.course",
            "get_guard_duty_board_data",
            [String(this.state.activeDay), this.state.activeShift, this.state.activeAreaIds, this.activeDate]
        );
        this.state.loading = false;
        this.syncNavigation();
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
        return absence === "pending" ? "o_guard_board_absent_pending" : "";
    }

    // Managing absences from the absences table (issues #539, #571, #581). Every action below
    // is checked again on the server (ems.absence_cover.board_assign/board_release,
    // ems.notice.board_send_absence_change): the flags the board sends only decide what is
    // offered, never what is allowed.

    get actionLabels() {
        return {
            releasesTitle: _t("Guards no longer needed"),
            propose: _t("Send notice"),
            rectify: _t("Send correction"),
            openDraft: _t("Open draft"),
            release: _t("Release guard"),
            removeArrangement: _t("Remove arrangement"),
            arrangementsTitle: _t("Proposals for the absences"),
            arrangementsHelp: _t("For each group, how to organise its absences, the best first: the teachers rearranging their lessons so that the students lose as few lessons as possible and no guard is needed, or only telling the families. Uncheck the steps you do not want: the lessons they would have solved stay on the table. Sending a notice strikes its lessons off the table; you can choose a shorter change and send a guard to the rest. The teachers involved are notified."),
            noticeOnly: _t("Only tell the families"),
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
            o_guard_board_absence_manageable: this.isAssignable(absence) || absence.can_self_assign || Boolean(absence.self_cover_id),
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
            return false;
        }
        return absence.duty_id ? _t("Click to cover this guard duty yourself") : _t("Click to cover this class yourself");
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
        const reason = this.struckReason(absence);
        if (!reason) {
            if (absence.arrangement && absence.can_manage) {
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
        } else if (absence.self_cover_id) {
            props.actionLabel = _t("Stop covering this class");
            props.onAction = () => this.confirmSelfRelease(absence);
        }
        const icon = ev.currentTarget.querySelector(".o_guard_board_absence_info") || ev.currentTarget;
        this.popover.add(icon, GuardBoardReasonPopover, props);
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
    // lessons with it): what is waiting (an arrangement waiting for its notice, a correction), the
    // arrangement plans, the best first, and the timetable changes alone.
    get proposalSections() {
        const sections = new Map();
        for (const action of this.state.board.actions) {
            if (action.type === "obsolete_cover") {
                continue;
            }
            if (!sections.has(action.section_key)) {
                sections.set(action.section_key, { key: action.section_key, title: action.section_title, waiting: [], plans: [], notices: [] });
            }
            const section = sections.get(action.section_key);
            if (action.type === "arrangement_plan") {
                section.plans.push(action);
            } else if (action.type === "proposal") {
                section.notices.push(action);
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
    async applyPlan(plan, selection) {
        const result = await this.orm.call("ems.absence_cover", "board_apply_plan", [
            this.activeDate, selectedPlanSteps(plan, selection),
        ]);
        if (!(await this.openUnsentNotice(result))) {
            await this.loadBoard();
        }
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
        if (action.draft_id) {
            return this.actionLabels.openDraft;
        }
        return action.type === "rectification" ? this.actionLabels.rectify : this.actionLabels.propose;
    }

    openCoverDialog(line, absence) {
        if (!this.isAssignable(absence)) {
            return;
        }
        const classArgs = [this.activeDate, line.hour_from, line.hour_to, absence.teacher_id, absence.group_id];
        this.dialog.add(GuardCoverDialog, {
            row: absence,
            line,
            onAssign: async (guardId, message) => {
                await this.orm.call("ems.absence_cover", "board_assign", [...classArgs, guardId, message],
                    { duty_id: absence.duty_id });
                await this.loadBoard();
            },
            // Issue #605: an internal arrangement, detected or described by hand.
            loadArrangementCandidates: () => this.orm.call("ems.course", "get_arrangement_candidates", classArgs),
            onApplyPlan: (plan, selection) => this.applyPlan(plan, selection),
            onArrange: (teacherId, note) => this.applyManualArrangement(line, absence.teacher_id, absence.group_id, teacherId, note),
            onOpenNotice: absence.arrangement && absence.arrangement.pending ? () => this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "ems.notice",
                res_id: absence.arrangement.notice_id,
                views: [[false, "form"]],
                target: "current",
            }) : undefined,
            onRelease: async (coverId) => {
                await this.orm.call("ems.absence_cover", "board_release", [coverId || absence.arrangement.id]);
                await this.loadBoard();
            },
        });
    }

    // Issue #601: a teacher on guard duty takes a class nobody covers yet, or leaves one they
    // took themselves. Nobody is notified - the board itself shows it to whoever organises it.
    confirmSelfAssign(line, absence) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Cover this class"),
            body: _t("You will cover %(group)s (%(time)s) instead of %(teacher)s.", {
                group: absence.group, time: absence.self_label, teacher: absence.teacher,
            }),
            confirmLabel: _t("Cover it"),
            confirm: async () => {
                await this.orm.call("ems.absence_cover", "board_self_assign", [
                    this.activeDate, line.hour_from, line.hour_to, absence.teacher_id, absence.group_id,
                ], { duty_id: absence.duty_id });
                await this.loadBoard();
            },
            cancel: () => {},
        });
    }

    confirmSelfRelease(absence) {
        this.dialog.add(ConfirmationDialog, {
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

    // Proposing (or rectifying) a timetable change opens its draft notice - created on the spot
    // the first time - for the planner to review and send from the notice's own form; releasing a
    // guard that is no longer needed notifies them straight away.
    async onAction(action) {
        if (action.type === "obsolete_cover") {
            await this.orm.call("ems.absence_cover", "board_release", [action.cover_id]);
            await this.loadBoard();
            return;
        }
        if (action.draft_id) {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "ems.notice",
                res_id: action.draft_id,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        // Sent at once (issue #652): clicking the button is the confirmation. A notice that could
        // not be sent stays a draft and opens, with the reason, for the planner to review.
        const option = action.options[action.default];
        const result = await this.orm.call("ems.notice", "board_send_absence_change", [
            this.activeDate, action.group_id, option.change_type, option.hour, option.hour_to,
        ]);
        if (!(await this.openUnsentNotice(result))) {
            this.notification.add(_t("Notice sent."), { type: "success" });
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
