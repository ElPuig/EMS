/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #676: the Department Chief sets the other half of a split group on one half's form. Seed
// data and the check that the other half got it too come from TestGroupJoinsWithTour.
registry.category("web_tour.tours").add("ems_group_joins_with", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded halves",
            run: "edit Tour Joins With",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Joins With A')",
            content: "Open the first half",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='joinable_group_ids'] input",
            content: "Type the other half",
            run: "edit Tour Joins With B",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('Tour Joins With B')",
            content: "Pick it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='joinable_group_ids'] .o_tag:contains('Tour Joins With B')",
            content: "It is now its other half",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});
