/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Academic history" (action_year_record_list, ems.student.year_record) had zero coverage -
// neither its own standalone list/form, nor the nested subject/outcome dialogs it opens, nor
// the "Academic history" tab on res.partner's own form (a separate rendering path for the
// same underlying data). The model is create="0" in the UI (records only come from
// generate_for_students(), called here directly like tests/test_year_record.py does), so this
// tour only ever opens an already-seeded record - never creates one through the UI.
registry.category("web_tour.tours").add("ems_year_record_list_and_subject", {
    test: true,
    url: "/odoo/action-ems.action_year_record_list",
    steps: () => [
        { trigger: ".o_list_view", content: "Academic history list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit Year Record Tour Student",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_searchview_facet:contains('Year Record Tour Student')",
            content: "The search facet is applied",
        },
        // The action's own context defaults to grouping by course (search_default_group_by_course).
        {
            trigger: ".o_searchview_facet:contains('Course') .o_facet_remove",
            content: "Remove the default 'Course' grouping facet",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Year Record Tour Student')",
            content: "Open the seeded year record",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_data_cell:contains('Year Record Tour Subject')",
            content: "The 'Subjects' tab (the form's only notebook page) rendered with the seeded subject record",
        },
        {
            // Odoo binds the row-open click handler to a data cell, not the bare <tr>.
            trigger: ".o_data_cell:contains('Year Record Tour Subject')",
            content: "Open the subject record's own popup form",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('Year Record Tour Outcome')",
            content: "The nested outcome list rendered inside the subject dialog",
        },
    ],
});

registry.category("web_tour.tours").add("ems_year_record_partner_tab", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        { trigger: ".o_control_panel", content: "Educational Community loaded" },
        { trigger: ".o_switch_view.o_list", content: "Switch to list view", run: "click" },
        { trigger: ".o_list_view", content: "List view rendered" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit Year Record Tour Student",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_searchview_facet:contains('Year Record Tour Student')",
            content: "The search facet is applied",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Year Record Tour Student')",
            content: "Open the seeded student",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Academic history')",
            content: "Open the Academic history tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='year_record_ids'] .o_data_row",
            content: "The embedded year_record_ids list rendered on the partner's own form (a separate rendering path from the standalone list/form tour)",
        },
    ],
});
