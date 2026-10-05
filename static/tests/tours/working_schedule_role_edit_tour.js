/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #531: a Department Chief (the least-privileged role allowed to edit a schedule) removes a
// teacher's only class from the Schedule tab and saves. Dropping a class deletes the teacher's
// derived ems.teaching row, which is what kept failing with an AccessError for Head of Studies -
// every other schedule tour logs in as admin, so none of them could see it.
registry.category("web_tour.tours").add("ems_working_schedule_role_edit", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            // Typing before the switch has settled loses the text: the control panel re-renders.
            trigger: ".o_list_view .o_data_row",
            content: "List view rendered",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the tour's own teacher",
            run: "edit Role Edit Tour Teacher",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_searchview_facet",
            content: "Search applied",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Role Edit Tour Teacher')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='schedule']",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('TWSRE')",
            content: "The saved class is shown",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Enter edit mode",
            run: "click",
        },
        {
            // Monday can hold other cards too (e.g. a break), so pick the one whose selected
            // subject is ours - read imperatively, since OWL doesn't sync the 'selected' attribute.
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card .o_schedule_grid_card_subject",
            content: "Remove Monday's class",
            run: function () {
                const card = [...document.querySelectorAll(".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card")].find(
                    (el) => el.querySelector(".o_schedule_grid_card_subject")?.selectedOptions[0]?.textContent.includes("Role Edit Tour Subject")
                );
                if (!card) {
                    throw new Error("Monday's class card not found");
                }
                card.querySelector(".o_schedule_grid_card_remove").click();
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0']:not(:has(.o_schedule_grid_card_subject option:checked:contains('Role Edit Tour Subject')))",
            content: "The card is gone from the edit buffer",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Save')",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Saved without an error, back in view mode",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "The class is gone",
            run: function () {
                const left = [...document.querySelectorAll(".o_schedule_grid_entry")].filter((el) => el.textContent.includes("TWSRE"));
                if (left.length) {
                    throw new Error("The removed class is still shown after saving");
                }
            },
        },
    ],
});
