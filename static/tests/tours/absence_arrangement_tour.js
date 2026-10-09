/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #605, as the absent teacher's Department Chief: resolves next Monday's two lessons left
// without a teacher with internal arrangements instead of guards. The guard on duty takes the
// first one (the row is struck out and the guard is struck out of the guard column, so nobody asks
// them to cover anything else); a teacher of the group moves their last lesson forward to the
// second one, which lets the group leave earlier, so saving it opens the notice for the families.
// Seed data comes from TestAbsenceCoverageTour.test_absence_arrangement_tour.
function chooseOption(selector, text) {
    const select = document.querySelector(selector);
    const option = [...select.options].find((candidate) => candidate.textContent.includes(text));
    if (!option) {
        throw new Error(`No option containing "${text}" in ${selector}`);
    }
    select.value = option.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
}

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
            trigger: "tr:has(.o_guard_board_time:contains('08:00-09:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the first lesson",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_mode_arrangement",
            content: "No guard needed: internal arrangement",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_teacher_select:has(option:contains('Tour Cover Guard (on guard duty)'))",
            content: "The guard on duty is offered, flagged as such",
            run: () => chooseOption(".o_guard_cover_teacher_select", "Tour Cover Guard"),
        },
        {
            trigger: ".o_guard_cover_note",
            content: "Describe the movement",
            run: "edit The guard teaches them instead",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Save the arrangement",
            run: "click",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('08:00-09:00')) .o_guard_board_absence_struck:has(.o_guard_board_arrangement_tag:contains('Tour Cover Guard'))",
            content: "The lesson is struck out, with the teacher who is with the group",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('08:00-09:00')) .o_guard_board_guard_badge.o_guard_board_guard_busy:contains('Tour Cover Guard')",
            content: "The guard is struck out of the guard column: they cannot cover anything else then",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('09:00-10:00')) .o_guard_board_guard_badge:not(.o_guard_board_guard_busy):contains('Tour Cover Guard')",
            content: "Only in that period: at 9 they are on guard duty as usual",
        },
        {
            trigger: "tr:has(.o_guard_board_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the second lesson",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_mode_arrangement",
            content: "No guard needed: internal arrangement",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_teacher_select:has(option:contains('Tour Swap Teacher (teaches this group)'))",
            content: "A teacher of the group, who moves their 11:00 lesson forward",
            run: () => chooseOption(".o_guard_cover_teacher_select", "Tour Swap Teacher"),
        },
        {
            trigger: ".o_guard_cover_vacated_select",
            content: "Their 11:00 lesson is left free",
            run: () => chooseOption(".o_guard_cover_vacated_select", "11:00-12:00"),
        },
        {
            trigger: ".o_guard_cover_note",
            content: "Describe the movement",
            run: "edit The 11:00 lesson moves to 9:00",
        },
        {
            trigger: ".o_guard_cover_assign:enabled",
            content: "Save the arrangement",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('TABTG')",
            content: "The notice for the families opens: the arrangement only counts once it is sent",
        },
    ],
});
