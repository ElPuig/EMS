/** @odoo-module **/

import { registry } from "@web/core/registry";

// Manages next Monday's absences from the guard duty board's absences table as the absent
// teacher's Department Chief (issues #539, #571, #581): sends the guard on duty to the second of
// the two lessons left without a teacher (the row takes the guard's colour and is struck out),
// sees the timetable change the remaining empty first lesson allows, and proposes it, landing on
// its draft notice. Seed data comes from TestAbsenceCoverageTour (tests/test_absence_coverage_tour.py).
registry.category("web_tour.tours").add("ems_absence_coverage", {
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
            trigger: ".o_guard_board_action:contains('TABTG'):contains('Could start at 10:00') .o_guard_board_action_button",
            content: "Both empty first lessons let the group start at 10:00",
        },
        {
            trigger: ".o_guard_board_proposals .o_guard_board_actions_help",
            content: "The proposals box explains that sending the notice strikes the lessons off",
        },
        {
            trigger: ".o_guard_board_action:contains('TABTG') .o_guard_board_action_option",
            content: "A shorter change (only an hour late) can be chosen too, the full one by default",
            run: () => {
                const select = document.querySelector(".o_guard_board_action_option");
                const labels = [...select.options].map((option) => option.textContent.trim());
                if (labels.join("|") !== "Starts at 09:00|Starts at 10:00" || select.selectedIndex !== 1) {
                    throw new Error(`Unexpected options ${labels} (selected ${select.selectedIndex})`);
                }
            },
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the second lesson to send a guard",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_guard_select",
            content: "Only the guard on duty is offered",
            run: "selectByLabel Tour Cover Guard",
        },
        {
            trigger: ".o_guard_cover_message",
            content: "Write what the students have to do",
            run: "edit Exercises on page 12",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Assign and notify",
            run: "click",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('09:00-10:00')) .o_guard_board_absence_struck.o_guard_board_cover_0:contains('Tour Cover Guard')",
            content: "The covered lesson is struck out in the guard's colour",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('09:00-10:00')) .o_guard_board_guard_badge.o_guard_board_cover_0:contains('Tour Cover Guard')",
            content: "The guard shares that colour",
        },
        {
            trigger: ".o_guard_board_action:contains('TABTG'):contains('Could start at 09:00') .o_guard_board_action_button",
            content: "With a guard in the second lesson, only the first one can be skipped now",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('TABTG')",
            content: "The draft notice says it is a timetable change for the group",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids']:contains('TABTG')",
            content: "Addressed to that group",
        },
    ],
});
