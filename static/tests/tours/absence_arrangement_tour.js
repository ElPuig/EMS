/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #605, as the absent teacher's Department Chief: the board proposes how the group's teachers
// could rearrange their lessons so that no guard is needed. The 8:00 lesson is solved by applying
// the swap from the possible arrangements box (struck out at once, and shown in the timetable); the
// 9:00 one, from its own dialog, by moving the group's last lesson forward, which opens the notice
// for the families. Seed data comes from TestAbsenceCoverageTour.test_absence_arrangement_tour.
registry.category("web_tour.tours").add("ems_absence_arrangement", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_options_tag",
            content: "The empty lesson says there are possible arrangements",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_action:contains('08:00-09:00'):contains('Swap: Tour Swap Teacher') .o_guard_board_action_button",
            content: "The swap comes first: the students lose no lesson",
            run: "click",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_absence_struck:has(.o_guard_board_arrangement_tag:contains('Tour Swap Teacher'))",
            content: "The lesson is struck out, with the teacher who is with the group",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the 9:00 lesson",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_option label:contains('Tour Move Teacher moves their 12:00 lesson')",
            content: "Its possible arrangements are offered in the dialog, with the notice they need",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_option:has(input:checked) label:contains('The families will be told')",
            content: "Chosen: it says the families will be told",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Apply it",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('TABTG')",
            content: "The notice for the families opens: the arrangement only counts once it is sent",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb li.breadcrumb-item:first-child a",
            content: "Back to the board",
            run: "click",
        },
        {
            trigger: ".o_guard_board_view_tabs .nav-link:contains('Guard duty schedule')",
            content: "Switch to the timetable",
            run: "click",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('11:00-12:00')) .o_guard_board_guard_busy:contains('Tour Swap Teacher')",
            content: "At 11 the swap teacher's lesson is struck out...",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('11:00-12:00')) .o_guard_board_cell_substitute:contains('Tour Absent Teacher')",
            content: "...and the absent teacher teaches it instead",
        },
    ],
});

// Issue #623, as the absent teacher's Department Chief: a lesson moved into the empty 9:00 class,
// whose notice the families already got, shows both who teaches it and that the group leaves
// earlier because of it. Seed data comes from
// TestAbsenceCoverageTour.test_absence_arrangement_change_tour.
registry.category("web_tour.tours").add("ems_absence_arrangement_change", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_struck:has(.o_guard_board_arrangement_tag:contains('Tour Move Teacher')) .o_guard_board_arrangement_change_tag:contains('Leaves at 11:00')",
            content: "The 9:00 class says who teaches it and that the group leaves at 11:00",
        },
    ],
});
