/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Enrollment proposal" (Academic management > Enrollment > Enrollment proposal,
// ems.action_student_group_enrollment - an ir.actions.server that re-domains
// act_window_student_group_enrollment by role before opening it) had zero coverage. Its list's
// <header> exposes two bulk actions on the selected students: "Enrollment proposal"
// (ems.enrollment_proposal_wizard) and "Graduation" (ems.graduation_wizard) - neither wizard,
// nor the list itself, nor the server-action redirect had ever been driven in a browser.
registry.category("web_tour.tours").add("ems_enrollment_proposal_create", {
    test: true,
    url: "/odoo/action-ems.action_student_group_enrollment",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The server-action-redirected list loaded",
        },
        // This dev DB has 1000+ real students, paginated - the seeded one isn't necessarily
        // on the first page under the default main_group_id sort, so search for it by name
        // first (same pattern as group_tour.js's "DAM1A" search).
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit Enrollment Proposal Tour Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Enrollment Proposal Tour Student')",
            content: "The seeded student is now shown",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('Enrollment Proposal Tour Student')) .o_list_record_selector",
            content: "Select the seeded student",
            run: "click",
        },
        {
            trigger: ".o_list_view button:contains('Enrollment proposal')",
            content: "Open the enrollment proposal wizard",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='template_id'] input",
            content: "Search for the seeded template (not auto-selected: the student isn't an applicant with a granted course)",
            run: "edit Enrollment Proposal Tour Template",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Enrollment Proposal Tour Template')",
            content: "Select the template",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='ems_group_id'] input:not(:value(''))",
            content: "The destination group got auto-suggested via _onchange_suggest_group (same group/course) - verified against the DB afterward",
        },
        {
            trigger: ".modal footer button[name='action_create_enrollments']",
            content: "Create the enrollment",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Enrollment Proposal Tour Student')",
            content: "Back on the list - the wizard closed via ir.actions.act_window_close",
        },
    ],
});

registry.category("web_tour.tours").add("ems_enrollment_proposal_graduation", {
    test: true,
    url: "/odoo/action-ems.action_student_group_enrollment",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the second seeded student",
            run: "edit Enrollment Proposal Tour Graduate",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Enrollment Proposal Tour Graduate')",
            content: "The seeded student is now shown",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('Enrollment Proposal Tour Graduate')) .o_list_record_selector",
            content: "Select the student to mark as graduated",
            run: "click",
        },
        {
            trigger: ".o_list_view button:contains('Graduation')",
            content: "Open the graduation wizard",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('Enrollment Proposal Tour Graduate')",
            content: "The wizard's embedded line list rendered with the selected student",
        },
        {
            trigger: ".modal footer button[name='action_apply']",
            content: "Mark graduation",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Enrollment Proposal Tour Graduate')",
            content: "Back on the list - the wizard closed",
        },
    ],
});
