/** @odoo-module **/

import { registry } from "@web/core/registry";

// Manages next Monday's absences from the guard duty board's absences table as the absent
// teacher's Department Chief (issues #539, #571, #581): sends the guard on duty to the second of
// the two lessons left without a teacher (the row takes the guard's colour and is struck out),
// sees the timetable change the remaining empty first lesson allows, and proposes it, landing on
// its draft notice. Seed data comes from TestAbsenceCoverageTour (tests/test_absence_coverage_tour.py).
// The board's URL when the notice was opened, to know when the form has replaced it.
let boardUrl = "";

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
            trigger: ".o_guard_board_notice_step:contains('TABTG'):contains('Could start at 10:00') .o_guard_board_plan_check:checked",
            content: "Both empty first lessons let the group start at 10:00, a step checked by default",
        },
        {
            trigger: ".o_guard_board_section:contains('TABTG') .o_guard_board_notice_plan:contains('Only tell the families') .o_guard_board_action:contains('Could start at 10:00')",
            content: "The change alone is the group's last proposal: only telling the families",
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
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "Open the second lesson to send a guard",
            run: "click",
        },
        {
            trigger: ".o_guard_cover_guard_select",
            content: "Only the guard on duty is offered",
            run: "selectByLabel Tour Cover Guard",
        },
        {
            trigger: ".o_guard_cover_guard_select",
            content: "Each candidate says how many classes they have covered this course (issue #600)",
            run: () => {
                const select = document.querySelector(".o_guard_cover_guard_select");
                const label = select.options[select.selectedIndex].textContent.trim();
                if (label !== "Tour Cover Guard (0 covered this course)") {
                    throw new Error(`Unexpected candidate label ${label}`);
                }
            },
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
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_struck.o_guard_board_cover_0:contains('Tour Cover Guard')",
            content: "The covered lesson is struck out in the guard's colour",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_guard_badge.o_guard_board_cover_0:contains('Tour Cover Guard')",
            content: "The guard shares that colour",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_guard_badge:contains('Tour Cover Guard') .o_guard_board_guard_count:contains('1')",
            content: "Their badge now counts the class they were sent to cover",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_struck:has(.o_guard_board_absence_info)",
            content: "The struck-out line has an info icon; clicking anywhere on the line explains it",
            run: "click",
        },
        {
            trigger: ".o_guard_board_reason_popover:contains('Covered by Tour Cover Guard') .o_guard_board_reason_action",
            content: "Its reason, and for whoever organises the absence a way to change the guard",
        },
        {
            trigger: ".o_guard_board_notice_step:contains('TABTG'):contains('Could start at 09:00') .o_guard_board_plan_check:checked",
            content: "With a guard in the second lesson, only the first one can be skipped now",
        },
        {
            trigger: ".o_guard_board_section:contains('TABTG') .o_guard_board_notices_apply:enabled",
            content: "Tell the families: the group has nobody to send it to, so its draft opens",
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
        // Coming back keeps what the planner was looking at (next Monday, not today), whether
        // through the breadcrumbs or the browser's back button - see navigationState in
        // guard_duty_board.js.
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb li.breadcrumb-item:first-child a",
            content: "Back to the board through the breadcrumbs",
            run: "click",
        },
        {
            trigger: ".o_guard_board_action:contains('TABTG') .o_guard_board_action_button",
            content: "The board is back on next Monday's absences table",
            run: () => assertBoardOnNextMonday(),
        },
        {
            trigger: ".o_guard_board_action:contains('TABTG') .o_guard_board_action_button",
            content: "Open the draft notice again",
            run: (helpers) => {
                boardUrl = window.location.href;
                return helpers.click();
            },
        },
        {
            trigger: ".o_form_view .alert-info:contains('TABTG')",
            content: "The draft notice is open",
            // Only once the router has pushed the form's URL: going back any earlier leaves the
            // browser on the form, which then pushes its URL on top of the board's.
            run: async () => {
                while (window.location.href === boardUrl) {
                    await new Promise((resolve) => setTimeout(resolve, 50));
                }
                window.history.back();
            },
        },
        {
            trigger: ".o_guard_board_action:contains('TABTG') .o_guard_board_action_button",
            content: "The browser's back button returns to the same day too",
            run: () => assertBoardOnNextMonday(),
        },
    ],
});

// Next Monday, the day the tour moved the board to - shown on the date input, in the URL, and
// with the absences table active.
function assertBoardOnNextMonday() {
    const value = document.querySelector(".o_guard_board_date_input").value;
    const picked = new Date(value + "T00:00:00");
    const days = (picked - new Date(new Date().toDateString())) / 86400000;
    if (picked.getDay() !== 1 || days < 1 || days > 7) {
        throw new Error(`Expected next Monday on the board, got ${value}`);
    }
    if (!window.location.search.includes(`date=${value}`)) {
        throw new Error(`The URL does not keep the date: ${window.location.href}`);
    }
    if (!document.querySelector(".o_guard_board_view_tabs .nav-link.active")?.textContent.includes("Absences table")) {
        throw new Error("Expected the absences table to be the active view");
    }
}

// Issue #659: the families were told group TABTG starts at 10:00 next Monday. From the struck-out
// 8:00 row, its Department Chief sees the arrangements that could replace it (each correcting the
// notice) and changes it to 9:00 with one correction; the 9:00 lesson then needs a guard again. Seed data comes from TestAbsenceCoverageTour.test_change_proposal_tour.
registry.category("web_tour.tours").add("ems_change_proposal", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_absence_struck:contains('Starts at 10:00') .o_guard_board_change_proposal",
            content: "The struck-out row offers to change what the families were told",
            run: "click",
        },
        {
            trigger: ".o_guard_change_proposal_dialog:contains('Starts at 10:00')",
            content: "The dialog says what was told",
        },
        {
            trigger: ".o_guard_change_proposal_plan:has(.fa-exchange):has(.fa-exclamation-triangle)",
            content: "It also offers a swap, with the correction to the families among its steps",
        },
        {
            trigger: ".o_guard_change_proposal_dialog .form-check:contains('Starts at 09:00') .o_guard_change_proposal_option",
            content: "Start at 9:00 instead",
            run: "click",
        },
        {
            trigger: ".o_guard_change_proposal_send:enabled",
            content: "Send one correction",
            run: "click",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_absence_struck:contains('Starts at 09:00')",
            content: "The first lesson is now struck out by the new start time",
        },
        {
            trigger: "td:has(.o_guard_board_block_time:contains('09:00-10:00')) .o_guard_board_absence_manageable:contains('Tour Absent Teacher')",
            content: "The second lesson needs a guard again",
        },
    ],
});

// Issue #659: a group whose families were told something that no longer matches the absences is
// in the red corrections box, its correction a step of every proposal; "Only tell the families",
// the new early leave unchecked, sends the correction alone. Seed data comes from
// TestAbsenceCoverageTour.test_corrections_box_tour.
registry.category("web_tour.tours").add("ems_corrections_box", {
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
            trigger: ".o_guard_board_corrections .o_guard_board_section:contains('TABTG') .o_guard_board_notice_step.o_guard_board_action_rectification",
            content: "The group is in the corrections box, its correction a step",
        },
        {
            trigger: ".o_guard_board_corrections .o_guard_board_notice_step.o_guard_board_action_proposal:contains('Could leave') .o_guard_board_plan_check",
            content: "Uncheck the new early leave: only the correction goes out",
            run: "click",
        },
        {
            trigger: ".o_guard_board_corrections .o_guard_board_notices_apply:enabled",
            content: "Apply the checked steps",
            run: "click",
        },
        {
            trigger: ".o_guard_board_arrangements:not(.o_guard_board_corrections) .o_guard_board_section:contains('TABTG')",
            content: "Nothing to correct any more: the group is back with the other proposals",
        },
    ],
});

// Issue #659: a teacher who is not on guard duty sees every class still to be covered answer the
// pointer, saying why they cannot cover it. Seed data comes from
// TestAbsenceCoverageTour.test_not_on_guard_tour.
registry.category("web_tour.tours").add("ems_not_on_guard", {
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
            trigger: "td:has(.o_guard_board_block_time:contains('08:00-09:00')) .o_guard_board_absence_not_on_guard[data-tooltip*='not on guard duty']:contains('Tour Absent Teacher')",
            content: "The class answers the pointer and says why it cannot be covered",
            run: "click",
        },
        {
            trigger: ".o_guard_board_reason_popover:contains('not on guard duty')",
            content: "Clicking it says the same",
        },
    ],
});

// Issue #679: a longer break the students were told about still needs a guard (the ones under 18
// cannot leave the centre), so its lesson shows the break but is not struck out. Seed data comes
// from TestAbsenceCoverageTour.test_absence_long_break_tour.
registry.category("web_tour.tours").add("ems_absence_long_break", {
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
            trigger: ".o_guard_board_absence_row:contains('Tour Absent Teacher'):has(.o_guard_board_break_change_tag):not(.o_guard_board_absence_struck)",
            content: "The lesson shows the longer break and still waits for a guard",
        },
    ],
});
