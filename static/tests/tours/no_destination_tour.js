/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Students without destination" (action_students_no_destination) had zero coverage - neither
// the list itself nor its header's "Suggest destination group" bulk action
// (action_suggest_destination_group).
registry.category("web_tour.tours").add("ems_no_destination_suggest_group", {
    test: true,
    url: "/odoo/action-ems.action_students_no_destination",
    steps: () => [
        { trigger: ".o_list_view", content: "Students without destination list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit No Destination Tour Student",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        // Wait for the search to actually take effect (the facet chip renders synchronously
        // with the trigger the moment it's applied, unlike the resulting network re-render -
        // this dev DB has 1000+ real matches, so clicking a group header by name too early
        // risks hitting a same-named group from the still-unfiltered list instead).
        {
            trigger: ".o_searchview_facet:contains('No Destination Tour Student')",
            content: "The search facet is applied",
        },
        // The action's own context defaults to grouping by main_group_id
        // (search_default_gb_group) - drop it so the seeded row is a flat .o_data_row,
        // same pattern as applicant_tour.js. Scoped to the "Group" facet specifically since
        // the "Enrollment-flow studies" filter is a separate facet chip.
        {
            trigger: ".o_searchview_facet:contains('Group') .o_facet_remove",
            content: "Remove the default 'Group' grouping facet",
            run: "click",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('No Destination Tour Student')) .o_list_record_selector",
            content: "Select the seeded student",
            run: "click",
        },
        {
            trigger: ".o_list_view button:contains('Suggest destination group')",
            content: "Suggest a destination group",
            run: "click",
        },
        {
            trigger: ".o_notification:contains('destination group')",
            content: "A success notification confirms the enrollment was filled - verified against the DB afterward",
        },
    ],
});
