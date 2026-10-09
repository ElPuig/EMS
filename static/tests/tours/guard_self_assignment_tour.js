/** @odoo-module **/

import { registry } from "@web/core/registry";

// A teacher on guard duty takes next Monday's free classes themselves from the guard duty board's
// absences table (issue #601): covers the first one, changes their mind and leaves it, then covers
// the second one. They manage nobody's absences, so the board offers them nothing else. Seed data
// comes from TestAbsenceCoverageTour.test_guard_self_assignment_tour.
const firstLesson = "tr:has(.o_guard_board_time:contains('08:00-09:00'))";
const secondLesson = "tr:has(.o_guard_board_time:contains('09:00-10:00'))";

registry.category("web_tour.tours").add("ems_guard_self_assignment", {
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
            trigger: `${firstLesson} .o_guard_board_absence_manageable:contains('Tour Absent Teacher')`,
            content: "The free first lesson can be taken",
            run: () => {
                if (document.querySelector(".o_guard_board_action")) {
                    throw new Error("A guard who manages nobody's absences must not get the pending actions");
                }
            },
        },
        {
            trigger: `${firstLesson} .o_guard_board_absence_manageable:contains('Tour Absent Teacher')`,
            content: "Take the first lesson",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: `${firstLesson} .o_guard_board_absence_struck:contains('Tour Self Guard')`,
            content: "The lesson is now struck out with the guard's name",
            run: "click",
        },
        {
            trigger: ".o_guard_board_reason_action",
            content: "Leave the lesson again",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: `${firstLesson} .o_guard_board_absence_row:not(.o_guard_board_absence_struck):contains('Tour Absent Teacher')`,
            content: "The first lesson is free again",
        },
        {
            trigger: `${secondLesson} .o_guard_board_absence_manageable:contains('Tour Absent Teacher')`,
            content: "Take the second lesson",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: `${secondLesson} .o_guard_board_absence_struck:contains('Tour Self Guard')`,
            content: "The second lesson is covered by the guard",
        },
    ],
});
