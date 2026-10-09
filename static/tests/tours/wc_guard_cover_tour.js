/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #606: next Monday the WC guard is away, so their guard duty is one more row of the guard
// duty board's absences table, and the absent teacher's Department Chief sends the regular guard
// on duty to it. Seed data comes from TestAbsenceCoverageTour.test_wc_guard_cover_tour
// (tests/test_absence_coverage_tour.py).
registry.category("web_tour.tours").add("ems_wc_guard_cover", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        {
            trigger: ".o_guard_board_week_nav button:last-child",
            content: "Move to next week",
            run: "click",
        },
        {
            trigger: ".o_guard_board_tabs .nav-link:contains('Monday')",
            content: "Open Monday",
            run: "click",
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "Morning shift",
            run: "selectByLabel Morning",
        },
        {
            trigger: ".o_guard_board_view_tabs .nav-link:contains('Absences table')",
            content: "Switch to the absences table",
            run: "click",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('08:00-09:00')) .o_guard_board_absence_manageable:contains('Tour WC Guard'):contains('Guard (WC)')",
            content: "The absent WC guard's duty needs covering: open it to send a guard",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_guard_select",
            content: "Only the regular guard on duty is offered",
            run: "selectByLabel Tour Cover Guard (0 covered this course)",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Assign and notify",
            run: "click",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('08:00-09:00')) .o_guard_board_absence_struck.o_guard_board_cover_0:contains('Tour WC Guard'):contains('Tour Cover Guard')",
            content: "The covered guard duty is struck out in the guard's colour",
        },
    ],
});
