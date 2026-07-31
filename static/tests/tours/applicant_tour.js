/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Preinscription" (action_ems_applicants, res.partner filtered to contact_type='applicant')
// had zero coverage: neither the list itself, nor an applicant's own form (whose "Applicant
// data" notebook page - the model's own default-open tab for this contact_type - had never
// rendered), nor its "Enrollment proposal" header button (shared with the tutor-facing screen
// covered by enrollment_proposal_tour.js, but exercised here via the auto-preselected-template
// code path instead of the manual one, since an applicant with a granted course hits a
// different branch of default_get than a plain renewing student does).
registry.category("web_tour.tours").add("ems_applicant_form_and_proposal", {
    test: true,
    url: "/odoo/action-ems.action_ems_applicants",
    steps: () => [
        { trigger: ".o_list_view", content: "Preinscription list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded applicant",
            run: "edit Preinscription Tour Applicant",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        // The action's own context defaults to grouping by shift then course (see
        // applicants.xml) - the seeded applicant has neither set, so it starts collapsed
        // inside a "None" group header, not a flat .o_data_row.
        {
            trigger: ".o_list_view .o_group_header:contains('None')",
            content: "Expand the seeded applicant's (ungrouped) group",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Preinscription Tour Applicant')",
            content: "Open the applicant's own form",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='study_id']",
            content: "The 'Applicant data' tab (the default one for this contact_type) rendered without crashing",
        },
        {
            trigger: ".o_control_panel .breadcrumb-item:contains('Preinscription')",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search again (breadcrumb navigation resets the list)",
            run: "edit Preinscription Tour Applicant",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_list_view .o_group_header:contains('None')",
            content: "Expand the group again (a fresh list load re-collapses it)",
            run: "click",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('Preinscription Tour Applicant')) .o_list_record_selector",
            content: "Select the applicant",
            run: "click",
        },
        {
            trigger: ".o_list_view button:contains('Enrollment proposal')",
            content: "Open the enrollment proposal wizard",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='template_id'] input:not(:value(''))",
            content: "The template got auto-preselected (granted course matches the template's study year) - verified against the DB afterward",
        },
        {
            trigger: ".modal footer button[name='action_create_enrollments']",
            content: "Create the enrollment",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Preinscription Tour Applicant')",
            content: "Back on the list - the wizard closed",
        },
    ],
});
