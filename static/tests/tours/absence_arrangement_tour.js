/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issues #605 and #645, as the absent teacher's Department Chief: the board proposes how the group's
// teachers could rearrange their lessons, as plans of steps. Proposal 1 swaps the 8:00 lesson, moves
// the group's last lesson into the 9:00 one and has the absent teacher, in from 10:00, teach their
// 9:00 lesson at 12:00 instead: nobody loses a lesson. The planner keeps all but that last step:
// both lessons are solved at once, and the lesson left free at 12:00 becomes a class to cover, with
// the early leave proposed. Applying it sends the notice to the group's students about the lessons
// that change time (issues #649, #652); the group has no students, so it cannot be sent and opens as
// a draft to review. ems_absence_arrangement_result then checks the board. Seed data comes from
// TestAbsenceCoverageTour.test_absence_arrangement_tour.
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
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_step:contains('Tour Swap Teacher teaches at 08:00') input:checked",
            content: "Proposal 1 starts with the swap, checked",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_step:contains('Tour Move Teacher moves their 12:00 lesson to 09:00') input:checked",
            content: "...then the move into the 9:00 lesson",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_step:contains('Tour Absent Teacher moves their 09:00 lesson to 12:00') input:checked",
            content: "...and the absent teacher's 9:00 lesson at 12:00: keep all but this one",
            run: "click",
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_step:contains('Tour Absent Teacher moves') input:not(:checked)",
            content: "It is unchecked",
        },
        {
            // Issue #647: the button sits on the right, in the same column and with the same width
            // as the buttons of the proposal rows ("Propose notice"...), not under the steps.
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_actions .o_guard_board_plan_apply.o_guard_board_action_button",
            content: "The apply button is right-aligned, lined up with the other action buttons",
            run: () => {
                const box = document.querySelector(".o_guard_board_arrangements");
                const apply = box.querySelector(".o_guard_board_plan_apply").getBoundingClientRect();
                const plan = box.querySelector(".o_guard_board_plan_apply").closest(".o_guard_board_plan").getBoundingClientRect();
                if (Math.abs(apply.right - plan.right) > 1) {
                    throw new Error(`The apply button ends at ${apply.right}px, its proposal at ${plan.right}px`);
                }
                for (const button of box.querySelectorAll(".o_guard_board_action_button")) {
                    const other = button.getBoundingClientRect();
                    if (Math.abs(other.right - apply.right) > 1 || Math.abs(other.width - apply.width) > 1) {
                        throw new Error(`"${button.textContent.trim()}" is not lined up with the apply button`);
                    }
                }
            },
        },
        {
            trigger: ".o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_apply",
            content: "Apply the checked steps",
            run: "click",
        },
        {
            trigger: ".modal:has(.modal-title:contains('Working day changes')):contains('Tour Move Teacher comes in at 09:00 instead of 12:00.'):contains('Have you talked to Tour Swap Teacher and Tour Move Teacher?') .modal-footer .btn-secondary",
            content: "Their entry and exit times change: the board asks whether they agreed (issue #709). Not yet",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_guard_board_arrangements .o_guard_board_plan:has(.o_guard_board_plan_title:contains('Proposal 1:')) .o_guard_board_plan_apply",
            content: "Nothing was applied: the proposal is still there. Apply it again",
            run: "click",
        },
        {
            trigger: ".modal:has(.modal-title:contains('Working day changes')) .modal-footer .btn-primary",
            content: "Confirm the teachers whose working day changes agreed (issue #709)",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('Lessons moved by an arrangement'):contains('TABTG')",
            content: "The draft notice to the group's students opens: no families' notice is needed",
        },
    ],
});

// Issues #605 and #645: the board once ems_absence_arrangement has applied its steps. Seed data
// comes from TestAbsenceCoverageTour.test_absence_arrangement_tour.
registry.category("web_tour.tours").add("ems_absence_arrangement_result", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_absence_struck:has(.o_guard_board_arrangement_tag:contains('Tour Swap Teacher'))",
            content: "The 8:00 lesson is struck out, with the teacher who is with the group",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_struck:has(.o_guard_board_arrangement_tag:contains('Tour Move Teacher'))",
            content: "So is the 9:00 one",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('12:00-13:00')) .o_guard_board_absence_manageable:contains('Tour Move Teacher') .o_guard_board_moved_tag:contains('Lesson moved to 09:00')",
            content: "The lesson left free at 12:00 is a class to cover",
        },
        {
            trigger: ".o_guard_board_notice_plan .o_guard_board_action:contains('TABTG'):contains('Could leave at 12:00')",
            content: "...and the families can still be told the group leaves at 12:00",
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

// Issues #605 and #645, from the 9:00 lesson's own dialog: the plan that solves it comes first,
// already chosen with every step checked; applying it sends the notice for the families (issue
// #652), which the move into the 9:00 lesson waits for: the group has no students, so it cannot be
// sent and opens as a draft to review. Seed data comes from
// TestAbsenceCoverageTour.test_absence_arrangement_dialog_tour.
registry.category("web_tour.tours").add("ems_absence_arrangement_dialog", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the 9:00 lesson",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_option:has(input[type=radio]:checked) .o_guard_board_plan_step:contains('Tour Move Teacher moves their 12:00 lesson to 09:00') input:checked:enabled",
            content: "The plan that solves it is chosen, every step checked",
        },
        {
            trigger: ".o_guard_cover_option:has(input[type=radio]:checked) .o_guard_board_plan_step:contains('Notice to the families'):contains('Leaves at 11:00') input:checked",
            content: "...the notice for the families included",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Apply it",
            run: "click",
        },
        {
            trigger: ".modal:has(.modal-title:contains('Working day changes')) .modal-footer .btn-primary",
            content: "Confirm the teachers whose working day changes agreed (issue #709)",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('TABTG')",
            content: "The notice for the families opens: the move only counts once it is sent",
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

// Issue #678, as the absent teacher's Department Chief: the 12:00 lesson is co-taught and one of
// its teachers has another class at 9:00. The plan moves it with the other teacher and warns that
// this one stays on guard; applied without the notice to the families, they show in the guard
// column at 12:00. Seed data comes from TestAbsenceCoverageTour.test_absence_arrangement_co_teaching_tour.
registry.category("web_tour.tours").add("ems_absence_arrangement_co_teaching", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the 9:00 lesson",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_option:has(input[type=radio]:checked) .o_guard_board_plan_step:contains('Tour Move Teacher moves their 12:00 lesson to 09:00'):contains('Tour Co-Teacher cannot follow the lesson (busy then): on guard at 12:00 instead.')",
            content: "The step warns that the co-teacher who cannot follow the lesson stays on guard",
        },
        {
            trigger: ".o_guard_cover_option:has(input[type=radio]:checked) .o_guard_board_plan_step:contains('Notice to the families') input:checked",
            content: "Leave the notice to the families out",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_option:has(input[type=radio]:checked) .o_guard_board_plan_step:contains('Notice to the families') input:not(:checked)",
            content: "The notice is unchecked",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Apply the move",
            run: "click",
        },
        {
            trigger: ".modal:has(.modal-title:contains('Working day changes')) .modal-footer .btn-primary",
            content: "Confirm the teachers whose working day changes agreed (issue #709)",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids']:contains('TABTG')",
            content: "The students' notice opens: the group has no students to send it to",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb li.breadcrumb-item:first-child a",
            content: "Back to the board",
            run: "click",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('12:00-13:00')) .o_guard_board_guard_badge:contains('Tour Co-Teacher'):contains('lesson moved')",
            content: "The co-teacher is on guard at 12:00, tagged",
        },
    ],
});
