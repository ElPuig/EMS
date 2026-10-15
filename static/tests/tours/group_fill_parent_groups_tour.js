/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions } from "@ems/../tests/tours/actions_dropdown_helpers";

// A reinforcement group whose enrolled students come from two main groups it does not list yet:
// a warning above the form says so, and the Department Chief fills them from its button (also
// offered in the Actions dropdown). Seed data comes
// from TestGroupFillParentGroupsTour.
registry.category("web_tour.tours").add("ems_group_fill_parent_groups", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded reinforcement group",
            run: "edit Tour Fill Parents",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Fill Parents')",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert.o_group_missing_parent_groups:not(.o_form_sheet .o_group_missing_parent_groups) .o_field_widget[name='missing_parent_group_ids']:has(.o_tag ~ .o_tag)",
            content: "A warning above the form says its students come from two main groups it does not list",
        },
        ...checkActions({ offered: ["action_fill_parent_groups"] }, "The Actions dropdown offers to fill them too"),
        {
            trigger: ".o_group_missing_parent_groups button[name='action_fill_parent_groups']",
            content: "Fill the main groups from the warning's own button",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='parent_group_ids']:has(.o_tag ~ .o_tag)",
            content: "Both are now its main groups",
        },
        {
            trigger: ".o_form_view .o_form_sheet:not(:has(.o_group_missing_parent_groups))",
            content: "...and the warning is gone",
        },
    ],
});
