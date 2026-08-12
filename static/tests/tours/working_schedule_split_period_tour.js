/** @odoo-module **/

import { registry } from "@web/core/registry";

// plans/calendar_driven_attendance_templates.md's "Mid-course subject handoff" refinement: the same
// weekday/time slot can now hold two different subjects across the year, distinguished only by each
// card's own date range. The 2026-08-11 card redesign replaced the earlier shared-row "Split" button
// with independent per-day cards - the same effect is now achieved by adding two cards to the same
// weekday and giving them the exact same time (each card's own start/end time inputs) but different,
// non-overlapping date ranges. Exercises the real interactive flow (add a card, assign it, add a
// second one at the same time, assign it differently, give both their own date range, save) - a clean
// upgrade.sh and passing TransactionCase tests prove none of this on their own, since neither renders
// anything in a real browser.
registry.category("web_tour.tours").add("ems_working_schedule_split_period", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Split Period Tour Teacher')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Enter edit mode",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_add_card",
            content: "Monday: add the first card",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:first-of-type",
            content: "First card: fix its start time to a value the tour fully controls, regardless of the framework's own bell-schedule periods",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:first-of-type"
                );
                input.value = "20:00";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:last-of-type",
            content: "First card: fix its end time",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:last-of-type"
                );
                input.value = "21:00";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_subject",
            content: "First card: pick the first subject",
            run: "selectByLabel Split Tour Subject A",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_group",
            content: "First card: pick the first group",
            run: "selectByLabel Split Tour Group A",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_add_card",
            content: "Monday: add a second card",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:first-of-type",
            content: "Second card: same start time as the first (the actual mid-course-handoff mechanism - same slot, different dates)",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:first-of-type"
                );
                input.value = "20:00";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:last-of-type",
            content: "Second card: same end time as the first",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:last-of-type"
                );
                input.value = "21:00";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_subject",
            content: "Second card: pick the second subject",
            run: "selectByLabel Split Tour Subject B",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_group",
            content: "Second card: pick the second group",
            run: "selectByLabel Split Tour Group B",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card_group:not(:disabled)",
            content: "Give each card its own date range - looked up by which subject it currently holds, not by DOM position, since a card can legitimately swap position with its sibling the moment it gets a start date (cards with a tied time sort by date, per the developer's own spec) - a position-based selector would silently write the wrong card's date once that first reorder happens",
            run: function () {
                const findCardBySubject = (label) => {
                    const column = document.querySelector(".o_schedule_grid_day_column[data-day='0']");
                    return Array.from(column.querySelectorAll(".o_schedule_grid_card")).find((card) => {
                        const select = card.querySelector(".o_schedule_grid_card_subject");
                        const selected = Array.from(select.options).find((option) => option.selected);
                        // Substring, not equality - the option's real text is "ACRONYM: Name" (see
                        // ems.subject._compute_display_name), not the bare name given here.
                        return selected && selected.textContent.includes(label);
                    });
                };
                const setDateInput = (label, selector, value) => {
                    const input = findCardBySubject(label).querySelector(selector);
                    input.value = value;
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                };
                setDateInput("Split Tour Subject A", ".o_schedule_grid_card_date:first-of-type", "2026-09-01");
                setDateInput("Split Tour Subject A", ".o_schedule_grid_card_date:last-of-type", "2027-02-28");
                setDateInput("Split Tour Subject B", ".o_schedule_grid_card_date:first-of-type", "2027-03-01");
                setDateInput("Split Tour Subject B", ".o_schedule_grid_card_date:last-of-type", "2027-07-01");
            },
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Save')",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('Split Tour Subject A')",
            content: "Monday now shows the first subject's block",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('Split Tour Subject B')",
            content: "...and the second card's own block, side by side rather than hidden underneath it",
        },
    ],
});
