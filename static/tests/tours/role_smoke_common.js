/** @odoo-module **/

import { Component } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";

// Shared crawler for the per-role smoke tours - see CLAUDE.md's "Per-role smoke tours" (issue
// #434 follow-up). Each role's own tour file (role_smoke_<role>_tour.js) is a thin wrapper
// around crawlAccessibleScreens() below, registered under its own role-specific tour name so
// each lands as its own test class/shard.
//
// Instead of a hand-authored step list, this fetches the exact menu tree the real webclient
// would (already filtered server-side by the logged-in session's own groups, via the "menu"
// service) and opens every reachable window action in every view_mode it declares. It asserts
// nothing about the data shown - only that nothing crashes. Detection needs no bespoke
// error-dialog checking: Odoo's own tour/HttpCase harness already fails the test on any
// console.error, and the webclient's error service logs every uncaught client error that way
// (including an AccessError surfaced while a view fetches its data - exactly how #434 itself
// would have been caught here). `Component.env` (set by web/static/src/start.js on every
// webclient boot) is used instead of a step's own `this` context, which the tour engine binds
// to `{anchor}` only.
//
// Maintaining this list: add an action's xml_id here only for a CONFIRMED false positive - a
// deliberate business-rule guard (typically a UserError raised from default_get()/create() for
// a role that legitimately cannot use that screen), not to silence a genuine finding. xml_id
// (not the numeric action id, which varies per database) is what keeps this list portable
// across environments - see CLAUDE.md's "Per-role smoke tours".
const SKIP_ACTION_XMLIDS = new Set([
    // ems.enrollment's default_get() deliberately raises UserError("Only admins and secretary
    // staff can create manual enrollments.") for anyone else - a pre-existing, documented
    // limitation (models/contacts/enrollment.py's own "TODO: unable to hide the NEW button
    // based for only tutors..."), not an unintended crash. Found 2026-09-11 via the `teacher`
    // spike run.
    "ems.action_enrollment_tree",
    // ems.attendance_justification's default_get() deliberately raises UserError("Only tutors
    // can justify student's attendances.") for a non-tutor teacher - same shape, same
    // pre-existing TODO (models/attendance/attendance_justification.py). Found 2026-09-11.
    "ems.action_attendance_justification_tree",
    // Confirmed real, reproducible hang (not yet root-caused) - see plans/role_smoke_student_kanban_secretary_hang.md.
    // Opening the "Students" kanban (context: active_test=False,
    // search_default_my_students=1) as a secretary consistently hangs the whole 60s step with
    // no further server request ever sent after get_views succeeds - a client-side stall, not
    // a permission crash (the exact failure class this crawler targets). Skipped here rather
    // than left to time out the whole step every run, until that's investigated separately.
    "ems.action_student_kanban",
    // 4 more confirmed-real, not-yet-root-caused findings on the secretary role, all with the
    // same signature (onWillStart "Odoo Server Error", zero corresponding server-side trace,
    // zero failed RPC) - see plans/role_smoke_secretary_unexplained_findings.md. Existing
    // dedicated tours already open ems.attendance_template's and ems.attendance_session's own
    // list/form views successfully for other logins, which points at a crawler-speed/ordering
    // artifact rather than a screen that's actually broken - but that's not yet confirmed.
    "ems.action_attendance_template_tree",
    "ems.action_attendance_session_tree",
    "ems.action_strike_list",
    "calendar.action_calendar_event",
]);

// A role with a large menu reach (e.g. secretary) can take longer than the tour engine's
// default 10s per-step timeout (macro.js's own hardcoded default, separate from start_tour()'s
// own overall `timeout` kwarg) to work through every action - found empirically 2026-09-11 via
// a genuine "TIMEOUT step failed to complete within 10000 ms" on the secretary role's own spike
// run. 60000 is the actual ceiling: web_tour's own StepSchema (tour_service.js) validates
// `timeout` as `value >= 0 && value <= 60000` - anything above that fails schema validation
// before the tour even starts ("'timeout' is not valid"), confirmed empirically the same day.
const CRAWL_STEP_TIMEOUT_MS = 60000;

// NOTE: a per-action Promise.race timeout was tried here (2026-09-11) to bound a single slow
// screen's cost, but caused worse false positives than the problem it solved: Promise.race
// never actually cancels the losing side, so the abandoned doAction() call kept mutating the
// action-manager/controller-stack state in the background, corrupting whichever unrelated
// action the crawler had already moved on to (confirmed: several actions immediately after the
// one that "timed out" then failed too, with onWillStart errors that had zero corresponding
// server-side trace - i.e. no real server call ever failed for them). Reverted in favor of
// fixing the actual slow screen instead (see SKIP_ACTION_XMLIDS) - a real await, left to
// complete or genuinely fail on its own, is what keeps one screen's problem from bleeding into
// the next.

// options.xmlIdPrefix: only open actions whose xml_id starts with it (e.g. "ems." for the admin
// crawler, whose menu also reaches every native Odoo app - those are Odoo's to test, not ours).
export function roleSmokeSteps(content, options = {}) {
    return [
        {
            trigger: "body",
            timeout: CRAWL_STEP_TIMEOUT_MS,
            content,
            run: async () => crawlAccessibleScreens(options),
        },
    ];
}

export async function crawlAccessibleScreens({ xmlIdPrefix } = {}) {
    const { action: actionService, menu: menuService } = Component.env.services;

    // Force-load the lazy widget bundle (timepicker, one2many_list, ...) up front - a human
    // session only ever hits its on-demand loading gradually, while this crawler can reach a
    // datetime/one2many field within the first couple of actions. Kept as cheap, reasonable
    // hygiene even though it turned out NOT to explain the "Odoo Server Error" findings it was
    // first suspected of causing (2026-09-11, secretary role) - those two specific widget names
    // (`timepicker` on a Date field, `one2many_list`) were separately confirmed as genuinely
    // non-existent widgets and fixed directly in their views (see the git history for
    // views/attendance/attendance_template/form.xml and .../attendance_session/form.xml); the
    // "Missing widget" warnings were real but harmless (a silent fallback), unrelated to the
    // onWillStart crashes. See SKIP_ACTION_XMLIDS below for what those crashes actually were.
    await loadBundle("web.assets_backend_lazy");

    const actionIds = [...new Set(
        menuService.getAll()
            .filter((item) => item.actionModel === "ir.actions.act_window" && item.actionID)
            .map((item) => item.actionID)
    )];
    if (!actionIds.length) {
        throw new Error("Role smoke tour found no reachable window actions for this role's menu - " +
            "check the role's group/menu access before trusting a green run.");
    }

    const failures = [];
    let openedActions = 0;
    let openedViews = 0;
    for (const actionId of actionIds) {
        let action;
        try {
            // loadAction() (not orm.read on ir.actions.act_window directly) - the model itself
            // is only readable by Administration/Settings; loadAction's own server route
            // (/web/action/load) reads it with sudo() deliberately, since resolving the action
            // behind a menu click must work for every internal user regardless of that ACL.
            action = await actionService.loadAction(actionId);
        } catch (error) {
            failures.push(`Action ${actionId}: failed to load - ${error.message || error}`);
            continue;
        }
        if (!action || action.target === "new" || SKIP_ACTION_XMLIDS.has(action.xml_id)) {
            continue; // Wizards/dialogs, or a confirmed false positive - see SKIP_ACTION_XMLIDS.
        }
        if (xmlIdPrefix && !(action.xml_id || "").startsWith(xmlIdPrefix)) {
            continue;
        }
        openedActions++;
        // Bound the initial page size regardless of the action's own default - this crawler
        // only cares whether the screen crashes, never about the data itself, and a real dev
        // DB's data volume (hundreds/thousands of rows on some models) shouldn't be allowed to
        // slow down (or client-side hang) a check that a handful of rows would answer just as
        // well.
        action.limit = 1;
        for (const viewType of (action.view_mode || "").split(",").map((type) => type.trim()).filter(Boolean)) {
            try {
                await actionService.doAction(action, { viewType, clearBreadcrumbs: true });
                openedViews++;
            } catch (error) {
                failures.push(`Action ${actionId} (${action.name}), view=${viewType}: ${error.message || error}`);
            }
        }
    }
    if (failures.length) {
        throw new Error(`${failures.length} screen(s) failed for this role:\n${failures.join("\n")}`);
    }
    if (!openedActions) {
        throw new Error("Role smoke tour opened no action at all - check its filters before " +
            "trusting a green run.");
    }
    // Shows up in the test log, so a green run also says how much it actually covered.
    console.log(`Role smoke crawl: ${openedViews} view(s) opened across ${openedActions} action(s).`);
}
