/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #660, as the absent teacher's Department Chief: TABTG and TABTH are the two halves of a
// split group. The board proposes joining TABTH to the lesson Tour Join Teacher gives TABTG at 9:00,
// so that its 12:00 lesson is left free and both halves leave at 12:00. Applying it opens the first
// families' notice left in draft (the groups have no students). Seed data comes from
// TestAbsenceCoverageTour.test_join_split_groups_tour.
const openMonday = [
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
];

registry.category("web_tour.tours").add("ems_join_split_groups", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        ...openMonday,
        {
            trigger: ".o_guard_board_view_tabs .nav-link:contains('Absences table')",
            content: "Switch to the absences table",
            run: "click",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan_step:contains('Joined groups: Tour Join Teacher teaches TABT1TABTH together with TABT1TABTG at 09:00, instead of at 12:00') input:checked",
            content: "The proposal joins the two halves at 9:00, checked",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_step:contains('Tour Join Teacher teaches TABT1TABTH together with TABT1TABTG at 09:00')):not(:has(.o_guard_board_plan_step:contains('moves their'))) .o_guard_board_plan_step:contains('TABTG'):contains('TABTH'):contains('12:00') input:checked",
            content: "...and tells the families of both halves they leave at 12:00",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_step:contains('Tour Join Teacher teaches TABT1TABTH together with TABT1TABTG at 09:00')):not(:has(.o_guard_board_plan_step:contains('moves their'))) .o_guard_board_plan_apply",
            content: "Apply the checked steps",
            run: "click",
        },
        {
            trigger: ".modal:has(.modal-title:contains('Working day changes')) .modal-footer .btn-primary",
            content: "Confirm the teachers whose working day changes agreed (issue #709)",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name=absence_group_id]",
            content: "The families' notice opens as a draft: the halves have no students to send it to",
        },
    ],
});

// Issue #660: the board once the families were told. Seed data comes from
// TestAbsenceCoverageTour.test_join_split_groups_tour.
registry.category("web_tour.tours").add("ems_join_split_groups_result", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        ...openMonday,
        {
            trigger: ".o_guard_board_view_tabs .nav-link:contains('Guard duty schedule')",
            content: "Switch to the timetable",
            run: "click",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_cell_joined:contains('Together with TABT1TABTG')",
            content: "At 9 TABTH is taught together with TABTG...",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_cell_joined:contains('Together with TABT1TABTH')",
            content: "...and TABTG together with TABTH",
        },
    ],
});
