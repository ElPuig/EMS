/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { dayLabels } from "./schedule_grid_geometry";
import { serverNow, syncServerClock } from "./server_clock";
import { GuardCoverDialog } from "./guard_cover_dialog";

// The reason a struck-out line needs no guard, opened by clicking its info icon - the same text
// its tooltip shows on hover, for whoever doesn't hover (or uses a touchscreen).
class GuardBoardReasonPopover extends Component {
    static template = "ems.GuardBoardReasonPopover";
    static props = { reason: String, close: Function };
}

const SHIFTS = [
    { key: "morning", label: _t("Morning") },
    { key: "afternoon", label: _t("Afternoon") },
];

// The two ways of reading the same day: the timetable everyone already knows, with whoever is
// away struck through it, and the plain "who is missing / who is on guard" list built from the
// very same payload (see ems.course.get_guard_duty_board_data) - one fetch, two renderings.
const VIEWS = [
    { key: "schedule", label: _t("Guard duty schedule") },
    { key: "table", label: _t("Absences table") },
];

const MS_PER_DAY = 24 * 60 * 60 * 1000;

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
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.popover = useService("popover");
        this.state = useState({
            // Both set in onWillStart, once the server clock is known.
            activeDay: 0,
            activeShift: "morning",
            // Issue #390's level filter: empty = "All levels" (the previous, still-default
            // behaviour) - see guard_duty_board.py's own get_guard_duty_board_lines() docstring.
            activeLevelIds: [],
            levels: [],
            // The Monday the weekday tabs hang off. Absences are keyed to real dates while the
            // timetable is keyed to weekdays, so the board needs a concrete week before it can
            // say who is away - see ems.course.get_guard_duty_board_lines()'s 'day' argument.
            weekStart: "",
            activeView: "schedule",
            board: null,
            loading: true,
            courseId: null,
            courseName: "",
        });
        onWillStart(async () => {
            const [course, levels] = await Promise.all([
                this.orm.call("ems.course", "get_current_course_data", []),
                this.orm.call("ems.course", "get_guard_duty_board_levels", []),
                syncServerClock(this.orm),
            ]);
            const now = serverNow();
            const { day, shift } = getDefaultDayAndShift(now);
            this.state.activeDay = day;
            this.state.activeShift = shift;
            this.state.weekStart = toIsoDate(mondayOf(fromIsoDate(now.toISODate())));
            this.state.courseId = course.id;
            this.state.courseName = course.name;
            this.state.levels = levels;
            await this.loadBoard();
        });
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

    get coveredTitle() {
        return _t("Co-taught: another teacher is in the class, no guard needed");
    }

    // Compact label for the level dropdown's own toggle button - the full checkbox list already
    // shows every level by name, this is just what's visible before opening it.
    get levelFilterLabel() {
        if (!this.state.activeLevelIds.length) {
            return _t("All levels");
        }
        const selected = this.state.levels.filter((level) => this.state.activeLevelIds.includes(level.id));
        return selected.map((level) => level.name).join(", ");
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
    }

    async onShiftChange(ev) {
        const key = ev.target.value;
        if (key === this.state.activeShift) {
            return;
        }
        this.state.activeShift = key;
        await this.loadBoard();
    }

    async toggleLevel(levelId) {
        const activeLevelIds = this.state.activeLevelIds;
        const index = activeLevelIds.indexOf(levelId);
        if (index === -1) {
            activeLevelIds.push(levelId);
        } else {
            activeLevelIds.splice(index, 1);
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
        this.state.board = await this.orm.call(
            "ems.course",
            "get_guard_duty_board_data",
            [String(this.state.activeDay), this.state.activeShift, this.state.activeLevelIds, this.activeDate]
        );
        this.state.loading = false;
    }

    // Bold red for an absence that is going to happen, a lighter italic for one still waiting
    // on its approver - the planner has to be able to tell a fact from a warning at a glance.
    absenceClass(absence) {
        if (absence === "approved") {
            return "o_guard_board_absent";
        }
        return absence === "pending" ? "o_guard_board_absent_pending" : "";
    }

    // Managing absences from the absences table (issues #539, #571, #581). Every action below
    // is checked again on the server (ems.absence_cover.board_assign/board_release,
    // ems.notice.board_propose_absence_change): the flags the board sends only decide what is
    // offered, never what is allowed.

    get actionLabels() {
        return {
            proposalsTitle: _t("Late entry / early leave proposals"),
            proposalsHelp: _t("Sending the notice strikes these lessons off the table, so no guard teacher has to cover them. You can choose a shorter change and send a guard to the rest."),
            releasesTitle: _t("Guards no longer needed"),
            propose: _t("Propose notice"),
            rectify: _t("Propose correction"),
            openDraft: _t("Open draft"),
            release: _t("Release guard"),
        };
    }

    // A row nobody needs to be sent to anymore is struck out: a co-teacher is in the class, a
    // guard has been assigned (the row then takes that guard's colour), or the families were told
    // the students can stay at home for it.
    absenceRowClass(absence) {
        const classes = {
            o_guard_board_absence_covered: absence.covered,
            o_guard_board_absence_struck: !absence.covered && Boolean(absence.cover || absence.authorized),
            o_guard_board_absence_manageable: this.isAssignable(absence),
        };
        if (absence.cover) {
            classes[`o_guard_board_cover_${absence.cover.color}`] = true;
        }
        return classes;
    }

    absenceRowTitle(absence) {
        return this.isAssignable(absence) ? _t("Click to send a guard teacher to this class") : false;
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
        if (absence.cover) {
            return _t("Covered by %s, the guard teacher sent to this class.", absence.cover.guard);
        }
        return false;
    }

    showStruckReason(ev, absence) {
        this.popover.add(ev.currentTarget, GuardBoardReasonPopover, { reason: this.struckReason(absence) });
    }

    // A co-taught class or one the families were told about needs nobody, so it offers nothing.
    isAssignable(absence) {
        return absence.can_manage && !absence.covered && !absence.authorized;
    }

    guardBadgeClass(guard) {
        const base = this.absenceClass(guard.absence);
        return guard.color === false ? base : `${base} o_guard_board_cover_${guard.color}`;
    }

    get proposalActions() {
        return this.state.board.actions.filter((action) => action.type !== "obsolete_cover");
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
        return action.type === "rectification" ? "fa fa-exclamation-triangle" : "fa fa-envelope-o";
    }

    actionButtonLabel(action) {
        if (action.type === "obsolete_cover") {
            return this.actionLabels.release;
        }
        if (action.draft_id) {
            return this.actionLabels.openDraft;
        }
        return action.type === "rectification" ? this.actionLabels.rectify : this.actionLabels.propose;
    }

    onAbsenceClick(line, absence) {
        if (!this.isAssignable(absence)) {
            return;
        }
        this.dialog.add(GuardCoverDialog, {
            row: absence,
            line,
            onAssign: async (guardId, message) => {
                await this.orm.call("ems.absence_cover", "board_assign", [
                    this.activeDate, line.hour_from, line.hour_to, absence.teacher_id, absence.group_id,
                    guardId, message,
                ]);
                await this.loadBoard();
            },
            onRelease: async () => {
                await this.orm.call("ems.absence_cover", "board_release", [absence.cover.id]);
                await this.loadBoard();
            },
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
        const option = action.options[action.default];
        const notice = await this.orm.call("ems.notice", "board_propose_absence_change", [
            this.activeDate, action.group_id, option.change_type, option.hour,
        ]);
        await this.actionService.doAction(notice);
    }

    // One PDF per day AND per shift — whichever day tab / shift dropdown is currently active,
    // not the whole week or both shifts — see reports/attendance/report_guard_duty_board.xml's
    // own use of the 'guard_duty_weekday'/'guard_duty_shift' context keys. 'guard_duty_level_ids'
    // (issue #390) forwards the same level selection, following the same pattern; 'guard_duty_date'
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
                guard_duty_level_ids: this.state.activeLevelIds,
                guard_duty_date: this.activeDate,
                guard_duty_view: this.state.activeView,
            },
        });
    }
}

registry.category("actions").add("ems_guard_duty_board", GuardDutyBoard);
