/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #611: a main group's Schedule tab also shows the classes of its subgroups (split halves,
// optatives), each labelled with its subgroup; up to 3 at the same time side by side, more than
// that collapsed into one "N classes in parallel" block detailed in a table below the grid. Run as
// a plain teacher: reading a group's schedule needs no special role.
registry.category("web_tour.tours").add("ems_group_schedule_subgroups", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded main group",
            run: "edit Tour Subgroups Main",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Subgroups Main')",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='schedule']",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry:not(.o_schedule_grid_entry_parallel) .o_schedule_grid_entry_room:contains('Tour Half 1')",
            content: "The first half's class is in the main group's schedule, labelled with its subgroup",
        },
        {
            trigger: ".o_schedule_grid_entry:not(.o_schedule_grid_entry_parallel) .o_schedule_grid_entry_room:contains('Tour Half 2')",
            content: "...next to the other half's, at the same time",
        },
        {
            trigger: ".o_schedule_grid_entry_parallel .o_schedule_grid_entry_label:contains('4')",
            content: "The 4 optatives of the same hour are one block",
        },
        {
            trigger: ".o_schedule_grid_parallel tr:contains('Tour Optative 3'):contains('Tour Teacher Optative 3')",
            content: "...detailed below the grid, with its teacher",
        },
        {
            trigger: ".o_schedule_grid_parallel tr:contains('Tour Optative 4')",
            content: "Every collapsed class is listed",
        },
    ],
});
