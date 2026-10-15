/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// A reinforcement group whose enrolled students come from two main groups it does not list yet:
// the form says so, and the Department Chief fills them from the Actions dropdown. Seed data comes
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
            trigger: ".o_group_missing_parent_groups .o_field_widget[name='missing_parent_group_ids']:has(.o_tag ~ .o_tag)",
            content: "The form says its students come from two main groups it does not list",
        },
        ...clickAction("action_fill_parent_groups", "Fill the main groups from the enrolled students"),
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
