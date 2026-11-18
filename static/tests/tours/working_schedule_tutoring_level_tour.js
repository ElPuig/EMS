/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #846: a Department Chief (the least-privileged role allowed to edit a schedule) picks the
// level a tutoring (ATAL/TT) card is given to on the Schedule tab and saves; a class card has no
// level selector.
registry.category("web_tour.tours").add("ems_working_schedule_tutoring_level", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row",
            content: "List view rendered",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the tour's own teacher",
            run: "edit Tutoring Level Tour Teacher",
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
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Tutoring Level Tour Teacher')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='schedule']",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Enter edit mode",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card_level",
            content: "The tutoring card asks for a level",
            run: function () {
                const select = document.querySelector(".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card_level");
                const option = [...select.options].find((item) => item.textContent.includes("Tutoring Level Tour Level"));
                if (!option) {
                    throw new Error("The tour's level is not offered");
                }
                select.value = option.value;
                select.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='1']",
            content: "A class card (Tuesday) has no level selector",
            run: function () {
                if (document.querySelector(".o_schedule_grid_day_column[data-day='1'] .o_schedule_grid_card_level")) {
                    throw new Error("A class card must not ask for a level");
                }
            },
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
    ],
});
