/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #725, as the Department Chief of the department that manages the group's study: from the
// guard column of next Monday's absences table, sends the guard on duty to support the teacher
// of TABTG at 08:00 (who is in), sees the guard struck out as busy and the support on the
// timetable, then removes it. Seed data comes from TestAbsenceCoverageTour.test_guard_support_tour.
const guardBadge = "td.o_guard_board_guard_cell:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_guard_badge:contains('Tour Cover Guard')";

registry.category("web_tour.tours").add("ems_guard_support", {
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
            trigger: ".o_guard_board_view_tabs .nav-item:nth-child(1) .nav-link",
            content: "Switch to the absences table",
            run: "click",
        },
        {
            trigger: `${guardBadge}.o_guard_board_guard_supportable`,
            content: "The guard on duty can be sent as a support",
            run: "click",
        },
        {
            trigger: ".o_guard_support_option:contains('TABTG'):contains('Tour Absent Teacher') input:checked",
            content: "The only class with its teacher in is offered, already chosen",
        },
        {
            trigger: ".o_guard_support_message",
            content: "Say what the support is for",
            run: "edit Help with the practical",
        },
        {
            trigger: ".o_guard_support_send:enabled",
            content: "Send and notify",
            run: "click",
        },
        {
            trigger: `${guardBadge}.o_guard_board_guard_busy`,
            content: "The guard is busy: struck out of the guard column",
        },
        {
            trigger: ".o_guard_board_view_tabs .nav-item:nth-child(2) .nav-link",
            content: "Back to the timetable",
            run: "click",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_cell_support:contains('Tour Cover Guard')",
            content: "The class shows its support",
        },
        {
            trigger: ".o_guard_board_view_tabs .nav-item:nth-child(1) .nav-link",
            content: "Absences table again",
            run: "click",
        },
        {
            trigger: `${guardBadge}.o_guard_board_guard_busy`,
            content: "Open the guard's support",
            run: "click",
        },
        {
            trigger: ".o_guard_support_current:contains('TABTG') .o_guard_support_remove",
            content: "Remove the support",
            run: "click",
        },
        {
            trigger: `${guardBadge}.o_guard_board_guard_supportable:not(.o_guard_board_guard_busy)`,
            content: "The guard is free again",
        },
    ],
});
